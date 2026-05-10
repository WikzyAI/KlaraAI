// ============================================
// KlaraAI Credits API Server (Postgres-backed)
// ============================================

require('dotenv').config();
const express = require('express');
const cors = require('cors');
const path = require('path');
const fs = require('fs');
const { Pool } = require('pg');
const stripe = require('stripe')(process.env.STRIPE_SECRET_KEY || 'sk_test_YOUR_STRIPE_SECRET_KEY');

// ============================================
// Config
// ============================================
const app = express();
const PORT = process.env.PORT || 3000;
const JSON_DB = path.join(__dirname, 'credits.json'); // legacy — used only as one-shot migration source
const BOT_TOKEN = process.env.DISCORD_TOKEN || process.env.DISCORD_BOT_TOKEN || '';

const ADMIN_USER_IDS = new Set(
    (process.env.ADMIN_USER_IDS || '')
        .split(',')
        .map(s => s.trim())
        .filter(s => /^\d+$/.test(s))
);

const CREDIT_PACKS = {
    'Starter':  { credits: 100,  price_usd: 100  },
    'Popular':  { credits: 500,  price_usd: 500  },
    'Pro':      { credits: 1000, price_usd: 1000 },
    'Elite':    { credits: 5000, price_usd: 5000 },
    'Standard': { credits: 1600, price_usd: 1600 },
    'Premium':  { credits: 3200, price_usd: 3200 },
};

const REFERRER_PURCHASE_BONUS = 200;
const REFERRER_PURCHASE_THRESHOLD = 500;

console.log('[Stripe] Configured:', process.env.STRIPE_SECRET_KEY ? 'YES' : 'NO (using test key)');
console.log('[Server] Bot token configured:', BOT_TOKEN ? 'YES' : 'NO');
console.log('[Admin] Configured admin Discord IDs:', ADMIN_USER_IDS.size);

if (BOT_TOKEN) {
    fetch('https://discord.com/api/users/@me', {
        headers: { 'Authorization': `Bot ${BOT_TOKEN}` }
    }).then(res => {
        if (res.ok) {
            res.json().then(user => {
                console.log(`[Bot] Connected as ${user.username} (${user.id})`);
            });
        } else {
            console.error(`[Bot] Token test failed: ${res.status} ${res.statusText}`);
        }
    }).catch(e => {
        console.error('[Bot] Token test error:', e.message);
    });
}

// ============================================
// Postgres setup
// ============================================
if (!process.env.DATABASE_URL) {
    console.error('[FATAL] DATABASE_URL is not set. The API needs Postgres to persist credits.');
    process.exit(1);
}

const pool = new Pool({
    connectionString: process.env.DATABASE_URL,
    ssl: { rejectUnauthorized: false },
    max: 10,
});
pool.on('error', (err) => {
    console.error('[pg] idle client error:', err);
});

async function initSchema() {
    await pool.query(`
        CREATE TABLE IF NOT EXISTS credit_users (
            discord_id TEXT PRIMARY KEY,
            username TEXT,
            credits INTEGER NOT NULL DEFAULT 0,
            total_purchased INTEGER NOT NULL DEFAULT 0,
            referrer_id TEXT,
            referrer_granted BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    `);
    await pool.query(`
        CREATE TABLE IF NOT EXISTS credit_history (
            id SERIAL PRIMARY KEY,
            discord_id TEXT NOT NULL,
            type TEXT,
            amount INTEGER,
            pack_name TEXT,
            timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            stripe_session TEXT,
            payment_status TEXT
        )
    `);
    await pool.query(`CREATE INDEX IF NOT EXISTS idx_credit_history_user ON credit_history (discord_id, timestamp DESC)`);
    await pool.query(`CREATE INDEX IF NOT EXISTS idx_credit_users_referrer ON credit_users (referrer_id)`);
    await pool.query(`CREATE INDEX IF NOT EXISTS idx_credit_users_updated ON credit_users (updated_at DESC)`);
    // Marker table so one-shot migrations never replay (even if credit_users
    // is somehow empty on a later boot, we do NOT re-import old JSON data).
    await pool.query(`
        CREATE TABLE IF NOT EXISTS migration_log (
            name TEXT PRIMARY KEY,
            ran_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            note TEXT
        )
    `);
    console.log('[DB] Schema ensured (credit_users, credit_history, migration_log)');
}

