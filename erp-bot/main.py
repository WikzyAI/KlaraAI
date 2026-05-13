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
from utils.api_client import get_credits


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
        await self.add_cog(SocialCog(self))
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
        # Log everything so we can confirm in Render logs that the check is
        # firing — and that it returns the right verdict for every case.
        cmd_dbg = (
            interaction.command.qualified_name
            if interaction.command is not None
            else None
        )
        print(
            f"[Check] type={interaction.type!r} cmd={cmd_dbg!r} "
            f"guild={(interaction.guild.id if interaction.guild else None)!r} "
            f"user={interaction.user.id}"
        )

        if interaction.guild is None:
            return True  # DMs are always allowed

        # In the support guild we ONLY allow component interactions (the
        # age-verify button, future button menus, etc.). Slash commands and
        # modal submits are still refused even there — the bot is DM-only
        # for any actual usage.
        is_support_guild = (
            config.SUPPORT_GUILD_ID
            and interaction.guild.id == config.SUPPORT_GUILD_ID
        )
        if is_support_guild and interaction.type == discord.InteractionType.component:
            print("[Check] -> ALLOW (component in support guild)")
            return True

        print(
            f"[Check] -> REFUSE (cmd in guild, support={is_support_guild!r}, "
            f"type={interaction.type!r})"
        )

        # From here on: slash command (or any other interaction) in a guild.
        # Refuse + run the command's logic in DM context.
        cmd_name = cmd_dbg
        cmd_label = f"`/{cmd_name}`" if cmd_name else "this command"

        # Red embed so it reads as an error, not as a normal bot response.
        server_embed = discord.Embed(
            title="🚫 Command not allowed in this server",
            description=(
                f"KlaraAI works **only in Direct Messages** with the bot.\n\n"
                f"You tried {cmd_label} here — that doesn't work in servers, "
                f"not even in the support server.\n\n"
                f"📨 **Check your DMs** — I just sent you the answer to "
                f"{cmd_label} privately."
            ),
            color=0xef4444,
        )
        server_embed.set_footer(text="KlaraAI · DM-only for privacy and 18+ content.")
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(embed=server_embed, ephemeral=True)
            else:
                await interaction.followup.send(embed=server_embed, ephemeral=True)
        except Exception as e:
            print(f"[InteractionCheck] in-server reply failed: {e}")

        # Forward the command to the user's DM. We try to actually run the
        # command's logic (so they get the real /profile, /premium, /help...
        # output) and fall back to a hint embed for commands that need
        # interactive DM context (/erp, /settings, /memories) or that we
        # don't know how to forward.
        try:
            sent_real_result = await self._dispatch_command_to_dm(
                cmd_name, interaction
            )
        except discord.Forbidden:
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
            return False
        except Exception as e:
            print(f"[InteractionCheck] dispatch_to_dm failed: {type(e).__name__}: {e}")
            sent_real_result = False

        # If we couldn't run the actual command, at least send the
        # tailored hint embed so the user knows what to do next.
        if not sent_real_result:
            try:
                hint_embed = self._build_dm_redirect_embed(
                    cmd_name, interaction.guild.name
                )
                await interaction.user.send(embed=hint_embed)
            except discord.Forbidden:
                try:
                    await interaction.followup.send(
                        "⚠️ I couldn't DM you — your DMs from server members "
                        "are closed. Enable *Allow direct messages from server "
                        "members* in your Discord settings.",
                        ephemeral=True,
                    )
                except Exception:
                    pass
            except Exception as e:
                print(f"[InteractionCheck] hint DM failed: {e}")

        return False

    async def _dispatch_command_to_dm(
        self, cmd_name: str | None, interaction: discord.Interaction
    ) -> bool:
        """Run the equivalent of the user's slash command and DM them the result.

        Returns True if the actual command result was sent, False if we
        only know how to send a generic hint for this command.
        """
        if cmd_name is None:
            return False

        user = interaction.user

        # /profile — full profile embed (plan, credits, streak, quota).
        if cmd_name == "profile":
            profile_cog = self.get_cog("ProfileCog")
            if profile_cog is None:
                return False
            try:
                profile = await asyncio.wait_for(
                    PostgresDB.get_profile(user.id), timeout=10.0
                )
            except Exception as e:
                print(f"[DM-dispatch /profile] get_profile failed: {e}")
                return False
            credits = None
            try:
                credits_data = await asyncio.wait_for(
                    asyncio.to_thread(get_credits, str(user.id)),
                    timeout=10.0,
                )
                credits = credits_data.get("credits", 0)
            except Exception as e:
                print(f"[DM-dispatch /profile] get_credits failed: {e}")
            embed = await profile_cog._build_profile_embed_async(
                user, profile, credits=credits
            )
            await user.send(embed=embed)
            return True

        # /premium — subscription & credits summary.
        if cmd_name == "premium":
            try:
                profile = await asyncio.wait_for(
                    PostgresDB.get_profile(user.id), timeout=10.0
                )
                sub_type = await asyncio.wait_for(
                    PostgresDB.get_sub_type(user.id), timeout=10.0
                )
                limits = await asyncio.wait_for(
                    PostgresDB.get_limits(user.id), timeout=10.0
                )
            except Exception as e:
                print(f"[DM-dispatch /premium] DB error: {e}")
                return False
            credits = 0
            try:
                credits_data = await asyncio.wait_for(
                    asyncio.to_thread(get_credits, str(user.id)),
                    timeout=10.0,
                )
                credits = credits_data.get("credits", 0)
            except Exception as e:
                print(f"[DM-dispatch /premium] credits fetch failed: {e}")

            sub_emoji = {"free": "🌿", "standard": "💎", "premium": "👑"}.get(sub_type, "✨")
            is_admin = user.id in config.ADMIN_USER_IDS
            plan_label = f"{sub_emoji} **{limits['name']}**"
            if is_admin:
                plan_label += "  ·  🛡️ **ADMIN**"

            embed = discord.Embed(
                title="👑 Subscription & Credits",
                description=f"Current plan: {plan_label}",
                color=discord.Color.from_rgb(239, 68, 68) if is_admin else discord.Color.from_rgb(241, 196, 15),
            )
            msgs_used = profile.get("daily_msgs_used", 0)
            sess_used = profile.get("daily_sessions_used", 0)
            msgs_limit = "∞" if limits["daily_msgs"] == -1 else limits["daily_msgs"]
            sess_limit = "∞" if limits["daily_sessions"] == -1 else limits["daily_sessions"]
            embed.add_field(
                name="💰 Wallet",
                value=f"**{credits}** credits  *(${credits/100:.2f})*",
                inline=True,
            )
            embed.add_field(name="💬 Messages today", value=f"{msgs_used} / {msgs_limit}", inline=True)
            embed.add_field(name="🎬 Sessions today", value=f"{sess_used} / {sess_limit}", inline=True)
            embed.add_field(
                name="🔁 Manage your plan",
                value="Type `/premium` here in DM to see the upgrade options and click the buttons.",
                inline=False,
            )
            embed.set_footer(text="KlaraAI · Sent from the server because the bot is DM-only.")
            await user.send(embed=embed)
            return True

        # /help — full command list (static, safe everywhere).
        if cmd_name == "help":
            embed = discord.Embed(
                title="📖 KlaraAI — Commands",
                description=(
                    "All commands work **only in this DM**. Here's what each one does:\n\n"
                    "**Core**\n"
                    "• `/erp` — Pick a character and start a private 18+ scene\n"
                    "• `/profile` — Profile, credits, plan, daily quota, streak\n"
                    "• `/settings` — Response length, language, custom characters\n"
                    "• `/premium` — Subscription overview, upgrade or cancel\n\n"
                    "**Social**\n"
                    "• `/referral` — Your invite code + bonus credit stats\n\n"
                    "**Memory**\n"
                    "• `/memories` — Browse, edit or wipe what I remember\n\n"
                    "**Help**\n"
                    "• `/help` — This list."
                ),
                color=0x9b59b6,
            )
            embed.set_footer(text="KlaraAI · DM-only for privacy and 18+ content.")
            await user.send(embed=embed)
            return True

        # /referral — invite stats.
        if cmd_name == "referral":
            social_cog = self.get_cog("SocialCog")
            if social_cog is None:
                return False
            # SocialCog may expose a helper; if not, hint instead so we
            # don't crash on missing internals.
            builder = getattr(social_cog, "_build_referral_embed", None)
            if not builder:
                return False
            try:
                embed = await builder(user)
                await user.send(embed=embed)
                return True
            except Exception as e:
                print(f"[DM-dispatch /referral] failed: {e}")
                return False

        # Commands that need interactive DM context (sessions, modals,
        # multi-step views) — we point the user back to the DM instead of
        # trying to half-run them.
        return False

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
        try:
            from discord.app_commands import errors as app_errors
            if isinstance(error, app_errors.CheckFailure):
                print(f"[App] swallowed CheckFailure (handled in interaction_check): {error}")
                return
        except Exception:
            pass

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
        # interaction_check returning False raises CheckFailure under the
        # hood — we ALREADY handled the user-facing response inside the
        # check (red embed + DM dispatch), so don't send a second
        # "An error occurred" message on top of it.
        try:
            from discord.app_commands import errors as app_errors
            if isinstance(error, app_errors.CheckFailure):
                print(f"[Tree] swallowed CheckFailure (handled in interaction_check): {error}")
                return
        except Exception:
            pass

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
from cogs.social import SocialCog
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
