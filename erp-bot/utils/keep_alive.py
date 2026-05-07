"""
Tiny HTTP server kept alongside the Discord bot so we can run on free
hosting tiers (Render Web Service, Replit, etc.) that suspend a process
when it has no inbound HTTP traffic for a few minutes.

An external monitor (UptimeRobot, BetterStack, cron-job.org, ...) hits
the /ping endpoint every 5 minutes — that resets the inactivity timer
and keeps our bot alive 24/7 without paying.

aiohttp is already a transitive dependency of discord.py 2.x, no new
package required.
"""
import os
from aiohttp import web


async def _root(_request):
    return web.Response(
        text=(
            "✦ KlaraAI Discord bot is alive ✦\n"
            "Endpoints: /ping  /health\n"
        ),
        content_type="text/plain",
    )


async def _ping(_request):
    return web.Response(text="pong", content_type="text/plain")


async def _health(_request):
    return web.json_response({"status": "ok"})


async def start_keep_alive(port: int | None = None) -> web.AppRunner:
    """
    Start a small HTTP server in the same event loop as the bot.
    Returns the runner so the caller can shut it down cleanly.
    """
    port = port or int(os.getenv("PORT", "8080"))
    app = web.Application()
    app.router.add_get("/", _root)
    app.router.add_get("/ping", _ping)
    app.router.add_get("/health", _health)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"[KeepAlive] HTTP server listening on 0.0.0.0:{port}")
    return runner
