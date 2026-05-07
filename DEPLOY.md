# 🚀 Deploying the KlaraAI Discord bot — 24/7, free

This guide deploys the bot to **Render's free tier** so it stays online
even when your computer is off, without paying anything.

> **Time:** ~15 minutes the first time.
> **Cost:** $0 / month with the free tier (limits: 750 hours of compute
> per month — enough for one always-on bot — and the service may suspend
> after 15 min of HTTP inactivity, so we use a tiny ping trick to keep
> it awake).

---

## 1. What's already in the repo

You don't need to write anything new — the work is already done:

| File | What it does |
|------|--------------|
| `erp-bot/utils/keep_alive.py` | Tiny HTTP server (`/ping`, `/health`) so an external monitor can keep the Render free service awake |
| `erp-bot/main.py` | Auto-starts the HTTP server when the `$PORT` env var is set (Render sets it automatically) |
| `erp-bot/render.yaml` | Render Blueprint that wires up Python, the start command, env vars, and a `/ping` health check |

---

## 2. Deploy to Render (the bot itself)

1. Go to https://render.com → log in (you already have an account).
2. **New +** → **Web Service**.
3. Pick the repo `WikzyAI/KlaraAI` (Render reads `render.yaml` automatically).
4. Render will detect the bot service. Verify the fields:
   - **Root directory:** `erp-bot`
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `python main.py`
   - **Plan:** Free
5. Click **Environment** tab and add the secrets the bot needs:
   - `DISCORD_TOKEN` — from the Dev Portal
   - `GROQ_API_KEY` — from console.groq.com
   - `OPENROUTER_API_KEY` — from openrouter.ai (the new one you just generated)
   - `DATABASE_URL` — already in your existing API service, copy/paste
   - `API_BASE` — `https://klaraai.onrender.com` (your existing API URL)
   - `API_SECRET` — same value as in the API service
6. Click **Create Web Service**. First deploy takes ~5 minutes.

When the deploy finishes you'll get a URL like:
`https://klaraai-bot.onrender.com`

Open it in your browser — you should see:
```
✦ KlaraAI Discord bot is alive ✦
Endpoints: /ping  /health
```

The bot is now running on Render. Your PC is no longer involved.

---

## 3. Stop the service from sleeping (UptimeRobot — free)

Render's free tier suspends a service after **15 minutes** without any
HTTP traffic. We work around that by pinging `/ping` every 5 minutes
from an external monitor.

1. Go to https://uptimerobot.com → free signup.
2. **+ New monitor**.
3. Settings:
   - **Type:** HTTP(s)
   - **Friendly Name:** `KlaraAI bot keepalive`
   - **URL:** `https://klaraai-bot.onrender.com/ping`
   - **Monitoring interval:** every **5 minutes**
4. Save.

That's it. UptimeRobot will hit `/ping` every 5 minutes, the bot stays
awake forever. Bonus: if Render does crash, you'll get an email alert.

---

## 4. (Optional) Local development

When you run the bot locally with `python main.py`, the `$PORT` env var
is **not** set, so the keep-alive HTTP server stays disabled. You don't
need to touch anything; local behavior is exactly what it was before.

If for some reason you *want* to start the keep-alive locally (e.g. to
test it), set `KEEP_ALIVE=1` in your `.env`:
```
KEEP_ALIVE=1
PORT=8080
```

---

## 5. Things to know about the free tier

| Limit | Value | What it means for the bot |
|-------|-------|--------------------------|
| Compute hours | 750 / month | One service running 24/7 = 720h, fits |
| Memory | 512 MB | Plenty for this bot |
| Bandwidth | 100 GB | Never a problem |
| Build minutes | 500 / month | Enough for ~50 redeploys |
| Sleep | After 15 min idle | Solved by UptimeRobot pings |
| Persistent disk | None on free | OK — we use Postgres for state |

If you ever hit the 750h quota (mostly happens if you run multiple
free services), the bot just stops at month-end. You'll get a heads-up
email from Render. The next month it auto-restarts.

---

## 6. Updating the bot later

Every `git push origin master` triggers an automatic redeploy on Render
(thanks to `autoDeploy: true` in `render.yaml`). The whole pipeline is:

```
edit code → git commit → git push → Render rebuilds → bot restarts
```

No more terminals, no more "did I leave my PC on?".

---

## 7. Backup plan: free alternatives if Render gets annoying

| Provider | Always-free? | Setup difficulty | Notes |
|----------|--------------|------------------|-------|
| **Render free** (this guide) | yes (sleeps without ping) | ★ easy | Recommended starting point |
| **Fly.io** | yes (3 shared VMs) | ★★ medium | Doesn't sleep, no ping needed; needs CLI |
| **Replit** | partially | ★ easy | They've cracked down on bots, not great in 2026 |
| **Oracle Cloud Free Tier** | yes (very generous) | ★★★ hard | 2 ARM VMs, 24 GB RAM total, no time limit |
| **Railway** | $5 trial only | ★ easy | Was great, no longer truly free |

If Render starts being weird about the keep-alive trick, **Fly.io** is
the next-best truly-free option — its free tier doesn't sleep at all.
