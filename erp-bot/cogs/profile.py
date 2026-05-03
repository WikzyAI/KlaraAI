"""
Profile Cog - User profile management.
Allows configuring name, age, description, response length, and custom characters via buttons.
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

    @app_commands.command(name="profile", description="View or update your profile")
    @app_commands.describe(
        name="Your name or nickname",
        age="Your age (must be ≥ 18)",
        description="A description of yourself (appearance, personality, etc.)"
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
            await interaction.followup.send("❌ You must be at least 18 years old to use this bot.", ephemeral=True)
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
            title="✅ Profile Updated",
            description="Your profile has been updated successfully.",
            color=discord.Color.green()
        )
        embed = self._build_profile_embed(interaction.user, profile, embed)
        await interaction.followup.send(embed=embed)

    def _build_profile_embed(self, user: discord.User, profile: dict, credits: int = None, embed: discord.Embed = None) -> discord.Embed:
        if embed is None:
            embed = discord.Embed(
                title=f"{user.name}'s Profile",
                color=discord.Color.from_rgb(147, 112, 219)
            )

        sub_type = profile.get("sub_type", "free")
        sub_name = config.SUBSCRIPTIONS.get(sub_type, config.SUBSCRIPTIONS["free"])["name"]

        response_length = profile.get("response_length", "medium")
        length_names = {"short": "Short (1-2 paragraphs)", "medium": "Medium (2-4 paragraphs)", "long": "Long (4-6 paragraphs)"}

        embed.add_field(name="Name", value=profile.get("name") or "Not set", inline=True)
        embed.add_field(name="Age", value=str(profile.get("age")) if profile.get("age") else "Not set", inline=True)
        embed.add_field(name="💎 Subscription", value=f"**{sub_name}**", inline=True)
        embed.add_field(name="📏 Response Length", value=length_names.get(response_length, response_length), inline=True)

        if credits is not None:
            embed.add_field(
                name="💎 Credits",
                value=f"{credits} credits (${credits/100:.2f})",
                inline=False
            )

        desc = profile.get("description")
        if desc:
            embed.add_field(name="Description", value=desc[:1024], inline=False)
        else:
            embed.add_field(name="Description", value="Not set", inline=False)

        embed.set_footer(text="Use /profile name:<name> age:<age> description:<desc> to modify")
        return embed

    @app_commands.command(name="settings", description="Configure bot settings (response length, custom characters)")
    async def settings(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)

        user_id = interaction.user.id
        profile = self.db.get_profile(user_id)
        limits = self.db.get_limits(user_id)

        embed = discord.Embed(
            title="⚙️ Settings",
            description="Click a button below to configure your settings.",
            color=discord.Color.blue()
        )

        current_length = profile.get("response_length", "short")
        length_names = {"short": "Short", "medium": "Medium", "long": "Long"}
        embed.add_field(name="📏 Current Response Length", value=length_names.get(current_length, current_length), inline=False)

        custom_chars_allowed = limits["custom_chars"]
        if custom_chars_allowed == -1:
            embed.add_field(name="🎭 Custom Characters", value="Unlimited", inline=False)
        else:
            embed.add_field(name="🎭 Custom Characters", value=f"{custom_chars_allowed} max", inline=False)

        # Get allowed lengths from subscription
        allowed_lengths = limits.get("allowed_lengths", ["short"])
        embed.add_field(name="✅ Available Lengths", value=", ".join([length_names.get(l, l) for l in allowed_lengths]), inline=False)

        view = discord.ui.View()

        # Response length buttons (only show allowed ones)
        if "short" in allowed_lengths:
            short_btn = discord.ui.Button(label="Short", style=discord.ButtonStyle.secondary if current_length != "short" else discord.ButtonStyle.success, emoji="📏")
            short_btn.callback = lambda i: self._set_response_length(i, "short")
            view.add_item(short_btn)

        if "medium" in allowed_lengths:
            medium_btn = discord.ui.Button(label="Medium", style=discord.ButtonStyle.secondary if current_length != "medium" else discord.ButtonStyle.success, emoji="📏")
            medium_btn.callback = lambda i: self._set_response_length(i, "medium")
            view.add_item(medium_btn)

        if "long" in allowed_lengths:
            long_btn = discord.ui.Button(label="Long", style=discord.ButtonStyle.secondary if current_length != "long" else discord.ButtonStyle.success, emoji="📏")
            long_btn.callback = lambda i: self._set_response_length(i, "long")
            view.add_item(long_btn)

        # Create custom character button
        create_btn = discord.ui.Button(label="Create Character", style=discord.ButtonStyle.primary, emoji="🎭")
        create_btn.callback = self._create_character_start
        view.add_item(create_btn)

        await interaction.followup.send(embed=embed, view=view)

    async def _set_response_length(self, interaction: discord.Interaction, length: str):
        await interaction.response.defer(thinking=True)
        user_id = str(interaction.user.id)

        # Check if user is allowed to use this length
        limits = self.db.get_limits(user_id)
        allowed_lengths = limits.get("allowed_lengths", ["short"])

        if length not in allowed_lengths:
            await interaction.followup.send(f"❌ Your subscription doesn't allow **{length}** responses. Allowed: {', '.join(allowed_lengths)}", ephemeral=True)
            return

        self.db.update_profile(user_id, response_length=length)
        length_names = {"short": "Short (1-2 paragraphs)", "medium": "Medium (2-4 paragraphs)", "long": "Long (4-6 paragraphs)"}
        embed = discord.Embed(
            title="✅ Setting Updated",
            description=f"Response length set to: **{length_names.get(length, length)}**",
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    async def _create_character_start(self, interaction: discord.Interaction):
        # Check if user can create custom characters
        profile = self.db.get_profile(str(interaction.user.id))
        limits = self.db.get_limits(str(interaction.user.id))
        custom_chars_allowed = limits["custom_chars"]

        if custom_chars_allowed == 0:
            await interaction.response.send_message("❌ This feature requires **Standard** or **Premium** subscription. Use `/premium` for more info.", ephemeral=True)
            return

        # For Premium, check how many customs have been created
        if custom_chars_allowed != -1:  # Not unlimited
            from cogs.erp import ERPCog
            erp_cog = interaction.client.get_cog("ERPCog")
            if erp_cog:
                characters = erp_cog._load_characters()
                user_chars = [k for k, v in characters.items() if v.get("creator") == str(interaction.user.id)]
                if len(user_chars) >= custom_chars_allowed:
                    await interaction.response.send_message(f"❌ Limit of {custom_chars_allowed} custom characters reached for your subscription.", ephemeral=True)
                    return

        # Start the character creation modal
        from cogs.erp import CharacterCreateModal
        modal = CharacterCreateModal(interaction.client.get_cog("ERPCog").characters_file)
        await interaction.response.send_modal(modal)


async def setup(bot: commands.Bot):
    await bot.add_cog(ProfileCog(bot))
