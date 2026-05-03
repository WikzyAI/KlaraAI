"""
KlaraAI - ERP Discord Bot
Bot works exclusively in DMs (Direct Messages).
"""
import discord
from discord.ext import commands
import config
import asyncio
import traceback
import os

class ERPBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.dm_messages = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.add_cog(GeneralCog(self))
        await self.add_cog(ProfileCog(self))
        await self.add_cog(PremiumCog(self))
        await self.add_cog(ERPCog(self))
        print("[OK] Cogs loaded")
        self.tree.interaction_check = self._global_interaction_check
        self._ensure_json_files()
        try:
            synced = await self.tree.sync()
            print(f"[OK] {len(synced)} slash commands synced globally")
        except Exception as e:
            print(f"[ERROR] Sync commands: {e}")
            traceback.print_exc()

    def _ensure_json_files(self):
        import json
        files = {
            config.CHARACTERS_FILE: config.DEFAULT_CHARACTERS,
            config.PROFILES_FILE: {},
            config.HISTORY_FILE: {}
        }
        for filename, default in files.items():
            if not os.path.exists(filename):
                with open(filename, "w", encoding="utf-8") as f:
                    json.dump(default, f, indent=2, ensure_ascii=False)
                print(f"[OK] File {filename} created")

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
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.streaming,
                name="ERP",
                url="https://twitch.tv/klaraai"
            )
        )

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

bot = ERPBot()

from cogs.general import GeneralCog
from cogs.profile import ProfileCog
from cogs.premium import PremiumCog
from cogs.erp import ERPCog

if __name__ == "__main__":
    if not config.TOKEN:
        print("[ERROR] DISCORD_TOKEN missing in .env")
    else:
        try:
            asyncio.run(bot.start(config.TOKEN))
        except KeyboardInterrupt:
            print("\n[STOP] Bot stopped by user")
        except Exception as e:
            print(f"[ERROR] Fatal error: {e}")
            traceback.print_exc()
