// ============================================
// KlaraAI Credits API Server
// ============================================

require('dotenv').config();
const express = require('express');
const cors = require('cors');
const path = require('path');
const fs = require('fs');

const app = express();
const PORT = process.env.PORT || 3000;
const JSON_DB = path.join(__dirname, 'credits.json');
const BOT_TOKEN = process.env.DISCORD_TOKEN || process.env.DISCORD_BOT_TOKEN || '';

console.log('[Server] Bot token configured:', BOT_TOKEN ? 'YES' : 'NO');

// Test bot token on startup
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

// Middleware
app.use(cors());
app.use(express.json());

// ============================================
// Database (JSON file storage)
// ============================================

function initJSONDB() {
    if (!fs.existsSync(JSON_DB)) {
        fs.writeFileSync(JSON_DB, JSON.stringify({ users: {} }, null, 2));
        console.log('[DB] Created new credits.json');
    }
}

function readJSONDB() {
    try {
        return JSON.parse(fs.readFileSync(JSON_DB, 'utf8'));
    } catch (e) {
        console.error('[DB] Error reading JSON:', e.message);
        return { users: {} };
    }
}

function writeJSONDB(data) {
    try {
        fs.writeFileSync(JSON_DB, JSON.stringify(data, null, 2));
    } catch (e) {
        console.error('[DB] Error writing JSON:', e.message);
    }
}

// ============================================
// Helpers
// ============================================

