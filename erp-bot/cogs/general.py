"""
General Cog - Commandes générales (help, ping, etc.)
"""
import discord
from discord import app_commands
from discord.ext import commands


class GeneralCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="help", description="Affiche les commandes disponibles")
    async def help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="KlaraAI - Aide",
            description="Bot ERP privé fonctionnant exclusivement en messages privés (DM).",
            color=discord.Color.from_rgb(147, 112, 219)
        )

        embed.add_field(
            name="Commandes Principales",
            value="/help - Affiche ce message\n"
                  "/profile - Configure ton profil (nom, âge, desc)\n"
                  "/premium - Gère ton abonnement premium\n"
                  "/erp start <personnage> - Lance une séance ERP",
            inline=False
        )

        embed.add_field(
            name="ERP - Jeu de Rôle Érotique",
            value="/erp start <personnage> - Commence avec un personnage\n"
                  "/erp end - Termine la séance\n"
                  "/erp list - Liste les personnages\n"
                  "/erp info <perso> - Infos sur un personnage\n"
                  "/erp create - Crée ton perso (premium)",
            inline=False
        )

        embed.add_field(
            name="Notes",
            value="• Le bot fonctionne qu'en DM\n"
                  "• Une fois /erp start lancé, le bot répond automatiquement\n"
                  "• Utilise /erp end pour arrêter",
            inline=False
        )

        embed.set_footer(text="KlaraAI • Fait avec ❤️")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="ping", description="Vérifie si le bot est en ligne")
    async def ping(self, interaction: discord.Interaction):
        latency = round(self.bot.latency * 1000)
        embed = discord.Embed(
            title="Pong !",
            description=f"Bot en ligne ✅\nLatence : {latency}ms",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(GeneralCog(bot))
