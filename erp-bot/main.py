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


# Rotating presence — cycles every PRESENCE_INTERVAL seconds. Streaming type
# is mandatory to keep the purple "Live" dot in Discord. The url must be a
# valid twitch.tv / youtube.com URL for Discord to render the badge.
PRESENCE_URL = "https://twitch.tv/klaraai"
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

        await self.add_cog(GeneralCog(self))
        await self.add_cog(ProfileCog(self))
        await self.add_cog(PremiumCog(self))
        await self.add_cog(ERPCog(self))
        await self.add_cog(Characters(self))
        await self.add_cog(SocialCog(self))
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
        if self.rotate_presence.is_running():
            self.rotate_presence.cancel()
        await PostgresDB.close_db()
        print("[OK] Database pool closed")

    async def _global_interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.guild is not None:
            await interaction.response.send_message(
                "This bot only works in DMs.",
                ephemeral=True
            )
            return False
        return True

    async def on_ready(self):
        print(f"[OK] Logged in as {self.user} (ID: {self.user.id})")
        # Set an initial presence immediately, then start the rotation loop.
        await self._set_streaming_presence(next(self._presence_iter))
        if not self.rotate_presence.is_running():
            self.rotate_presence.start()

    async def _set_streaming_presence(self, name: str):
        # discord.Streaming(name=..., url=...) sets the displayed activity name
        # to `name`. Avoid passing `details=` — it would override and freeze the
        # title across rotations.
        try:
            await self.change_presence(
                status=discord.Status.online,
                activity=discord.Streaming(name=name, url=PRESENCE_URL),
            )
        except Exception as e:
            print(f"[Presence] change_presence failed: {e}")

    @tasks.loop(seconds=PRESENCE_INTERVAL)
    async def rotate_presence(self):
        await self._set_streaming_presence(next(self._presence_iter))

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
        cog = self.get_cog("ERPCog")
        if cog and hasattr(cog, "handle_dm_message"):
            print("[DEBUG] ERPCog found, calling handle_dm_message...")
            handled = await cog.handle_dm_message(message)
            print(f"[DEBUG] handle_dm_message returned: {handled}")
            if handled:
                return
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
