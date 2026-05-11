"""
KlaraAI - ERP Discord Bot
Bot works exclusively in DMs (Direct Messages).
"""
import discord
from discord.ext import commands, tasks
import config
import asyncio
import itertools
import traceback
import os
from utils.db import PostgresDB


# Rotating presence — cycles every PRESENCE_INTERVAL seconds.
# We use ActivityType.playing (green dot, no clickable link) instead of
# streaming because Discord forces streaming activities to show a "Watch"
# button that always opens a twitch.tv/youtube.com URL (it cannot point to
# arbitrary sites). Playing keeps the rotating text without a stray link.
PRESENCE_INTERVAL = 45  # seconds — Discord rate-limits presence updates

PRESENCE_ROTATION = [
    "💋 ERP with Lilith",
    "🌹 In Isabelle's bedroom",
    "🔥 Chloé's late-night calls",
    "✨ Uncensored 18+ AI",
    "💎 /erp to begin",
    "👑 Premium = unlimited",
    "🌙 Strictly DMs",
    "🎭 3 base + custom characters",
    "💜 Long-term memory",
    "🎟️ Invite friends, earn credits",
    "🔥 Daily streak rewards",
]


class ERPBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.dm_messages = True
        super().__init__(command_prefix="!", intents=intents)
        self._presence_iter = itertools.cycle(PRESENCE_ROTATION)
        self._keep_alive_runner = None

    async def setup_hook(self):
        # Initialize PostgreSQL
        if not config.DATABASE_URL:
            print("[ERROR] DATABASE_URL missing in .env")
            return
        try:
            await PostgresDB.init_db(config.DATABASE_URL)
            print("[OK] PostgreSQL initialized")
        except Exception as e:
            print(f"[ERROR] PostgreSQL init failed: {e}")
            traceback.print_exc()
            return

        # Start the keep-alive HTTP server when running on a host that
        # provides a $PORT env var (Render, Replit, Fly, Railway, ...).
        # Locally we don't need it.
        if os.getenv("PORT") or os.getenv("KEEP_ALIVE") == "1":
            try:
                from utils.keep_alive import start_keep_alive
                self._keep_alive_runner = await start_keep_alive()
            except Exception as e:
                print(f"[KeepAlive] start failed: {e}")

        await self.add_cog(GeneralCog(self))
        await self.add_cog(ProfileCog(self))
        await self.add_cog(PremiumCog(self))
        await self.add_cog(ERPCog(self))
        await self.add_cog(Characters(self))
        await self.add_cog(SocialCog(self))
        await self.add_cog(AdminCog(self))
        await self.add_cog(VerificationCog(self))
        await self.add_cog(StatusCog(self))
        print("[OK] Cogs loaded")

        self.tree.interaction_check = self._global_interaction_check
        self.tree.on_error = self.on_tree_error

        try:
            synced = await self.tree.sync()
            print(f"[OK] {len(synced)} slash commands synced globally")
        except Exception as e:
            print(f"[ERROR] Sync commands: {e}")
            traceback.print_exc()

    async def cleanup(self):
        """Clean up resources on shutdown."""
        # Best-effort: flip the support-server status message to "Offline"
        # before we lose the network. Must happen BEFORE we tear down the
        # discord client, otherwise the edit just fails silently.
        status_cog = self.get_cog("StatusCog")
        if status_cog is not None:
            try:
                await status_cog.mark_offline()
            except Exception as e:
                print(f"[Cleanup] StatusCog.mark_offline failed: {e}")

        if self.rotate_presence.is_running():
            self.rotate_presence.cancel()
        if self._keep_alive_runner is not None:
            try:
                await self._keep_alive_runner.cleanup()
                print("[OK] Keep-alive server stopped")
            except Exception:
                pass
        await PostgresDB.close_db()
        print("[OK] Database pool closed")

    async def _global_interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.guild is not None:
            # Allow interactions inside the KlaraAI Support server so the
            # persistent age-verify button + future support-server-only
            # commands keep working. Every other guild is still refused —
            # the bot is otherwise strictly DM-only for ERP usage.
            if config.SUPPORT_GUILD_ID and interaction.guild.id == config.SUPPORT_GUILD_ID:
                return True

            # Refuse the interaction in-server, then DM the user with a
            # tailored explanation of the exact command they tried. The
            # in-server response is ephemeral (only the caller sees it).
            cmd_name = (
                interaction.command.qualified_name
                if interaction.command is not None
                else None
            )
            cmd_label = f"`/{cmd_name}`" if cmd_name else "this command"

            server_reply = (
                f"🚫 **KlaraAI only works in Direct Messages.**\n\n"
                f"You tried {cmd_label} in this server.\n"
                f"📨 I'm sending you a DM right now with how to use {cmd_label} properly."
            )
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(server_reply, ephemeral=True)
                else:
                    await interaction.followup.send(server_reply, ephemeral=True)
            except Exception as e:
                print(f"[InteractionCheck] in-server reply failed: {e}")

            # Try to DM the user with a command-specific hint.
            dm_embed = self._build_dm_redirect_embed(cmd_name, interaction.guild.name)
            try:
                await interaction.user.send(embed=dm_embed)
            except discord.Forbidden:
                # User has DMs from server members disabled — tell them how
                # to fix it via the same ephemeral reply we already used.
                try:
                    await interaction.followup.send(
                        "⚠️ I couldn't DM you — your DMs from server members "
                        "are closed.\n"
                        "Open **User Settings → Privacy & Safety → Server "
                        "Privacy Defaults** and enable *Allow direct messages "
                        "from server members*, then try the command again.",
                        ephemeral=True,
                    )
                except Exception:
                    pass
            except Exception as e:
                print(f"[InteractionCheck] DM redirect failed: {e}")

            return False
        return True

    def _build_dm_redirect_embed(self, cmd_name: str | None, guild_name: str) -> discord.Embed:
        """Build the DM the bot sends after refusing an in-server command.

        The body is tailored to the exact slash command the user tried so the
        DM feels like a natural continuation of what they were doing, not a
        generic "go away" notice.
        """
        # (label_for_dm, short pitch describing the command)
        COMMAND_HINTS = {
            "erp": (
                "Start an ERP scene",
                "Pick one of your characters (Lilith, Isabelle, Chloé, or a "
                "custom one) and dive into a private 18+ scene.",
            ),
            "profile": (
                "View your profile",
                "Check your credits balance, current plan, daily quota and "
                "streak — all in one embed.",
            ),
            "settings": (
                "Configure your settings",
                "Response length, language, and custom character options.",
            ),
            "premium": (
                "Manage your subscription",
                "Upgrade to Standard or Premium, see your usage and reset "
                "countdown, or cancel anytime.",
            ),
            "help": (
                "See all commands",
                "Quick reference for everything KlaraAI can do.",
            ),
            "referral": (
                "Your referral code",
                "Invite friends and earn bonus credits when they make their "
                "first purchase.",
            ),
            "memories": (
                "Manage your memories",
                "Browse, edit or wipe what the bot remembers about you "
                "across sessions.",
            ),
        }

        if cmd_name and cmd_name in COMMAND_HINTS:
            label, pitch = COMMAND_HINTS[cmd_name]
            slash = f"/{cmd_name}"
            embed = discord.Embed(
                title=f"📨 {slash} — let's continue here in DM",
                description=(
                    f"You just tried `{slash}` in **{guild_name}**, but "
                    f"KlaraAI **only works in Direct Messages** — privacy "
                    f"and 18+ content stay between you and me.\n\n"
                    f"**About `{slash}` — {label}**\n"
                    f"_{pitch}_\n\n"
                    f"👉 **Type `{slash}` right here in this DM** and I'll "
                    f"respond normally."
                ),
                color=0x9b59b6,
            )
        elif cmd_name:
            slash = f"/{cmd_name}"
            embed = discord.Embed(
                title=f"📨 {slash} — let's continue here in DM",
                description=(
                    f"You just tried `{slash}` in **{guild_name}**, but "
                    f"KlaraAI **only works in Direct Messages**.\n\n"
                    f"👉 **Type `{slash}` right here in this DM** and I'll "
                    f"respond normally.\n\n"
                    f"_Type `/help` to see every command._"
                ),
                color=0x9b59b6,
            )
        else:
            embed = discord.Embed(
                title="📨 Let's continue here in DM",
                description=(
                    f"You just tried to use KlaraAI in **{guild_name}**, but "
                    f"the bot **only works in Direct Messages**.\n\n"
                    f"👉 **Use my commands right here in this DM** — start "
                    f"with `/help` or `/erp`."
                ),
                color=0x9b59b6,
            )
        embed.set_footer(text="KlaraAI · DM-only for privacy and 18+ content")
        return embed

    async def on_ready(self):
        print(f"[OK] Logged in as {self.user} (ID: {self.user.id})")
        # Set an initial presence immediately, then start the rotation loop.
        await self._set_presence(next(self._presence_iter))
        if not self.rotate_presence.is_running():
            self.rotate_presence.start()

    async def _set_presence(self, name: str):
        try:
            await self.change_presence(
                status=discord.Status.online,
                activity=discord.Game(name=name),
            )
        except Exception as e:
            print(f"[Presence] change_presence failed: {e}")

    @tasks.loop(seconds=PRESENCE_INTERVAL)
    async def rotate_presence(self):
        await self._set_presence(next(self._presence_iter))

    @rotate_presence.before_loop
    async def _before_rotate_presence(self):
        await self.wait_until_ready()

    async def on_app_command_error(self, interaction: discord.Interaction, error):
        print(f"[ERROR] Slash command error: {error}")
        traceback.print_exc()
        try:
            if interaction.response.is_done():
                await interaction.followup.send("❌ An error occurred. Please try again.", ephemeral=True)
            else:
                await interaction.response.send_message("❌ An error occurred. Please try again.", ephemeral=True)
        except Exception:
            pass

    async def on_tree_error(self, interaction: discord.Interaction, error):
        print(f"[ERROR] Tree error: {error}")
        traceback.print_exc()
        try:
            if interaction.response.is_done():
                await interaction.followup.send("❌ An error occurred. Please try again.", ephemeral=True)
            else:
                await interaction.response.send_message("❌ An error occurred. Please try again.", ephemeral=True)
        except Exception:
            pass

    async def on_message(self, message: discord.Message):
        if message.author == self.user:
            return
        if message.guild is not None:
            return
        print(f"[DEBUG] DM received from {message.author} (ID: {message.author.id}): {message.content[:50]}...")

        erp_cog = self.get_cog("ERPCog")
        if erp_cog and hasattr(erp_cog, "handle_dm_message"):
            try:
                handled = await erp_cog.handle_dm_message(message)
                print(f"[DEBUG] ERPCog.handle_dm_message returned: {handled}")
                if handled:
                    return
            except Exception as e:
                print(f"[ERROR] ERPCog.handle_dm_message: {e}")
                traceback.print_exc()
        else:
            print(f"[DEBUG] ERPCog not found! Available cogs: {list(self.cogs.keys())}")

    async def close(self):
        await self.cleanup()
        await super().close()


bot = ERPBot()

from cogs.general import GeneralCog
from cogs.profile import ProfileCog
from cogs.premium import PremiumCog
from cogs.erp import ERPCog
from cogs.characters import Characters
from cogs.social import SocialCog
from cogs.admin import AdminCog
from cogs.verification import VerificationCog
from cogs.status import StatusCog


if __name__ == "__main__":
    if not config.TOKEN:
        print("[ERROR] DISCORD_TOKEN missing in .env")
    elif not config.DATABASE_URL:
        print("[ERROR] DATABASE_URL missing in .env")
    else:
        try:
            asyncio.run(bot.start(config.TOKEN))
        except KeyboardInterrupt:
            print("\n[STOP] Bot stopped by user")
        except Exception as e:
            print(f"[ERROR] Fatal error: {e}")
            traceback.print_exc()
