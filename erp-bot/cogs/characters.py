"""
Characters Cog - Character management commands.
Includes listing characters and creating custom ones.
Works in NSFW channels AND in DMs.
"""
import discord
from discord import app_commands
from discord.ext import commands
import json
import os
from config import CHARACTERS_FILE


def is_allowed_channel(interaction: discord.Interaction) -> bool:
    """Check if the command can be used here (NSFW channel or DM)."""
    # Allow DMs
    if isinstance(interaction.channel, discord.DMChannel):
        return True
    # In servers, require NSFW
    return interaction.channel.is_nsfw()


class Characters(commands.Cog):
    """
    Cog for managing RP characters.
    Allows users to list characters and create custom ones.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.characters_file = CHARACTERS_FILE

    def _load_characters(self) -> dict:
        """Load characters from JSON file."""
        with open(self.characters_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_characters(self, data: dict):
        """Save characters to JSON file."""
        with open(self.characters_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    @app_commands.command(name="character", description="Manage RP characters")
    @app_commands.describe(
        action="Action to perform: list, info, create",
        name="Character name (for 'info' or 'create')",
        description="Character description (for 'create')",
        personality="Character personality traits (for 'create')"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="list", value="list"),
        app_commands.Choice(name="info", value="info"),
        app_commands.Choice(name="create", value="create"),
    ])
    async def character(self, interaction: discord.Interaction, action: str,
                       name: str = None, description: str = None, personality: str = None):
        """
        Character management command dispatcher.
        """
        await interaction.response.defer(thinking=True)

        if not is_allowed_channel(interaction):
            await interaction.followup.send("This command can only be used in NSFW channels or in DMs.", ephemeral=True)
            return

        action = action.lower()

        if action == "list":
            await self._character_list(interaction)
        elif action == "info":
            if not name:
                await interaction.followup.send("You must specify a character name. Use /character list to see all.", ephemeral=True)
                return
            await self._character_info(interaction, name)
        elif action == "create":
            await self._character_create(interaction, name, description, personality)

    async def _character_list(self, interaction: discord.Interaction):
        """List all available characters."""
        characters = self._load_characters()

        embed = discord.Embed(
            title="All Characters",
            description="Default and custom characters available for RP.",
            color=discord.Color.from_rgb(147, 112, 219)
        )

        for key, char in characters.items():
            personality = char.get("personality", "N/A")
            embed.add_field(
                name=f"{char['name']} ({key})",
                value=f"{char['desc']}\n*Traits: {personality}*",
                inline=False
            )

        embed.set_footer(text="Use /erp and click 'Start' to begin | Use /character info <name> for details")
        await interaction.followup.send(embed=embed)

    async def _character_info(self, interaction: discord.Interaction, name: str):
        """Show detailed info about a specific character."""
        characters = self._load_characters()
        char_key = name.lower()

        if char_key not in characters:
            await interaction.followup.send(f"Character '{name}' not found.", ephemeral=True)
            return

        char = characters[char_key]

        embed = discord.Embed(
            title=f"{char['name']}",
            description=char["desc"],
            color=discord.Color.from_rgb(255, 105, 180)
        )
        embed.add_field(name="Personality", value=char.get("personality", "N/A"), inline=False)
        embed.add_field(name="Key", value=f"`{char_key}`", inline=True)
        embed.set_footer(text=f"Use /erp and click 'Start' to roleplay with this character")

        await interaction.followup.send(embed=embed)

    async def _character_create(self, interaction: discord.Interaction,
                                name: str, description: str, personality: str):
        """Create a custom character (bonus feature)."""
        if not name or not description:
            await interaction.followup.send(
                "You must provide at least a name and description to create a character.\n"
                "Usage: /character create name:<name> description:<desc> personality:<traits>",
                ephemeral=True
            )
            return

        characters = self._load_characters()
        char_key = name.lower().replace(" ", "_")

        if char_key in characters:
            await interaction.followup.send(
                f"A character with key '{char_key}' already exists. Choose a different name.",
                ephemeral=True
            )
            return

        # Create new character
        characters[char_key] = {
            "name": name,
            "desc": description,
            "personality": personality or "undefined"
        }

        self._save_characters(characters)

        embed = discord.Embed(
            title="Character Created!",
            description=f"**{name}** has been added to the character list.",
            color=discord.Color.green()
        )
        embed.add_field(name="Key", value=f"`{char_key}`", inline=True)
        embed.add_field(name="Description", value=description, inline=False)
        if personality:
            embed.add_field(name="Personality", value=personality, inline=False)
        embed.set_footer(text=f"Use /erp and click 'Start' to start roleplaying with your new character!")

        await interaction.followup.send(embed=embed)


# Async setup function (required for load_extension in discord.py 2.0+)
async def setup(bot: commands.Bot):
    await bot.add_cog(Characters(bot))
