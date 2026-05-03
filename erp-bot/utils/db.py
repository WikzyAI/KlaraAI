"""
Utilitaires de base de données JSON pour le bot ERP.
"""
import json
import os
from datetime import datetime
import config
from utils.api_client import get_credits


class JSONDatabase:
    def __init__(self, filename: str):
        self.filename = filename
        self._ensure_exists()

    def _ensure_exists(self):
        if not os.path.exists(self.filename):
            self.save({})

    def load(self) -> dict:
        try:
            with open(self.filename, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

    def save(self, data: dict):
        with open(self.filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get(self, key: str, default=None):
        data = self.load()
        return data.get(str(key), default)

    def set(self, key: str, value):
        data = self.load()
        data[str(key)] = value
        self.save(data)

    def delete(self, key: str):
        data = self.load()
        if str(key) in data:
            del data[str(key)]
            self.save(data)


class ProfilesDB(JSONDatabase):
    def get_profile(self, user_id: int) -> dict:
        default = {
            "name": None,
            "age": None,
            "description": None,
            "sub_type": "free",
            "credits": 0,
            "daily_msgs_used": 0,
            "daily_sessions_used": 0,
            "last_reset": datetime.now().strftime("%Y-%m-%d"),
        }
        profile = self.get(str(user_id), default)
        for k, v in default.items():
            if k not in profile:
                profile[k] = v
        return profile

    def update_profile(self, user_id: int, **kwargs):
        profile = self.get_profile(user_id)
        profile.update(kwargs)
        self.set(str(user_id), profile)
        return profile

    def get_sub_type(self, user_id: int) -> str:
        profile = self.get_profile(user_id)
        return profile.get("sub_type", "free")

    def is_premium(self, user_id: int) -> bool:
        """Standard ou Premium."""
        return self.get_sub_type(user_id) in ["standard", "premium"]

    def is_premium_plus(self, user_id: int) -> bool:
        """Premium uniquement."""
        return self.get_sub_type(user_id) == "premium"

    def _check_reset_daily(self, profile: dict) -> dict:
        today = datetime.now().strftime("%Y-%m-%d")
        if profile.get("last_reset") != today:
            profile["daily_msgs_used"] = 0
            profile["daily_sessions_used"] = 0
            profile["last_reset"] = today
        return profile

    def can_send_message(self, user_id: int) -> bool:
        profile = self.get_profile(user_id)
        profile = self._check_reset_daily(profile)
        self.set(str(user_id), profile)
        sub = config.SUBSCRIPTIONS.get(profile["sub_type"], config.SUBSCRIPTIONS["free"])
        max_daily = sub["daily_msgs"]
        if max_daily == -1:
            return True
        return profile["daily_msgs_used"] < max_daily

    def increment_messages(self, user_id: int):
        profile = self.get_profile(user_id)
        profile = self._check_reset_daily(profile)
        profile["daily_msgs_used"] += 1
        self.set(str(user_id), profile)

    def can_start_session(self, user_id: int) -> bool:
        profile = self.get_profile(user_id)
        profile = self._check_reset_daily(profile)
        self.set(str(user_id), profile)
        sub = config.SUBSCRIPTIONS.get(profile["sub_type"], config.SUBSCRIPTIONS["free"])
        max_daily = sub["daily_sessions"]
        if max_daily == -1:
            return True
        return profile["daily_sessions_used"] < max_daily

    def increment_sessions(self, user_id: int):
        profile = self.get_profile(user_id)
        profile = self._check_reset_daily(profile)
        profile["daily_sessions_used"] += 1
        self.set(str(user_id), profile)

    def get_limits(self, user_id: int) -> dict:
        profile = self.get_profile(user_id)
        sub_type = profile.get("sub_type", "free")

        # Check API credits to determine actual subscription level
        try:
            from utils.api_client import get_credits
            import asyncio
            credits_data = get_credits(str(user_id))
            credits = credits_data.get("credits", 0)
            # Upgrade sub_type based on credits if needed
            if credits >= 3200 and sub_type != "premium":
                sub_type = "premium"
                self.update_profile(user_id, sub_type="premium")
            elif credits >= 1600 and sub_type == "free":
                sub_type = "standard"
                self.update_profile(user_id, sub_type="standard")
        except Exception as e:
            print(f"[DB] Error checking API credits: {e}")

        sub = config.SUBSCRIPTIONS.get(sub_type, config.SUBSCRIPTIONS["free"])
        return {
            "daily_msgs": sub["daily_msgs"],
            "daily_sessions": sub["daily_sessions"],
            "max_tokens": sub["max_tokens"],
            "context": sub["context"],
            "custom_chars": sub["custom_chars"],
            "price_month": sub["price_month"],
            "price_day": sub["price_day"],
            "type": sub_type,
            "name": sub["name"]
        }


class HistoryDB(JSONDatabase):
    def get_session(self, user_id: int) -> dict | None:
        data = self.load()
        return data.get(str(user_id))

    def set_session(self, user_id: int, session: dict):
        data = self.load()
        data[str(user_id)] = session
        self.save(data)

    def delete_session(self, user_id: int):
        self.delete(str(user_id))

    def has_active_session(self, user_id: int) -> bool:
        return self.get_session(user_id) is not None