// One-shot migration from credits.json. Runs only if Postgres has zero users
// AND the migration has never run before AND credits.json exists with at
// least one user. Never deletes credits.json. Sets a marker so it can never
// re-run, even if credit_users becomes empty later (which would otherwise
// risk overwriting new real users with stale data).
const MIGRATION_NAME = 'credits_json_to_postgres_v1';
async function maybeMigrateFromJSON() {
    const { rows: markerRows } = await pool.query(
        'SELECT 1 FROM migration_log WHERE name = $1',
        [MIGRATION_NAME]
    );
    if (markerRows.length > 0) {
        console.log('[Migration] marker present → migration already ran, skip');
        return;
    }
    const { rows } = await pool.query('SELECT COUNT(*)::int AS c FROM credit_users');
    if ((rows[0] && rows[0].c) > 0) {
        // Postgres already has data → record the marker so we never try again.
        await pool.query(
            `INSERT INTO migration_log (name, note) VALUES ($1, $2)
             ON CONFLICT (name) DO NOTHING`,
            [MIGRATION_NAME, 'skipped: credit_users already populated at first boot']
        );
        console.log('[Migration] credit_users already populated → marker set, skip JSON migration');
        return;
    }
    if (!fs.existsSync(JSON_DB)) {
        // No JSON to import. Still record the marker so we don't keep checking.
        await pool.query(
            `INSERT INTO migration_log (name, note) VALUES ($1, $2)
             ON CONFLICT (name) DO NOTHING`,
            [MIGRATION_NAME, 'skipped: no credits.json on disk']
        );
        console.log('[Migration] no credits.json found → marker set, nothing to migrate');
        return;
    }
    let parsed;
    try {
        parsed = JSON.parse(fs.readFileSync(JSON_DB, 'utf8'));
    } catch (e) {
        console.error('[Migration] failed to parse credits.json:', e.message);
        return;
    }
    const users = parsed.users || {};
    const ids = Object.keys(users);
    if (ids.length === 0) {
        console.log('[Migration] credits.json is empty → nothing to migrate');
        return;
    }
    console.log(`[Migration] migrating ${ids.length} users from credits.json → credit_users`);
    let okUsers = 0, okHistory = 0;
    for (const id of ids) {
        const u = users[id];
        try {
            await pool.query(
                `INSERT INTO credit_users (discord_id, username, credits, total_purchased, referrer_id, referrer_granted, created_at, updated_at)
                 VALUES ($1, $2, $3, $4, $5, $6, COALESCE($7::timestamptz, NOW()), COALESCE($8::timestamptz, NOW()))
                 ON CONFLICT (discord_id) DO NOTHING`,
                [
                    id,
                    u.username || 'Unknown',
                    parseInt(u.credits) || 0,
                    parseInt(u.total_purchased) || 0,
                    u.referrer_id ? String(u.referrer_id) : null,
                    !!u.referrer_granted,
                    u.created_at || null,
                    u.updated_at || null,
                ]
            );
            okUsers++;
            for (const h of (u.history || [])) {
                if (!h || !h.amount) continue;
                await pool.query(
                    `INSERT INTO credit_history (discord_id, type, amount, pack_name, timestamp, stripe_session, payment_status)
                     VALUES ($1, $2, $3, $4, COALESCE($5::timestamptz, NOW()), $6, $7)`,
                    [id, h.type || null, parseInt(h.amount) || 0, h.pack_name || null, h.timestamp || null, h.stripe_session || null, h.payment_status || null]
                );
                okHistory++;
            }
        } catch (err) {
            console.error(`[Migration] failed to migrate user ${id}:`, err.message);
        }
    }
    // Record the marker so this migration can NEVER re-run, even if
    // credit_users is wiped or credits.json is altered later.
    await pool.query(
        `INSERT INTO migration_log (name, note) VALUES ($1, $2)
         ON CONFLICT (name) DO NOTHING`,
        [MIGRATION_NAME, `imported ${okUsers} users + ${okHistory} history rows from credits.json`]
    );
    console.log(`[Migration] DONE: ${okUsers} users + ${okHistory} history rows imported. credits.json kept on disk for safety. Marker set → will never re-run.`);
}

