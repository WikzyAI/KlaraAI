"""
Profile Cog - Gestion du profil utilisateur.
Permet de configurer son nom, âge et description.
"""
import discord
from discord import app_commands
from discord.ext import commands
from utils.db import ProfilesDB
from utils.api_client import get_credits
import config
import asyncio


class ProfileCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = ProfilesDB(config.PROFILES_FILE)

    @app_commands.command(name="profile", description="Configure ton profil utilisateur")
    @app_commands.describe(
        name="Ton nom ou pseudo",
        age="Ton âge (doit être ≥ 18)",
        description="Une description de toi (apparence, personnalité, etc.)"
    )
    async def profile(self, interaction: discord.Interaction,
                     name: str = None,
                     age: int = None,
                     description: str = None):
        await interaction.response.defer(thinking=True)

        user_id = interaction.user.id
        profile = self.db.get_profile(user_id)

        if name is None and age is None and description is None:
            # Get credits from API
            credits_data = await asyncio.to_thread(get_credits, str(interaction.user.id))
            credits = credits_data.get("credits", 0)
            embed = self._build_profile_embed(interaction.user, profile, credits=credits)
            await interaction.followup.send(embed=embed)
            return

        if age is not None and age < 18:
            await interaction.followup.send("❌ Tu dois avoir au moins 18 ans pour utiliser ce bot.", ephemeral=True)
            return

        updates = {}
        if name is not None:
            updates["name"] = name
        if age is not None:
            updates["age"] = age
        if description is not None:
            updates["description"] = description

        profile = self.db.update_profile(user_id, **updates)

        embed = discord.Embed(
            title="✅ Profil mis à jour",
            description="Ton profil a été mis à jour avec succès.",
            color=discord.Color.green()
        )
        embed = self._build_profile_embed(interaction.user, profile, embed)
        await interaction.followup.send(embed=embed)

    def _build_profile_embed(self, user: discord.User, profile: dict, credits: int = None, embed: discord.Embed = None) -> discord.Embed:
        if embed is None:
            embed = discord.Embed(
                title=f"Profil de {user.name}",
                color=discord.Color.from_rgb(147, 112, 219)
            )

        embed.add_field(name="Nom", value=profile.get("name") or "Non configuré", inline=True)
        embed.add_field(name="Âge", value=str(profile.get("age")) if profile.get("age") else "Non configuré", inline=True)
        embed.add_field(name="Premium", value="✅ Oui" if profile.get("premium") else "❌ Non", inline=True)

        if credits is not None:
            embed.add_field(
                name="💎 Crédits",
                value=f"{credits} crédits (${credits/100:.2f})",
                inline=False
            )

        desc = profile.get("description")
        if desc:
            embed.add_field(name="Description", value=desc[:1024], inline=False)
        else:
            embed.add_field(name="Description", value="Non configurée", inline=False)

        embed.set_footer(text="Utilise /profile name:<nom> age:<âge> description:<desc> pour modifier")
        return embed


async def setup(bot: commands.Bot):
    await bot.add_cog(ProfileCog(bot))
