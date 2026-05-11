"""
Status Cog — keeps a live status message in the support server's #status
channel.

Behaviour
---------
- On boot, finds the bot's existing status message in #status (or posts a
  new one if none exists) and edits it to "🟢 Online".
- Edits the message every HEARTBEAT_INTERVAL seconds with a fresh
  timestamp ("Last heartbeat: <t:NOW:R>") and the current uptime. Discord
  renders the relative time on the client side, so visitors always see a
  fresh "X seconds ago" without us spamming edits.
- On graceful shutdown the bot's close() hook calls mark_offline() which
  switches the embed to "🔴 Offline" before disconnecting. If the bot
  crashes hard (host kills it, network drops), the heartbeat just stops
  and the "Last heartbeat" relative time keeps growing on its own — once
  it's more than ~2 minutes old, anyone visiting the channel can tell
  the bot is down.

The message is identified by being the latest embed in #status whose
author is the bot itself, so we don't need to persist any IDs in the DB.
"""
import asyncio
import time
from datetime import datetime, timezone

import discord
from discord.ext import commands, tasks

import config


HEARTBEAT_INTERVAL = 60  # seconds between message edits
STATUS_CHANNEL_NAME = "status"
STALE_THRESHOLD_SECONDS = 120  # how long we tell users to wait before assuming offline


def _format_uptime(seconds: int) -> str:
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours or days:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}m")
    return " ".join(parts)


class StatusCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.status_message: discord.Message | None = None
        self.boot_time = time.time()
        self._initialized = False

    # ----------------------------------------------------------------
    # Embed builders
    # ----------------------------------------------------------------
    def _build_online_embed(self) -> discord.Embed:
        now = datetime.now(timezone.utc)
        ts = int(now.timestamp())
        uptime = _format_uptime(int(time.time() - self.boot_time))

        embed = discord.Embed(
            title="🟢 KlaraAI — Online",
            description=(
                "The bot is **up and responding normally.**\n\n"
                f"⏱️  Last heartbeat: <t:{ts}:R>  ·  *<t:{ts}:T>*\n"
                f"📈  Uptime: **{uptime}**\n"
                f"🔄  Auto-refresh: every **{HEARTBEAT_INTERVAL}s**\n\n"
                f"_If the 'Last heartbeat' shown above is more than "
                f"~{STALE_THRESHOLD_SECONDS // 60} minutes old, the bot is "
                f"probably offline — wait a few minutes or ping an admin._"
            ),
            color=0x10b981,
        )
        embed.set_footer(text="KlaraAI · Live status")
        return embed

    def _build_offline_embed(self) -> discord.Embed:
        now = datetime.now(timezone.utc)
        ts = int(now.timestamp())
        uptime = _format_uptime(int(time.time() - self.boot_time))

        embed = discord.Embed(
            title="🔴 KlaraAI — Offline",
            description=(
                "The bot is **currently offline.**\n\n"
                f"⏱️  Went offline: <t:{ts}:R>  ·  *<t:{ts}:T>*\n"
                f"📈  Was up for: **{uptime}**\n\n"
                "The bot is most likely being redeployed or restarting.\n"
                "Please try again in a few minutes.\n"
                "If the issue persists, ping an admin in <#help>."
            ),
            color=0xef4444,
        )
        embed.set_footer(text="KlaraAI · Live status")
        return embed

    # ----------------------------------------------------------------
    # Setup
    # ----------------------------------------------------------------
    async def _find_or_create_message(self) -> discord.Message | None:
        if not config.SUPPORT_GUILD_ID:
            print("[Status] SUPPORT_GUILD_ID not set — skipping status cog")
            return None

        guild = self.bot.get_guild(config.SUPPORT_GUILD_ID)
        if guild is None:
            print(f"[Status] Bot is not in SUPPORT_GUILD_ID={config.SUPPORT_GUILD_ID}")
            return None

        channel = discord.utils.get(guild.text_channels, name=STATUS_CHANNEL_NAME)
        if channel is None:
            print(f"[Status] #{STATUS_CHANNEL_NAME} not found in {guild.name}")
            return None

        # 1. Try pinned messages first (cheap, exact).
        try:
            pins = await channel.pins()
            for msg in pins:
                if msg.author.id == self.bot.user.id and msg.embeds:
                    return msg
        except Exception as e:
            print(f"[Status] pins() failed: {e}")

        # 2. Fall back to scanning the latest 50 messages.
        try:
            async for msg in channel.history(limit=50):
                if msg.author.id == self.bot.user.id and msg.embeds:
                    return msg
        except Exception as e:
            print(f"[Status] history scan failed: {e}")

        # 3. No prior message — create one and pin it for stability.
        try:
            new_msg = await channel.send(embed=self._build_online_embed())
            try:
                await new_msg.pin(reason="KlaraAI live status")
            except discord.Forbidden:
                pass  # not allowed to pin — not a problem
            return new_msg
        except Exception as e:
            print(f"[Status] failed to post initial status message: {e}")
            return None

    @commands.Cog.listener()
    async def on_ready(self):
        # on_ready can fire multiple times (reconnects) — initialise only once.
        if self._initialized:
            return
        self._initialized = True

        self.status_message = await self._find_or_create_message()
        if self.status_message is None:
            return

        # Refresh immediately so the message shows "online" right after boot.
        try:
            await self.status_message.edit(embed=self._build_online_embed())
        except Exception as e:
            print(f"[Status] initial edit failed: {e}")

        if not self.heartbeat.is_running():
            self.heartbeat.start()

    # ----------------------------------------------------------------
    # Heartbeat loop
    # ----------------------------------------------------------------
    @tasks.loop(seconds=HEARTBEAT_INTERVAL)
    async def heartbeat(self):
        if self.status_message is None:
            return
        try:
            await self.status_message.edit(embed=self._build_online_embed())
        except discord.NotFound:
            # Someone deleted the message — try to re-post one.
            print("[Status] status message was deleted, re-creating...")
            self.status_message = await self._find_or_create_message()
        except discord.HTTPException as e:
            # Rate-limit or transient API error — just log and try next tick.
            print(f"[Status] heartbeat edit HTTPException: {e}")
        except Exception as e:
            print(f"[Status] heartbeat edit failed: {type(e).__name__}: {e}")

    @heartbeat.before_loop
    async def _before_heartbeat(self):
        await self.bot.wait_until_ready()

    # ----------------------------------------------------------------
    # Shutdown hook
    # ----------------------------------------------------------------
    async def mark_offline(self):
        """Best-effort edit to "Offline" before the bot disconnects.

        Called by main.py's close() override. If the network is already
        gone we just swallow the error — users will see the stale heartbeat
        timestamp and infer the bot is down.
        """
        if self.heartbeat.is_running():
            self.heartbeat.cancel()
        if self.status_message is None:
            return
        try:
            await asyncio.wait_for(
                self.status_message.edit(embed=self._build_offline_embed()),
                timeout=5.0,
            )
            print("[Status] marked status message as Offline")
        except Exception as e:
            print(f"[Status] mark_offline failed (expected on hard kill): {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(StatusCog(bot))