// ============================================
// Middleware
// ============================================
app.use(cors());
const jsonParser = express.json();
app.use((req, res, next) => {
    if (req.path === '/api/stripe-webhook') next();
    else jsonParser(req, res, next);
});

// ============================================
// DB helpers (Postgres)
// ============================================
async function getUserDB(discordId) {
    const { rows } = await pool.query(
        `SELECT discord_id, username, credits, total_purchased, referrer_id, referrer_granted, created_at, updated_at
         FROM credit_users WHERE discord_id = $1`,
        [String(discordId)]
    );
    return rows[0] || null;
}

async function ensureUserDB(discordId, username) {
    await pool.query(
        `INSERT INTO credit_users (discord_id, username) VALUES ($1, $2)
         ON CONFLICT (discord_id) DO UPDATE SET username = COALESCE(EXCLUDED.username, credit_users.username)`,
        [String(discordId), username || null]
    );
}

async function addCreditsDB({ discordId, username, amount, packName, stripeSession = null, paymentStatus = null, isPurchase = false }) {
    const idStr = String(discordId);
    // Upsert user, accumulate credits + total_purchased (only when buying), update username + updated_at.
    const { rows } = await pool.query(
        `INSERT INTO credit_users (discord_id, username, credits, total_purchased, updated_at)
         VALUES ($1, $2, $3, $4, NOW())
         ON CONFLICT (discord_id) DO UPDATE SET
             credits = credit_users.credits + EXCLUDED.credits,
             total_purchased = credit_users.total_purchased + EXCLUDED.total_purchased,
             username = COALESCE(EXCLUDED.username, credit_users.username),
             updated_at = NOW()
         RETURNING credits, total_purchased`,
        [idStr, username || null, amount, isPurchase && amount > 0 ? amount : 0]
    );
    await pool.query(
        `INSERT INTO credit_history (discord_id, type, amount, pack_name, stripe_session, payment_status)
         VALUES ($1, $2, $3, $4, $5, $6)`,
        [idStr, amount >= 0 ? 'add' : 'deduct', amount, packName || 'Credits', stripeSession, paymentStatus]
    );
    return rows[0]; // { credits, total_purchased }
}

async function setCreditsDB(discordId, newAmount, packName) {
    const idStr = String(discordId);
    const before = (await getUserDB(idStr))?.credits || 0;
    const delta = newAmount - before;
    await pool.query(
        `INSERT INTO credit_users (discord_id, credits, updated_at) VALUES ($1, $2, NOW())
         ON CONFLICT (discord_id) DO UPDATE SET credits = EXCLUDED.credits, updated_at = NOW()`,
        [idStr, newAmount]
    );
    await pool.query(
        `INSERT INTO credit_history (discord_id, type, amount, pack_name)
         VALUES ($1, $2, $3, $4)`,
        [idStr, delta >= 0 ? 'add' : 'deduct', delta, packName]
    );
    return { before, after: newAmount, delta };
}

async function setReferrerDB(referredId, referrerId) {
    const r = String(referredId);
    const ref = String(referrerId);
    await ensureUserDB(r, null);
    const { rows } = await pool.query(
        `UPDATE credit_users SET referrer_id = $2, referrer_granted = FALSE
         WHERE discord_id = $1 AND (referrer_id IS NULL)
         RETURNING discord_id`,
        [r, ref]
    );
    return rows.length > 0;
}

async function getReferralCountDB(referrerId) {
    const { rows } = await pool.query(
        `SELECT COUNT(*)::int AS c FROM credit_users WHERE referrer_id = $1`,
        [String(referrerId)]
    );
    return rows[0]?.c || 0;
}

// Returns { granted: bool, referrerId } — if granted, also adds the bonus to
// the referrer atomically.
async function maybeGrantReferralReward(referredId, packName) {
    const u = await getUserDB(referredId);
    if (!u || !u.referrer_id || u.referrer_granted) return { granted: false };
    if ((u.total_purchased || 0) < REFERRER_PURCHASE_THRESHOLD) return { granted: false };

    const referrerId = u.referrer_id;
    // Mark granted FIRST to prevent double-grant on concurrent webhooks.
    const { rows } = await pool.query(
        `UPDATE credit_users SET referrer_granted = TRUE WHERE discord_id = $1 AND referrer_granted = FALSE RETURNING discord_id`,
        [String(referredId)]
    );
    if (rows.length === 0) return { granted: false };
    // Credit the referrer.
    await addCreditsDB({
        discordId: referrerId,
        username: null,
        amount: REFERRER_PURCHASE_BONUS,
        packName: `Referral bonus (${referredId} bought ${packName})`,
        isPurchase: false,
    });
    return { granted: true, referrerId, amount: REFERRER_PURCHASE_BONUS };
}

