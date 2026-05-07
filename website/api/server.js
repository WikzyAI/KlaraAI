// ============================================
// KlaraAI Credits API Server
// ============================================

require('dotenv').config();
const express = require('express');
const cors = require('cors');
const path = require('path');
const fs = require('fs');
const stripe = require('stripe')(process.env.STRIPE_SECRET_KEY || 'sk_test_YOUR_STRIPE_SECRET_KEY');

// Verify Stripe config on startup
console.log('[Stripe] Configured:', process.env.STRIPE_SECRET_KEY ? 'YES' : 'NO (using test key)');

const app = express();
const PORT = process.env.PORT || 3000;
const JSON_DB = path.join(__dirname, 'credits.json');
const BOT_TOKEN = process.env.DISCORD_TOKEN || process.env.DISCORD_BOT_TOKEN || '';

// Credit pack definitions (price in cents USD)
const CREDIT_PACKS = {
    'Starter': { credits: 100, price_usd: 100 },      // $1
    'Popular': { credits: 500, price_usd: 500 },      // $5
    'Pro': { credits: 1000, price_usd: 1000 },        // $10
    'Elite': { credits: 5000, price_usd: 5000 },      // $50
    'Standard': { credits: 1600, price_usd: 1600 },   // $16 (1 month sub)
    'Premium': { credits: 3200, price_usd: 3200 }    // $32 (1 month sub)
};

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

// JSON parser for all routes except Stripe webhook
const jsonParser = express.json();
app.use((req, res, next) => {
    if (req.path === '/api/stripe-webhook') {
        next();
    } else {
        jsonParser(req, res, next);
    }
});

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

