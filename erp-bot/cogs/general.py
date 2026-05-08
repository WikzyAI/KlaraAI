"""
General Cog - General commands (help, ping, etc.)
"""
import discord
from discord import app_commands
from discord.ext import commands


class GeneralCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="help", description="Show available commands")
    async def help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="✦ KlaraAI ✦",
            description="*Your private uncensored ERP bot — DM only.*",
            color=discord.Color.from_rgb(232, 67, 147)
        )

        embed.add_field(
            name="🎭 Main Commands",
            value=(
                "`/erp` — Open the session menu\n"
                "`/profile` — Profile, credits & streak\n"
                "`/settings` — Tune response length & customs\n"
                "`/premium` — Subscriptions & wallet\n"
                "`/memories` — What your characters remember about you\n"
                "`/referral` — Invite friends, earn credits\n"
                "`/help` — This message\n"
                "`/ping` — Check bot latency"
            ),
            inline=False
        )

        embed.add_field(
            name="🌹 How to Play",
            value=(
                "1. Run `/erp` and tap **Play**\n"
                "2. Choose your companion\n"
                "3. Just write — she replies automatically\n"
                "4. Tap **End Session** to stop the scene"
            ),
            inline=False
        )

        embed.add_field(
            name="💎 Get More",
            value=(
                "› Buy credits: [klaraai.me](https://www.klaraai.me/buy-credits)\n"
                "› See plans: `/premium`\n"
                "› Premium unlocks unlimited messages, custom characters, and Long responses"
            ),
            inline=False
        )

        embed.set_footer(text="KlaraAI • 18+ • Strictly DM-only")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="ping", description="Check if the bot is online")
    async def ping(self, interaction: discord.Interaction):
        latency = round(self.bot.latency * 1000)
        embed = discord.Embed(
            title="Pong!",
            description=f"Bot is online ✅\nLatency: {latency}ms",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(GeneralCog(bot))
