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
            title="KlaraAI - Help",
            description="Private ERP bot that works exclusively in DMs.",
            color=discord.Color.from_rgb(147, 112, 219)
        )

        embed.add_field(
            name="Main Commands",
            value="/help - Show this message\n"
                  "/profile - View or update your profile\n"
                  "/settings - Configure bot settings\n"
                  "/premium - Manage your subscription\n"
                  "/erp - Show ERP session manager (buttons)",
            inline=False
        )

        embed.add_field(
            name="ERP - Erotic Roleplay",
            value="Use /erp to show the button menu\n"
                  "• Click 'Start' to begin with a character\n"
                  "• Click 'End' to close the session\n"
                  "• Click 'List Characters' to see available characters\n"
                  "• Click 'Character Info' for details\n"
                  "• Create your own character in /settings (premium)",
            inline=False
        )

        embed.add_field(
            name="Notes",
            value="• Bot only works in DMs\n"
                  "• Once a session is started via /erp buttons, the bot replies automatically\n"
                  "• Use /erp and click 'End' to stop",
            inline=False
        )

        embed.set_footer(text="KlaraAI • Made with ❤️")
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
