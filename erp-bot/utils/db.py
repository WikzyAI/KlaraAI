"""
PostgreSQL database layer for the ERP bot using asyncpg.
Replaces the old JSON-based database for concurrent-safe operations.
"""
import asyncpg
import json
import os
from datetime import datetime, timezone, timedelta
import config


# Daily quotas reset on a 24h rolling window: when a user starts using their
# quota (first message of the window) `last_reset` is set to NOW; once 24h
# elapse, the counters reset and the next message starts a fresh window.
RESET_WINDOW = timedelta(hours=24)


class PostgresDB:
    """Async PostgreSQL database handler using asyncpg pool."""
    _pool = None

    @classmethod
    async def init_db(cls, database_url: str = None):
        """Initialize the connection pool and create tables if needed."""
        url = database_url or config.DATABASE_URL
        if not url:
            raise ValueError("DATABASE_URL not set in environment or config.")

        cls._pool = await asyncpg.create_pool(url, min_size=2, max_size=20)

        async with cls._pool.acquire() as conn:
            # Profiles table — last_reset is a TIMESTAMPTZ (24h rolling window).
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS profiles (
                    user_id BIGINT PRIMARY KEY,
                    name TEXT,
                    age INT,
                    description TEXT DEFAULT '',
                    sub_type TEXT DEFAULT 'free',
                    credits INT DEFAULT 0,
                    daily_msgs_used INT DEFAULT 0,
                    daily_sessions_used INT DEFAULT 0,
                    last_reset TIMESTAMPTZ,
                    response_length TEXT DEFAULT 'medium'
                )
            """)

            # Idempotent migration: legacy column was DATE; convert to TIMESTAMPTZ.
            await conn.execute("""
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'profiles'
                          AND column_name = 'last_reset'
                          AND data_type = 'date'
                    ) THEN
                        ALTER TABLE profiles
                            ALTER COLUMN last_reset DROP DEFAULT,
                            ALTER COLUMN last_reset TYPE TIMESTAMPTZ
                                USING last_reset::timestamptz;
                    END IF;
                END $$;
            """)

            # Sessions table — one active /erp session per user.
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    user_id BIGINT PRIMARY KEY,
                    character_key TEXT,
                    character_name TEXT,
                    messages JSONB DEFAULT '[]',
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            # Legacy columns from the removed /chat feature — kept here so
            # existing deployments don't error on SELECT/INSERT, but the code
            # no longer reads or writes them. Safe to DROP COLUMN later if
            # you want a clean schema.

            # Archived sessions — when a user ends a scene, we keep the message
            # history per (user, character) pair so they can choose to "continue
            # from where they left off" the next time they pick the same
            # character (instead of always starting fresh).
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS archived_sessions (
                    user_id BIGINT NOT NULL,
                    character_key TEXT NOT NULL,
                    messages JSONB NOT NULL,
                    ended_at TIMESTAMPTZ DEFAULT NOW(),
                    PRIMARY KEY (user_id, character_key)
                )
            """)

            # Characters table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS characters (
                    key TEXT PRIMARY KEY,
                    name TEXT,
                    "desc" TEXT,
                    personality TEXT,
                    creator TEXT,
                    is_default BOOL DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)

            # Long-term memories table (per user/character pair)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    character_key TEXT NOT NULL,
                    content TEXT NOT NULL,
                    importance INT DEFAULT 5,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_memories_lookup
                ON memories (user_id, character_key, importance DESC, created_at DESC)
            """)

            # Referral rewards log (one row per referral relationship)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS referrals (
                    referred_id BIGINT PRIMARY KEY,
                    referrer_id BIGINT NOT NULL,
                    code_used TEXT NOT NULL,
                    signup_bonus_granted BOOL DEFAULT FALSE,
                    purchase_bonus_granted BOOL DEFAULT FALSE,
                    referee_msg_count INT DEFAULT 0,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            # Idempotent: add the column if upgrading from a previous version.
            await conn.execute(
                "ALTER TABLE referrals ADD COLUMN IF NOT EXISTS referee_msg_count INT DEFAULT 0"
            )
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_referrals_referrer
                ON referrals (referrer_id)
            """)

            # Streak / referral / engagement columns on profiles (idempotent)
            await conn.execute("""
                ALTER TABLE profiles
                    ADD COLUMN IF NOT EXISTS streak_count INT DEFAULT 0,
                    ADD COLUMN IF NOT EXISTS streak_max INT DEFAULT 0,
                    ADD COLUMN IF NOT EXISTS streak_last_day DATE,
                    ADD COLUMN IF NOT EXISTS referral_code TEXT,
                    ADD COLUMN IF NOT EXISTS total_purchased_credits INT DEFAULT 0,
                    ADD COLUMN IF NOT EXISTS language TEXT DEFAULT 'auto'
            """)
            await conn.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_profiles_referral_code
                ON profiles (referral_code) WHERE referral_code IS NOT NULL
            """)

        # Insert default characters if not present
        await cls._insert_default_characters()

    @classmethod
    async def _insert_default_characters(cls):
        """Insert default characters from config if they don't exist."""
        async with cls._pool.acquire() as conn:
            for key, char in config.DEFAULT_CHARACTERS.items():
                exists = await conn.fetchval(
                    "SELECT COUNT(*) FROM characters WHERE key = $1", key
                )
                if not exists:
                    await conn.execute(
                        "INSERT INTO characters (key, name, \"desc\", personality, creator, is_default) "
                        "VALUES ($1, $2, $3, $4, NULL, TRUE)",
                        key, char["name"], char["desc"], char["personality"]
                    )

    @classmethod
    async def close_db(cls):
        """Close the connection pool."""
        if cls._pool:
            await cls._pool.close()
            cls._pool = None

    # ---- Helper ----
    @classmethod
    def _pool_get(cls):
        if not cls._pool:
            raise RuntimeError("Database not initialized. Call PostgresDB.init_db() first.")
        return cls._pool

    # ---- Profile methods ----

    @classmethod
    async def get_profile(cls, user_id) -> dict:
        user_id = int(user_id)
        pool = cls._pool_get()
        async with pool.acquire() as conn:
            # Atomic: insert if not exists, then fetch
            await conn.execute(
                "INSERT INTO profiles (user_id) VALUES ($1) ON CONFLICT (user_id) DO NOTHING",
                user_id
            )
            row = await conn.fetchrow(
                "SELECT user_id, name, age, description, sub_type, credits, "
                "daily_msgs_used, daily_sessions_used, last_reset, response_length, "
                "language "
                "FROM profiles WHERE user_id = $1",
                user_id
            )
            profile = dict(row)

        # Check and reset daily counters
        profile = await cls._check_reset_daily(profile)
        return profile

    @classmethod
    async def _check_reset_daily(cls, profile: dict) -> dict:
        """
        24h rolling window: if the window opened more than 24h ago, reset the
        counters and clear the window (a new window starts on the next message).
        """
        last_reset = profile.get("last_reset")
        if last_reset is None:
            return profile
        # asyncpg returns timezone-aware datetimes for TIMESTAMPTZ
        if last_reset.tzinfo is None:
            last_reset = last_reset.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - last_reset >= RESET_WINDOW:
            pool = cls._pool_get()
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE profiles SET daily_msgs_used = 0, daily_sessions_used = 0, "
                    "last_reset = NULL WHERE user_id = $1",
                    profile["user_id"]
                )
            profile["daily_msgs_used"] = 0
            profile["daily_sessions_used"] = 0
            profile["last_reset"] = None
        return profile

    @classmethod
    def get_reset_at(cls, profile: dict):
        """
        Return the UTC datetime at which the user's daily quota will reset,
        or None if the user has not started a window yet (full quota available).
        """
        last_reset = profile.get("last_reset")
        if last_reset is None:
            return None
        if last_reset.tzinfo is None:
            last_reset = last_reset.replace(tzinfo=timezone.utc)
        return last_reset + RESET_WINDOW

    @classmethod
    async def update_profile(cls, user_id, **kwargs) -> dict:
        user_id = int(user_id)
        pool = cls._pool_get()
        profile = await cls.get_profile(user_id)

        for k, v in kwargs.items():
            if k in ("name", "age", "description", "sub_type", "credits",
                     "daily_msgs_used", "daily_sessions_used", "response_length",
                     "last_reset", "language"):
                profile[k] = v

        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE profiles SET name = $1, age = $2, description = $3, sub_type = $4, "
                "credits = $5, daily_msgs_used = $6, daily_sessions_used = $7, "
                "response_length = $8, last_reset = $9, language = $10 "
                "WHERE user_id = $11",
                profile.get("name"), profile.get("age"), profile.get("description"),
                profile.get("sub_type"), profile.get("credits"),
                profile.get("daily_msgs_used"), profile.get("daily_sessions_used"),
                profile.get("response_length"), profile.get("last_reset"),
                profile.get("language") or "auto", user_id
            )
        return profile

    @classmethod
    async def get_sub_type(cls, user_id) -> str:
        user_id = int(user_id)
        profile = await cls.get_profile(user_id)
        return profile.get("sub_type", "free")

    @classmethod
    async def is_premium(cls, user_id) -> bool:
        user_id = int(user_id)
        return await cls.get_sub_type(user_id) in ["standard", "premium"]

    @classmethod
    async def is_premium_plus(cls, user_id) -> bool:
        user_id = int(user_id)
        return await cls.get_sub_type(user_id) == "premium"

    @classmethod
    async def can_send_message(cls, user_id) -> bool:
        user_id = int(user_id)
        profile = await cls.get_profile(user_id)
        sub = config.SUBSCRIPTIONS.get(profile["sub_type"], config.SUBSCRIPTIONS["free"])
        max_daily = sub["daily_msgs"]
        if max_daily == -1:
            return True
        return profile["daily_msgs_used"] < max_daily

    @classmethod
    async def increment_messages(cls, user_id):
        user_id = int(user_id)
        pool = cls._pool_get()
        async with pool.acquire() as conn:
            # Open a fresh 24h window the moment the counter starts climbing.
            await conn.execute(
                "UPDATE profiles SET "
                "daily_msgs_used = daily_msgs_used + 1, "
                "last_reset = COALESCE(last_reset, NOW()) "
                "WHERE user_id = $1",
                user_id
            )

    @classmethod
    async def can_start_session(cls, user_id) -> bool:
        user_id = int(user_id)
        profile = await cls.get_profile(user_id)
        sub = config.SUBSCRIPTIONS.get(profile["sub_type"], config.SUBSCRIPTIONS["free"])
        max_daily = sub["daily_sessions"]
        if max_daily == -1:
            return True
        return profile["daily_sessions_used"] < max_daily

    @classmethod
    async def increment_sessions(cls, user_id):
        user_id = int(user_id)
        pool = cls._pool_get()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE profiles SET "
                "daily_sessions_used = daily_sessions_used + 1, "
                "last_reset = COALESCE(last_reset, NOW()) "
                "WHERE user_id = $1",
                user_id
            )

    @classmethod
    async def get_limits(cls, user_id) -> dict:
        user_id = int(user_id)
        profile = await cls.get_profile(user_id)
        sub_type = profile.get("sub_type", "free")
        sub = config.SUBSCRIPTIONS.get(sub_type, config.SUBSCRIPTIONS["free"])
        return {
            "daily_msgs": sub["daily_msgs"],
            "daily_sessions": sub["daily_sessions"],
            "max_tokens": sub["max_tokens"],
            "context": sub["context"],
            "custom_chars": sub["custom_chars"],
            "allowed_lengths": sub["allowed_lengths"],
            "price_month": sub["price_month"],
            "price_day": sub["price_day"],
            "type": sub_type,
            "name": sub["name"]
        }

    # ---- Session methods ----

    @classmethod
    async def get_session(cls, user_id) -> dict | None:
        user_id = int(user_id)
        pool = cls._pool_get()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT character_key, character_name, messages, created_at "
                "FROM sessions WHERE user_id = $1",
                user_id
            )
            if not row:
                return None
            return {
                "character": row["character_key"],
                "character_name": row["character_name"],
                "messages": row["messages"] if isinstance(row["messages"], list) else json.loads(row["messages"]),
            }

    @classmethod
    async def set_session(cls, user_id, session: dict):
        user_id = int(user_id)
        pool = cls._pool_get()
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO sessions (user_id, character_key, character_name, messages) "
                "VALUES ($1, $2, $3, $4) "
                "ON CONFLICT (user_id) DO UPDATE SET "
                "character_key = EXCLUDED.character_key, "
                "character_name = EXCLUDED.character_name, "
                "messages = EXCLUDED.messages",
                user_id,
                session["character"],
                session["character_name"],
                json.dumps(session["messages"]),
            )

    @classmethod
    async def delete_session(cls, user_id):
        user_id = int(user_id)
        pool = cls._pool_get()
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM sessions WHERE user_id = $1", user_id)

    # ---- Archived session methods (Continue / Start fresh feature) ----

    @classmethod
    async def archive_session(cls, user_id, character_key: str, messages: list):
        """Save a session's message history so the user can resume next time."""
        user_id = int(user_id)
        if not character_key or not messages:
            return
        pool = cls._pool_get()
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO archived_sessions (user_id, character_key, messages, ended_at) "
                "VALUES ($1, $2, $3, NOW()) "
                "ON CONFLICT (user_id, character_key) DO UPDATE SET "
                "messages = EXCLUDED.messages, ended_at = NOW()",
                user_id, character_key, json.dumps(messages)
            )

    @classmethod
    async def get_archived_session(cls, user_id, character_key: str) -> dict | None:
        """Returns {messages, ended_at, count} or None if no archive exists."""
        user_id = int(user_id)
        pool = cls._pool_get()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT messages, ended_at FROM archived_sessions "
                "WHERE user_id = $1 AND character_key = $2",
                user_id, character_key
            )
            if not row:
                return None
            messages = row["messages"] if isinstance(row["messages"], list) \
                else json.loads(row["messages"])
            return {
                "messages": messages,
                "ended_at": row["ended_at"],
                "count": len(messages),
            }

    @classmethod
    async def clear_archived_session(cls, user_id, character_key: str):
        user_id = int(user_id)
        pool = cls._pool_get()
        async with pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM archived_sessions WHERE user_id = $1 AND character_key = $2",
                user_id, character_key
            )

    @classmethod
    async def has_active_session(cls, user_id) -> bool:
        user_id = int(user_id)
        pool = cls._pool_get()
        async with pool.acquire() as conn:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM sessions WHERE user_id = $1", user_id
            )
            return count > 0

    # ---- Character methods ----

    @classmethod
    async def get_all_characters(cls) -> dict:
        pool = cls._pool_get()
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT key, name, \"desc\", personality, creator FROM characters")
            result = {}
            for row in rows:
                result[row["key"]] = {
                    "name": row["name"],
                    "desc": row["desc"],
                    "personality": row["personality"],
                    "creator": row["creator"],
                }
            return result

    @classmethod
    async def get_visible_characters(cls, user_id: str) -> dict:
        """Get characters visible to user (public + own private ones)."""
        all_chars = await cls.get_all_characters()
        return {k: v for k, v in all_chars.items()
                if v.get("creator") is None or str(v.get("creator")) == str(user_id)}

    @classmethod
    async def set_character(cls, key: str, data: dict):
        pool = cls._pool_get()
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO characters (key, name, \"desc\", personality, creator) "
                "VALUES ($1, $2, $3, $4, $5) "
                "ON CONFLICT (key) DO UPDATE SET "
                "name = EXCLUDED.name, \"desc\" = EXCLUDED.\"desc\", "
                "personality = EXCLUDED.personality, creator = EXCLUDED.creator",
                key, data["name"], data["desc"], data["personality"],
                data.get("creator")
            )

    @classmethod
    async def delete_character(cls, key: str):
        pool = cls._pool_get()
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM characters WHERE key = $1", key)

    @classmethod
    async def character_exists(cls, key: str) -> bool:
        pool = cls._pool_get()
        async with pool.acquire() as conn:
            count = await conn.fetchval("SELECT COUNT(*) FROM characters WHERE key = $1", key)
            return count > 0

    @classmethod
    async def is_character_visible(cls, key: str, user_id: str) -> bool:
        pool = cls._pool_get()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT creator FROM characters WHERE key = $1", key)
            if not row:
                return False
            creator = row["creator"]
            if creator is None:
                return True
            return str(creator) == str(user_id)

    # ---- Memory methods ----

    @classmethod
    async def add_memory(cls, user_id, character_key: str, content: str, importance: int = 5):
        user_id = int(user_id)
        pool = cls._pool_get()
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO memories (user_id, character_key, content, importance) "
                "VALUES ($1, $2, $3, $4)",
                user_id, character_key, content[:1000], max(1, min(10, importance))
            )

    @classmethod
    async def add_memories_bulk(cls, user_id, character_key: str, items: list):
        """items = [{'content': str, 'importance': int}, ...]"""
        user_id = int(user_id)
        if not items:
            return
        pool = cls._pool_get()
        async with pool.acquire() as conn:
            await conn.executemany(
                "INSERT INTO memories (user_id, character_key, content, importance) "
                "VALUES ($1, $2, $3, $4)",
                [(user_id, character_key, m["content"][:1000],
                  max(1, min(10, int(m.get("importance", 5))))) for m in items]
            )

    @classmethod
    async def get_memories(cls, user_id, character_key: str, limit: int = 12) -> list:
        user_id = int(user_id)
        pool = cls._pool_get()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, content, importance, created_at FROM memories "
                "WHERE user_id = $1 AND character_key = $2 "
                "ORDER BY importance DESC, created_at DESC LIMIT $3",
                user_id, character_key, limit
            )
            return [dict(r) for r in rows]

    @classmethod
    async def get_all_memories_grouped(cls, user_id) -> dict:
        """All memories for a user, grouped by character_key."""
        user_id = int(user_id)
        pool = cls._pool_get()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, character_key, content, importance, created_at FROM memories "
                "WHERE user_id = $1 ORDER BY character_key, importance DESC, created_at DESC",
                user_id
            )
        grouped = {}
        for r in rows:
            grouped.setdefault(r["character_key"], []).append(dict(r))
        return grouped

    @classmethod
    async def delete_memory(cls, memory_id: int, user_id) -> bool:
        user_id = int(user_id)
        pool = cls._pool_get()
        async with pool.acquire() as conn:
            res = await conn.execute(
                "DELETE FROM memories WHERE id = $1 AND user_id = $2",
                memory_id, user_id
            )
            return res.endswith(" 1")

    @classmethod
    async def clear_memories(cls, user_id, character_key: str = None) -> int:
        user_id = int(user_id)
        pool = cls._pool_get()
        async with pool.acquire() as conn:
            if character_key is None:
                res = await conn.execute(
                    "DELETE FROM memories WHERE user_id = $1", user_id
                )
            else:
                res = await conn.execute(
                    "DELETE FROM memories WHERE user_id = $1 AND character_key = $2",
                    user_id, character_key
                )
            try:
                return int(res.split()[-1])
            except Exception:
                return 0

    # ---- Streak methods ----

    @classmethod
    async def update_streak(cls, user_id) -> dict:
        """
        Bump the streak based on UTC calendar day.
        Returns {'streak': int, 'milestone_reward': int (credits, 0 if none)}.
        Milestones: day 3 (+3), 7 (+10), 14 (+20), 30 (+50), then every 7 days (+15).
        """
        from datetime import date, timedelta as _td
        user_id = int(user_id)
        pool = cls._pool_get()
        today = date.today()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT streak_count, streak_max, streak_last_day FROM profiles WHERE user_id = $1",
                user_id
            )
            if row is None:
                return {"streak": 0, "milestone_reward": 0}

            current = row["streak_count"] or 0
            max_streak = row["streak_max"] or 0
            last_day = row["streak_last_day"]

            if last_day == today:
                return {"streak": current, "milestone_reward": 0}

            if last_day == today - _td(days=1):
                current += 1
            else:
                current = 1

            if current > max_streak:
                max_streak = current

            await conn.execute(
                "UPDATE profiles SET streak_count = $1, streak_max = $2, streak_last_day = $3 "
                "WHERE user_id = $4",
                current, max_streak, today, user_id
            )

        reward = 0
        if current == 3:
            reward = 3
        elif current == 7:
            reward = 10
        elif current == 14:
            reward = 20
        elif current == 30:
            reward = 50
        elif current > 30 and (current - 30) % 7 == 0:
            reward = 15

        return {"streak": current, "milestone_reward": reward}

    @classmethod
    async def get_streak(cls, user_id) -> dict:
        from datetime import date, timedelta as _td
        user_id = int(user_id)
        pool = cls._pool_get()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT streak_count, streak_max, streak_last_day FROM profiles WHERE user_id = $1",
                user_id
            )
        if row is None:
            return {"streak": 0, "max": 0, "active": False}
        current = row["streak_count"] or 0
        last_day = row["streak_last_day"]
        today = date.today()
        active = last_day in (today, today - _td(days=1))
        if not active:
            current = 0
        return {"streak": current, "max": row["streak_max"] or 0, "active": active}

    # ---- Referral methods ----

    @classmethod
    async def get_or_create_referral_code(cls, user_id) -> str:
        import secrets
        user_id = int(user_id)
        pool = cls._pool_get()
        async with pool.acquire() as conn:
            existing = await conn.fetchval(
                "SELECT referral_code FROM profiles WHERE user_id = $1", user_id
            )
            if existing:
                return existing
            # Generate a unique 6-char code (no ambiguous chars)
            alphabet = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
            for _ in range(20):
                code = "".join(secrets.choice(alphabet) for _ in range(6))
                try:
                    await conn.execute(
                        "UPDATE profiles SET referral_code = $1 WHERE user_id = $2",
                        code, user_id
                    )
                    return code
                except asyncpg.UniqueViolationError:
                    continue
            raise RuntimeError("Could not generate a unique referral code")

    @classmethod
    async def get_referrer_by_code(cls, code: str):
        pool = cls._pool_get()
        async with pool.acquire() as conn:
            return await conn.fetchval(
                "SELECT user_id FROM profiles WHERE referral_code = $1", code
            )

    @classmethod
    async def has_used_referral(cls, user_id) -> bool:
        user_id = int(user_id)
        pool = cls._pool_get()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT 1 FROM referrals WHERE referred_id = $1", user_id
            )
            return row is not None

    @classmethod
    async def record_referral(cls, referred_id, referrer_id, code: str) -> bool:
        """Insert a referral row. Returns False if already exists or self-referral."""
        referred_id = int(referred_id)
        referrer_id = int(referrer_id)
        if referred_id == referrer_id:
            return False
        pool = cls._pool_get()
        async with pool.acquire() as conn:
            try:
                await conn.execute(
                    "INSERT INTO referrals (referred_id, referrer_id, code_used) "
                    "VALUES ($1, $2, $3)",
                    referred_id, referrer_id, code
                )
                return True
            except asyncpg.UniqueViolationError:
                return False

    @classmethod
    async def mark_signup_bonus_granted(cls, referred_id):
        referred_id = int(referred_id)
        pool = cls._pool_get()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE referrals SET signup_bonus_granted = TRUE WHERE referred_id = $1",
                referred_id
            )

    @classmethod
    async def get_referral_for_purchase(cls, referred_id):
        """
        Return the referral row if this user was referred and the referrer has
        not yet been rewarded for this user's first purchase. Else None.
        """
        referred_id = int(referred_id)
        pool = cls._pool_get()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT referrer_id, code_used FROM referrals "
                "WHERE referred_id = $1 AND purchase_bonus_granted = FALSE",
                referred_id
            )
            return dict(row) if row else None

    @classmethod
    async def mark_purchase_bonus_granted(cls, referred_id):
        referred_id = int(referred_id)
        pool = cls._pool_get()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE referrals SET purchase_bonus_granted = TRUE WHERE referred_id = $1",
                referred_id
            )

    @classmethod
    async def get_referral_stats(cls, user_id) -> dict:
        user_id = int(user_id)
        pool = cls._pool_get()
        async with pool.acquire() as conn:
            total = await conn.fetchval(
                "SELECT COUNT(*) FROM referrals WHERE referrer_id = $1", user_id
            )
            converted = await conn.fetchval(
                "SELECT COUNT(*) FROM referrals "
                "WHERE referrer_id = $1 AND purchase_bonus_granted = TRUE",
                user_id
            )
        return {"total": total or 0, "converted": converted or 0}

    @classmethod
    async def increment_referee_msg_count(cls, referred_id) -> dict:
        """
        Track referee activity. Returns the row's current state if a referral
        exists (so callers can decide whether to grant the gated signup bonus).
        Safe no-op for users without a referral.
        """
        referred_id = int(referred_id)
        pool = cls._pool_get()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "UPDATE referrals SET referee_msg_count = referee_msg_count + 1 "
                "WHERE referred_id = $1 "
                "RETURNING referrer_id, referee_msg_count, signup_bonus_granted",
                referred_id
            )
            return dict(row) if row else None

    @classmethod
    async def add_purchased_credits(cls, user_id, amount: int):
        """Track lifetime purchases (used to detect 'first purchase' for referrals)."""
        user_id = int(user_id)
        pool = cls._pool_get()
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO profiles (user_id, total_purchased_credits) VALUES ($1, $2) "
                "ON CONFLICT (user_id) DO UPDATE SET "
                "total_purchased_credits = COALESCE(profiles.total_purchased_credits, 0) + $2",
                user_id, amount
            )

    @classmethod
    async def get_total_purchased_credits(cls, user_id) -> int:
        user_id = int(user_id)
        pool = cls._pool_get()
        async with pool.acquire() as conn:
            v = await conn.fetchval(
                "SELECT total_purchased_credits FROM profiles WHERE user_id = $1", user_id
            )
            return v or 0