async function verifyDiscordToken(token) {
    try {
        const res = await fetch('https://discord.com/api/users/@me', {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (res.ok) {
            return await res.json();
        }
    } catch (e) {
        console.error('[Auth] Token verification failed:', e.message);
    }
    return null;
}

function getUserFromDB(discordId) {
    const data = readJSONDB();
    return data.users[discordId] || null;
}

// Send DM via bot
async function sendDM(discordId, message) {
    if (!BOT_TOKEN) {
        console.log('[DM] No bot token set, skipping DM');
        return false;
    }
    try {
        // Open DM channel
        const dmRes = await fetch('https://discord.com/api/users/@me/channels', {
            method: 'POST',
            headers: {
                'Authorization': `Bot ${BOT_TOKEN}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ recipient_id: discordId })
        });
        if (!dmRes.ok) {
            console.error('[DM] Failed to open DM channel:', await dmRes.text());
            return false;
        }
        const dmChannel = await dmRes.json();
        // Send message
        const msgRes = await fetch(`https://discord.com/api/channels/${dmChannel.id}/messages`, {
            method: 'POST',
            headers: {
                'Authorization': `Bot ${BOT_TOKEN}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ content: message })
        });
        if (msgRes.ok) {
            console.log(`[DM] Sent message to ${discordId}`);
            return true;
        } else {
            console.error('[DM] Failed to send message:', await msgRes.text());
            return false;
        }
    } catch (e) {
        console.error('[DM] Error sending DM:', e.message);
        return false;
    }
}

// ============================================
// Routes
// ============================================

// Health check
app.get('/api/health', (req, res) => {
    res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

// Get user credits
app.get('/api/credits', async (req, res) => {
    const discordId = req.query.discord_id;
    const authHeader = req.headers.authorization;

    if (discordId) {
        const user = getUserFromDB(discordId);
        return res.json({
            discord_id: discordId,
            username: user ? user.username : 'Unknown',
            credits: user ? user.credits : 0
        });
    }

    if (authHeader && authHeader.startsWith('Bearer ')) {
        const token = authHeader.substring(7);
        const user = await verifyDiscordToken(token);
        if (!user) {
            return res.status(401).json({ error: 'Invalid token' });
        }
        const dbUser = getUserFromDB(user.id);
        return res.json({
            discord_id: user.id,
            username: user.username,
            credits: dbUser ? dbUser.credits : 0
        });
    }

    return res.status(400).json({ error: 'Missing discord_id or Authorization header' });
});

// Add/Deduct credits (called by website after purchase, or by bot for deductions)
app.post('/api/credits/add', async (req, res) => {
    const authHeader = req.headers.authorization;

    let discordId, username;

    if (authHeader && authHeader.startsWith('Bearer ')) {
        const token = authHeader.substring(7);
        const user = await verifyDiscordToken(token);
        if (!user) {
            return res.status(401).json({ error: 'Invalid token' });
        }
        discordId = user.id;
        username = user.username;
    } else if (req.body.discord_id && req.body.secret) {
        if (req.body.secret === process.env.API_SECRET) {
            discordId = req.body.discord_id;
            username = req.body.username || 'Unknown';
        } else {
            console.error(`[API] Invalid secret provided. Expected: ${process.env.API_SECRET ? 'SET' : 'NOT SET'}, Got: ${req.body.secret ? 'provided' : 'empty'}`);
            return res.status(401).json({ error: 'Invalid secret', success: false });
        }
    } else {
        return res.status(401).json({ error: 'Unauthorized' });
    }

    const amount = parseInt(req.body.amount);
    if (isNaN(amount) || amount === 0) {
        return res.status(400).json({ error: 'Invalid amount' });
    }

    const data = readJSONDB();
    if (!data.users[discordId]) {
        data.users[discordId] = {
            credits: 0,
            username: username,
            history: [],
            created_at: new Date().toISOString()
        };
    }

    data.users[discordId].credits += amount;
    data.users[discordId].username = username;
    data.users[discordId].history = data.users[discordId].history || [];
    data.users[discordId].history.push({
        type: amount > 0 ? 'add' : 'deduct',
        amount: amount,
        pack_name: req.body.pack_name || 'Credits',
        timestamp: new Date().toISOString()
    });
    data.users[discordId].updated_at = new Date().toISOString();

    writeJSONDB(data);

    console.log(`[Credits] ${amount > 0 ? 'Added' : 'Deducted'} ${Math.abs(amount)} credits to ${discordId} (${username}). New balance: ${data.users[discordId].credits}`);

    // Send DM for purchases (positive amounts only)
    if (amount > 0) {
        const thankYouMsg = `Thank you for your purchase! You have added **${amount} credits** (${req.body.pack_name || 'Credits'}). Your new balance is **${data.users[discordId].credits} credits**. Enjoy!`;
        sendDM(discordId, thankYouMsg);
    }

    res.json({
        success: true,
        discord_id: discordId,
        username: username,
        amount_added: amount,
        pack_name: req.body.pack_name || 'Credits',
        new_balance: data.users[discordId].credits
    });
});

// Update user info (called when user logs in)
app.post('/api/users/update', async (req, res) => {
    const authHeader = req.headers.authorization;
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
        return res.status(401).json({ error: 'Missing token' });
    }

    const token = authHeader.substring(7);
    const user = await verifyDiscordToken(token);
    if (!user) {
        return res.status(401).json({ error: 'Invalid token' });
    }

    const data = readJSONDB();
    if (!data.users[user.id]) {
        data.users[user.id] = {
            credits: 0,
            username: user.username,
            discriminator: user.discriminator,
            avatar: user.avatar,
            history: [],
            created_at: new Date().toISOString()
        };
    } else {
        if (data.users[user.id].username !== user.username) {
            data.users[user.id].username = user.username;
        }
    }
    writeJSONDB(data);

    res.json({ success: true, discord_id: user.id });
});

// Get leaderboard
app.get('/api/leaderboard', (req, res) => {
    const data = readJSONDB();
    const users = Object.entries(data.users)
        .map(([id, u]) => ({ discord_id: id, username: u.username, credits: u.credits }))
        .sort((a, b) => b.credits - a.credits)
        .slice(0, 10);
    res.json(users);
});

// ============================================
// Start Server
// ============================================
initJSONDB();

app.listen(PORT, () => {
    console.log(`[Server] KlaraAI Credits API running on http://localhost:${PORT}`);
    console.log(`[DB] Using JSON storage at ${JSON_DB}`);
    console.log(`[DM] Bot token ${BOT_TOKEN ? 'configured' : 'NOT configured - DMs will not be sent'}`);
});