// ============================================
// Discord helpers
// ============================================
async function verifyDiscordToken(token) {
    try {
        const res = await fetch('https://discord.com/api/users/@me', {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (res.ok) return await res.json();
    } catch (e) {
        console.error('[Auth] Token verification failed:', e.message);
    }
    return null;
}

async function sendDM(discordId, message) {
    if (!BOT_TOKEN) {
        console.log('[DM] No bot token set, skipping DM');
        return false;
    }
    try {
        const dmRes = await fetch('https://discord.com/api/users/@me/channels', {
            method: 'POST',
            headers: { 'Authorization': `Bot ${BOT_TOKEN}`, 'Content-Type': 'application/json' },
            body: JSON.stringify({ recipient_id: String(discordId) })
        });
        if (!dmRes.ok) {
            console.error('[DM] Failed to open DM channel:', await dmRes.text());
            return false;
        }
        const dmChannel = await dmRes.json();
        const msgRes = await fetch(`https://discord.com/api/channels/${dmChannel.id}/messages`, {
            method: 'POST',
            headers: { 'Authorization': `Bot ${BOT_TOKEN}`, 'Content-Type': 'application/json' },
            body: JSON.stringify({ content: message })
        });
        if (msgRes.ok) {
            console.log(`[DM] Sent message to ${discordId}`);
            return true;
        }
        console.error('[DM] Failed to send message:', await msgRes.text());
        return false;
    } catch (e) {
        console.error('[DM] Error sending DM:', e.message);
        return false;
    }
}

// ============================================
// Routes
// ============================================
app.get('/api/health', (req, res) => {
    res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

app.get('/api/credits', async (req, res) => {
    try {
        const discordId = req.query.discord_id;
        const authHeader = req.headers.authorization;
        if (discordId) {
            const u = await getUserDB(discordId);
            return res.json({
                discord_id: String(discordId),
                username: u ? u.username : 'Unknown',
                credits: u ? u.credits : 0,
            });
        }
        if (authHeader && authHeader.startsWith('Bearer ')) {
            const token = authHeader.substring(7);
            const user = await verifyDiscordToken(token);
            if (!user) return res.status(401).json({ error: 'Invalid token' });
            const u = await getUserDB(user.id);
            return res.json({
                discord_id: user.id,
                username: user.username,
                credits: u ? u.credits : 0,
            });
        }
        return res.status(400).json({ error: 'Missing discord_id or Authorization header' });
    } catch (e) {
        console.error('[api/credits] error:', e && e.stack || e);
        res.status(500).json({ error: 'internal', message: e.message });
    }
});

app.post('/api/credits/add', async (req, res) => {
    try {
        const authHeader = req.headers.authorization;
        let discordId, username;
        if (authHeader && authHeader.startsWith('Bearer ')) {
            const token = authHeader.substring(7);
            const user = await verifyDiscordToken(token);
            if (!user) return res.status(401).json({ error: 'Invalid token' });
            discordId = user.id; username = user.username;
        } else if (req.body.discord_id && req.body.secret) {
            if (req.body.secret !== process.env.API_SECRET) {
                return res.status(401).json({ error: 'Invalid secret', success: false });
            }
            discordId = req.body.discord_id;
            username = req.body.username || 'Unknown';
        } else {
            return res.status(401).json({ error: 'Unauthorized' });
        }

        const amount = parseInt(req.body.amount);
        if (isNaN(amount) || amount === 0) {
            return res.status(400).json({ error: 'Invalid amount' });
        }

        const result = await addCreditsDB({
            discordId,
            username,
            amount,
            packName: req.body.pack_name || 'Credits',
            isPurchase: false,
        });

        console.log(`[Credits] ${amount > 0 ? 'Added' : 'Deducted'} ${Math.abs(amount)} credits to ${discordId} (${username}). New balance: ${result.credits}`);

        if (amount > 0) {
            const msg = `Thank you! You have added **${amount} credits** (${req.body.pack_name || 'Credits'}). Your new balance is **${result.credits} credits**. Enjoy!`;
            sendDM(discordId, msg);
        }

        res.json({
            success: true,
            discord_id: String(discordId),
            username,
            amount_added: amount,
            pack_name: req.body.pack_name || 'Credits',
            new_balance: result.credits,
        });
    } catch (e) {
        console.error('[api/credits/add] error:', e && e.stack || e);
        res.status(500).json({ error: 'internal', message: e.message });
    }
});

app.post('/api/users/update', async (req, res) => {
    try {
        const authHeader = req.headers.authorization;
        if (!authHeader || !authHeader.startsWith('Bearer ')) {
            return res.status(401).json({ error: 'Missing token' });
        }
        const token = authHeader.substring(7);
        const user = await verifyDiscordToken(token);
        if (!user) return res.status(401).json({ error: 'Invalid token' });
        await ensureUserDB(user.id, user.username);
        res.json({ success: true, discord_id: user.id });
    } catch (e) {
        console.error('[api/users/update] error:', e && e.stack || e);
        res.status(500).json({ error: 'internal', message: e.message });
    }
});

app.get('/api/user/dashboard', async (req, res) => {
    try {
        const authHeader = req.headers.authorization;
        let discordId, username;
        if (authHeader && authHeader.startsWith('Bearer ')) {
            const token = authHeader.substring(7);
            const u = await verifyDiscordToken(token);
            if (!u) return res.status(401).json({ error: 'Invalid token' });
            discordId = u.id; username = u.username;
        } else if (req.query.discord_id) {
            discordId = String(req.query.discord_id);
        } else {
            return res.status(400).json({ error: 'Missing auth or discord_id' });
        }

        const isAdmin = ADMIN_USER_IDS.has(String(discordId));
        // sub_type lives in the bot's `profiles` table (same Postgres DB).
        // We swallow errors — the dashboard must still render if the bot's
        // schema isn't ready yet.
        let subType = 'free';
        try {
            const numericId = String(discordId).match(/^\d+$/) ? discordId : null;
            if (numericId) {
                const { rows: profRows } = await pool.query(
                    `SELECT sub_type FROM profiles WHERE user_id = $1::bigint LIMIT 1`,
                    [String(numericId)]
                );
                if (profRows[0] && profRows[0].sub_type) {
                    subType = String(profRows[0].sub_type).toLowerCase();
                }
            }
        } catch (e) {
            // Bot table may not exist on a fresh DB yet — ignore.
        }

        const user = await getUserDB(discordId);
        if (!user) {
            return res.json({
                discord_id: String(discordId),
                username: username || 'Unknown',
                credits: 0,
                total_purchased: 0,
                history: [],
                referral_count: 0,
                referrer_granted: false,
                sub_type: subType,
                is_admin: isAdmin,
            });
        }
        const { rows: hist } = await pool.query(
            `SELECT type, amount, pack_name, timestamp, stripe_session, payment_status
             FROM credit_history
             WHERE discord_id = $1 AND amount IS NOT NULL AND amount <> 0
             ORDER BY timestamp DESC LIMIT 8`,
            [String(discordId)]
        );
        const referralCount = await getReferralCountDB(discordId);

        res.json({
            discord_id: String(discordId),
            username: user.username || username || 'Unknown',
            credits: user.credits || 0,
            total_purchased: user.total_purchased || 0,
            history: hist,
            referral_count: referralCount,
            referrer_granted: !!user.referrer_granted,
            sub_type: subType,
            is_admin: isAdmin,
        });
    } catch (e) {
        console.error('[api/user/dashboard] error:', e && e.stack || e);
        res.status(500).json({ error: 'internal', message: e.message });
    }
});

app.get('/api/leaderboard', async (req, res) => {
    try {
        const { rows } = await pool.query(
            `SELECT discord_id, username, credits FROM credit_users ORDER BY credits DESC LIMIT 10`
        );
        res.json(rows);
    } catch (e) {
        console.error('[api/leaderboard] error:', e && e.stack || e);
        res.status(500).json({ error: 'internal', message: e.message });
    }
});

// ============================================
// Referral
// ============================================
app.post('/api/referrals/set', async (req, res) => {
    try {
        if (!req.body.secret || req.body.secret !== process.env.API_SECRET) {
            return res.status(401).json({ error: 'Invalid secret' });
        }
        const { referred_id, referrer_id } = req.body;
        if (!referred_id || !referrer_id || String(referred_id) === String(referrer_id)) {
            return res.status(400).json({ error: 'Invalid ids' });
        }
        const ok = await setReferrerDB(referred_id, referrer_id);
        if (!ok) return res.json({ success: false, error: 'Already has a referrer' });
        console.log(`[Referral] ${referred_id} linked to referrer ${referrer_id}`);
        res.json({ success: true });
    } catch (e) {
        console.error('[api/referrals/set] error:', e && e.stack || e);
        res.status(500).json({ error: 'internal', message: e.message });
    }
});

// ============================================
// Admin
// ============================================
async function requireAdmin(req, res) {
    const authHeader = req.headers.authorization;
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
        res.status(401).json({ error: 'Missing token' });
        return null;
    }
    const token = authHeader.substring(7);
    const user = await verifyDiscordToken(token);
    if (!user) {
        res.status(401).json({ error: 'Invalid token' });
        return null;
    }
    if (!ADMIN_USER_IDS.has(String(user.id))) {
        res.status(403).json({ error: 'Forbidden' });
        return null;
    }
    return user;
}

app.get('/api/admin/users', async (req, res) => {
    try {
        const admin = await requireAdmin(req, res);
        if (!admin) return;
        const page = Math.max(1, parseInt(req.query.page) || 1);
        const limit = Math.max(1, Math.min(100, parseInt(req.query.limit) || 20));
        const q = (req.query.q || '').toString().trim();

        const params = [];
        let where = '';
        if (q) {
            params.push('%' + q.toLowerCase() + '%');
            where = `WHERE LOWER(discord_id) LIKE $1 OR LOWER(COALESCE(username, '')) LIKE $1`;
        }
        const countQ = `SELECT COUNT(*)::int AS c FROM credit_users ${where}`;
        const { rows: countRows } = await pool.query(countQ, params);
        const total = countRows[0]?.c || 0;

        const offset = (page - 1) * limit;
        const listQ = `
            SELECT discord_id, username, credits, total_purchased, referrer_id, updated_at
            FROM credit_users
            ${where}
            ORDER BY updated_at DESC NULLS LAST
            LIMIT ${limit} OFFSET ${offset}
        `;
        const { rows } = await pool.query(listQ, params);

        res.json({
            page,
            limit,
            total,
            total_pages: Math.max(1, Math.ceil(total / limit)),
            users: rows,
        });
    } catch (e) {
        console.error('[admin/users] error:', e && e.stack || e);
        res.status(500).json({ error: 'internal', message: e.message });
    }
});

app.get('/api/admin/user/:id', async (req, res) => {
    try {
        const admin = await requireAdmin(req, res);
        if (!admin) return;
        const id = String(req.params.id);
        const u = await getUserDB(id);
        if (!u) return res.status(404).json({ error: 'User not found' });
        const { rows: hist } = await pool.query(
            `SELECT type, amount, pack_name, timestamp, stripe_session, payment_status
             FROM credit_history WHERE discord_id = $1
             ORDER BY timestamp DESC LIMIT 50`,
            [id]
        );
        res.json({
            discord_id: id,
            username: u.username || 'Unknown',
            credits: u.credits || 0,
            total_purchased: u.total_purchased || 0,
            referrer_id: u.referrer_id || null,
            referrer_granted: !!u.referrer_granted,
            created_at: u.created_at || null,
            updated_at: u.updated_at || null,
            history: hist,
        });
    } catch (e) {
        console.error('[admin/user/:id] error:', e && e.stack || e);
        res.status(500).json({ error: 'internal', message: e.message });
    }
});

app.post('/api/admin/credits/set', async (req, res) => {
    try {
        const admin = await requireAdmin(req, res);
        if (!admin) return;
        const targetId = String(req.body.discord_id || '');
        const newAmount = parseInt(req.body.amount);
        if (!/^\d+$/.test(targetId)) {
            return res.status(400).json({ error: 'Invalid discord_id' });
        }
        if (isNaN(newAmount) || newAmount < 0) {
            return res.status(400).json({ error: 'Invalid amount (must be non-negative integer)' });
        }
        const result = await setCreditsDB(targetId, newAmount, `Admin set (${admin.username || admin.id})`);
        console.log(`[ADMIN] ${admin.username} (${admin.id}) set credits of ${targetId} to ${newAmount} (was ${result.before})`);

        // DM the target so they know an admin touched their balance.
        if (result.delta !== 0) {
            const verb = result.delta > 0 ? 'added to' : 'removed from';
            const msg = `🛠️ An admin ${verb} your KlaraAI balance: **${result.delta > 0 ? '+' : ''}${result.delta} credits**. Your new balance is **${result.after} credits**.`;
            sendDM(targetId, msg);
        }

        res.json({
            success: true,
            discord_id: targetId,
            before: result.before,
            after: result.after,
            delta: result.delta,
        });
    } catch (e) {
        console.error('[admin/credits/set] error:', e && e.stack || e);
        res.status(500).json({ error: 'internal', message: e.message });
    }
});

app.post('/api/admin/credits/grant-self', async (req, res) => {
    try {
        const admin = await requireAdmin(req, res);
        if (!admin) return;
        const amount = parseInt(req.body.amount);
        if (isNaN(amount) || amount === 0) {
            return res.status(400).json({ error: 'Invalid amount' });
        }
        const targetId = String(admin.id);
        const result = await addCreditsDB({
            discordId: targetId,
            username: admin.username,
            amount,
            packName: 'Admin self-grant',
            isPurchase: false,
        });
        console.log(`[ADMIN SELF-GRANT] ${admin.username} (${admin.id}) ${amount > 0 ? '+' : ''}${amount} (new balance: ${result.credits})`);

        // DM the admin (= self) so they get a Discord notification of the action.
        const verb = amount > 0 ? 'added' : 'removed';
        const sign = amount > 0 ? '+' : '';
        const msg = `🛠️ **Admin self-grant** — you ${verb} **${sign}${amount} credits** to your own balance.\nNew balance: **${result.credits} credits**.`;
        sendDM(targetId, msg);

        res.json({
            success: true,
            new_balance: result.credits,
        });
    } catch (e) {
        console.error('[admin/credits/grant-self] error:', e && e.stack || e);
        res.status(500).json({ error: 'internal', message: e.message });
    }
});

// ============================================
// Stripe
// ============================================
app.post('/api/create-checkout', async (req, res) => {
    try {
        const authHeader = req.headers.authorization;
        if (!authHeader || !authHeader.startsWith('Bearer ')) {
            return res.status(401).json({ error: 'Missing token' });
        }
        const token = authHeader.substring(7);
        const user = await verifyDiscordToken(token);
        if (!user) return res.status(401).json({ error: 'Invalid token' });

        const { pack_name } = req.body;
        if (!pack_name || !CREDIT_PACKS[pack_name]) {
            return res.status(400).json({ error: 'Invalid pack name' });
        }
        const pack = CREDIT_PACKS[pack_name];
        const credits = pack.credits;
        const priceInCents = pack.price_usd;

        const session = await stripe.checkout.sessions.create({
            payment_method_types: ['card'],
            line_items: [{
                price_data: {
                    currency: 'usd',
                    product_data: {
                        name: `KlaraAI - ${pack_name} Pack (${credits} credits)`,
                        description: `${credits} credits for KlaraAI Discord Bot`,
                        images: ['https://www.klaraai.me/img/logo.png'],
                    },
                    unit_amount: priceInCents,
                },
                quantity: 1,
            }],
            mode: 'payment',
            success_url: `${req.headers.origin || 'https://www.klaraai.me'}/buy-credits?success=true&credits=${credits}`,
            cancel_url: `${req.headers.origin || 'https://www.klaraai.me'}/buy-credits?canceled=true`,
            metadata: {
                discord_id: user.id,
                username: user.username,
                pack_name: pack_name,
                credits: credits.toString(),
            },
            client_reference_id: user.id,
        });

        console.log(`[Stripe] Created checkout session ${session.id} for ${user.username} (${user.id}) - ${credits} credits`);
        res.json({ url: session.url, session_id: session.id });
    } catch (error) {
        console.error('[Stripe] Checkout error:', error.message);
        res.status(500).json({ error: 'Failed to create checkout session', details: error.message });
    }
});

app.post('/api/stripe-webhook', express.raw({ type: 'application/json' }), async (req, res) => {
    const sig = req.headers['stripe-signature'];
    const webhookSecret = process.env.STRIPE_WEBHOOK_SECRET || '';
    let event;
    try {
        if (webhookSecret) {
            event = stripe.webhooks.constructEvent(req.body, sig, webhookSecret);
        } else {
            event = JSON.parse(req.body.toString());
        }
    } catch (err) {
        console.error(`[Stripe] Webhook signature verification failed:`, err.message);
        return res.status(400).send(`Webhook Error: ${err.message}`);
    }

    if (event.type === 'checkout.session.completed') {
        const session = event.data.object;
        const discordId = session.metadata?.discord_id;
        const username = session.metadata?.username;
        const packName = session.metadata?.pack_name;
        const credits = parseInt(session.metadata?.credits);

        if (!discordId || !credits) {
            console.error('[Stripe] Missing metadata in session:', session.id);
            return res.json({ received: true });
        }

        try {
            const result = await addCreditsDB({
                discordId,
                username,
                amount: credits,
                packName: packName || 'Credits',
                stripeSession: session.id,
                paymentStatus: session.payment_status,
                isPurchase: true,
            });
            console.log(`[Stripe] Added ${credits} credits to ${discordId} (${username}) - Session: ${session.id}`);

            const thankYouMsg = `Thank you for your purchase! You have added **${credits} credits** (${packName} Pack). Your new balance is **${result.credits} credits**. Enjoy!`;
            sendDM(discordId, thankYouMsg);

            const referralPayout = await maybeGrantReferralReward(discordId, packName);
            if (referralPayout.granted) {
                console.log(`[Referral] Granted ${referralPayout.amount} credits to referrer ${referralPayout.referrerId}`);
                const refMsg = `🎁 **Referral reward!** A friend you invited just made their first purchase. You earned **+${referralPayout.amount} credits**. Enjoy!`;
                sendDM(referralPayout.referrerId, refMsg);
            }
        } catch (e) {
            console.error('[Stripe webhook] processing failed:', e && e.stack || e);
        }
    }

    res.json({ received: true });
});

// ============================================
// Global error handler
// ============================================
app.use((err, req, res, next) => {
    console.error('[GlobalError]', req.method, req.path, '-', err && err.stack || err);
    if (res.headersSent) return next(err);
    res.status(500).json({ error: 'internal', message: err && err.message });
});
process.on('unhandledRejection', (reason) => console.error('[unhandledRejection]', reason));
process.on('uncaughtException', (err) => console.error('[uncaughtException]', err && err.stack || err));

// ============================================
// Start
// ============================================
(async function start() {
    try {
        await initSchema();
        await maybeMigrateFromJSON();
    } catch (e) {
        console.error('[FATAL] DB init failed:', e && e.stack || e);
        process.exit(1);
    }
    app.listen(PORT, () => {
        console.log(`[Server] KlaraAI Credits API running on http://localhost:${PORT}`);
        console.log(`[DB] Postgres-backed (DATABASE_URL ${process.env.DATABASE_URL ? 'set' : 'MISSING'})`);
        console.log(`[DM] Bot token ${BOT_TOKEN ? 'configured' : 'NOT configured - DMs will not be sent'}`);
        console.log(`[Stripe] Secret key ${process.env.STRIPE_SECRET_KEY ? 'configured (' + (process.env.STRIPE_SECRET_KEY.startsWith('sk_live_') ? 'LIVE' : process.env.STRIPE_SECRET_KEY.startsWith('sk_test_') ? 'TEST' : 'unknown') + ')' : 'NOT configured'}`);
        console.log(`[Stripe] Webhook secret ${process.env.STRIPE_WEBHOOK_SECRET ? 'configured' : 'NOT configured'}`);
        console.log(`[API_SECRET] ${process.env.API_SECRET ? 'configured' : 'NOT configured'}`);
    });
})();