// Get full user dashboard: balance, total purchased, recent history
app.get('/api/user/dashboard', async (req, res) => {
    const authHeader = req.headers.authorization;
    let discordId, username;

    if (authHeader && authHeader.startsWith('Bearer ')) {
        const token = authHeader.substring(7);
        const u = await verifyDiscordToken(token);
        if (!u) return res.status(401).json({ error: 'Invalid token' });
        discordId = u.id;
        username = u.username;
    } else if (req.query.discord_id) {
        discordId = String(req.query.discord_id);
    } else {
        return res.status(400).json({ error: 'Missing auth or discord_id' });
    }

    const data = readJSONDB();
    const user = data.users[discordId];
    if (!user) {
        return res.json({
            discord_id: discordId,
            username: username || 'Unknown',
            credits: 0,
            total_purchased: 0,
            history: [],
            referral_count: 0,
            referrer_granted: false
        });
    }
    const history = (user.history || [])
        .filter(h => h && h.amount)
        .slice(-8)
        .reverse();
    const referralCount = Object.values(data.users)
        .filter(u => String(u.referrer_id) === String(discordId)).length;

    res.json({
        discord_id: discordId,
        username: user.username || username || 'Unknown',
        credits: user.credits || 0,
        total_purchased: user.total_purchased || 0,
        history,
        referral_count: referralCount,
        referrer_granted: !!user.referrer_granted
    });
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
// Referral system (signup -> first-purchase reward)
// ============================================
const REFERRER_PURCHASE_BONUS = 200;        // credits given to the referrer
const REFERRER_PURCHASE_THRESHOLD = 500;    // referee must spend >= this many credits ($5)

// Bot calls this when a user applies a referral code, so the webhook can later
// detect the converting purchase without needing Postgres access.
app.post('/api/referrals/set', (req, res) => {
    if (!req.body.secret || req.body.secret !== process.env.API_SECRET) {
        return res.status(401).json({ error: 'Invalid secret' });
    }
    const { referred_id, referrer_id } = req.body;
    if (!referred_id || !referrer_id || String(referred_id) === String(referrer_id)) {
        return res.status(400).json({ error: 'Invalid ids' });
    }
    const data = readJSONDB();
    if (!data.users[referred_id]) {
        data.users[referred_id] = {
            credits: 0, history: [], created_at: new Date().toISOString()
        };
    }
    if (data.users[referred_id].referrer_id) {
        return res.json({ success: false, error: 'Already has a referrer' });
    }
    data.users[referred_id].referrer_id = String(referrer_id);
    data.users[referred_id].referrer_granted = false;
    data.users[referred_id].total_purchased = data.users[referred_id].total_purchased || 0;
    writeJSONDB(data);
    console.log(`[Referral] ${referred_id} linked to referrer ${referrer_id}`);
    res.json({ success: true });
});

function maybeGrantReferralReward(data, referredId, packName) {
    const user = data.users[referredId];
    if (!user || !user.referrer_id || user.referrer_granted) return null;
    if ((user.total_purchased || 0) < REFERRER_PURCHASE_THRESHOLD) return null;

    const referrerId = user.referrer_id;
    if (!data.users[referrerId]) {
        data.users[referrerId] = {
            credits: 0, history: [], created_at: new Date().toISOString()
        };
    }
    data.users[referrerId].credits += REFERRER_PURCHASE_BONUS;
    data.users[referrerId].history = data.users[referrerId].history || [];
    data.users[referrerId].history.push({
        type: 'add',
        amount: REFERRER_PURCHASE_BONUS,
        pack_name: `Referral bonus (${referredId} bought ${packName})`,
        timestamp: new Date().toISOString()
    });
    user.referrer_granted = true;
    return { referrerId, amount: REFERRER_PURCHASE_BONUS };
}

// ============================================
// Stripe Payment Routes
// ============================================

// Create Stripe Checkout Session
app.post('/api/create-checkout', async (req, res) => {
    const authHeader = req.headers.authorization;
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
        return res.status(401).json({ error: 'Missing token' });
    }

    const token = authHeader.substring(7);
    const user = await verifyDiscordToken(token);
    if (!user) {
        return res.status(401).json({ error: 'Invalid token' });
    }

    const { pack_name, amount, price_usd } = req.body;

    if (!pack_name || !CREDIT_PACKS[pack_name]) {
        return res.status(400).json({ error: 'Invalid pack name' });
    }

    const pack = CREDIT_PACKS[pack_name];
    const credits = pack.credits;
    const priceInCents = pack.price_usd;

    try {
        const session = await stripe.checkout.sessions.create({
            payment_method_types: ['card'],
            line_items: [{
                price_data: {
                    currency: 'usd',
                    product_data: {
                        name: `KlaraAI - ${pack_name} Pack (${credits} credits)`,
                        description: `${credits} credits for KlaraAI Discord Bot`,
                        images: ['https://klaraai.vercel.app/img/logo.png'],
                    },
                    unit_amount: priceInCents,
                },
                quantity: 1,
            }],
            mode: 'payment',
            success_url: `${req.headers.origin || 'https://klaraai.vercel.app'}/buy-credits.html?success=true&credits=${credits}`,
            cancel_url: `${req.headers.origin || 'https://klaraai.vercel.app'}/buy-credits.html?canceled=true`,
            metadata: {
                discord_id: user.id,
                username: user.username,
                pack_name: pack_name,
                credits: credits.toString()
            },
            client_reference_id: user.id
        });

        console.log(`[Stripe] Created checkout session ${session.id} for ${user.username} (${user.id}) - ${credits} credits`);
        res.json({ url: session.url, session_id: session.id });
    } catch (error) {
        console.error('[Stripe] Checkout error:', error.message);
        res.status(500).json({ error: 'Failed to create checkout session', details: error.message });
    }
});

// Stripe Webhook - Handle successful payments
app.post('/api/stripe-webhook', express.raw({ type: 'application/json' }), async (req, res) => {
    const sig = req.headers['stripe-signature'];
    const webhookSecret = process.env.STRIPE_WEBHOOK_SECRET || '';

    let event;

    try {
        if (webhookSecret) {
            event = stripe.webhooks.constructEvent(req.body, sig, webhookSecret);
        } else {
            // For testing without webhook secret
            event = JSON.parse(req.body.toString());
        }
    } catch (err) {
        console.error(`[Stripe] Webhook signature verification failed:`, err.message);
        return res.status(400).send(`Webhook Error: ${err.message}`);
    }

    // Handle the checkout.session.completed event
    if (event.type === 'checkout.session.completed') {
        const session = event.data.object;

        const discordId = session.metadata.discord_id;
        const username = session.metadata.username;
        const packName = session.metadata.pack_name;
        const credits = parseInt(session.metadata.credits);

        if (!discordId || !credits) {
            console.error('[Stripe] Missing metadata in session:', session.id);
            return res.json({ received: true });
        }

        // Add credits to user
        const data = readJSONDB();
        if (!data.users[discordId]) {
            data.users[discordId] = {
                credits: 0,
                username: username,
                history: [],
                created_at: new Date().toISOString()
            };
        }

        data.users[discordId].credits += credits;
        data.users[discordId].username = username;
        data.users[discordId].total_purchased = (data.users[discordId].total_purchased || 0) + credits;
        data.users[discordId].history = data.users[discordId].history || [];
        data.users[discordId].history.push({
            type: 'add',
            amount: credits,
            pack_name: packName,
            timestamp: new Date().toISOString(),
            stripe_session: session.id,
            payment_status: session.payment_status
        });
        data.users[discordId].updated_at = new Date().toISOString();

        // If this user was referred and just hit the spending threshold, reward the referrer.
        const referralPayout = maybeGrantReferralReward(data, discordId, packName);

        writeJSONDB(data);

        console.log(`[Stripe] Added ${credits} credits to ${discordId} (${username}) - Session: ${session.id}`);

        // Send DM notification
        const thankYouMsg = `Thank you for your purchase! You have added **${credits} credits** (${packName} Pack). Your new balance is **${data.users[discordId].credits} credits**. Enjoy!`;
        sendDM(discordId, thankYouMsg);

        if (referralPayout) {
            console.log(`[Referral] Granted ${referralPayout.amount} credits to referrer ${referralPayout.referrerId} (referee ${discordId} converted)`);
            const refMsg = `🎁 **Referral reward!** A friend you invited just made their first purchase. You earned **+${referralPayout.amount} credits**. Enjoy!`;
            sendDM(referralPayout.referrerId, refMsg);
        }
    }

    res.json({ received: true });
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
