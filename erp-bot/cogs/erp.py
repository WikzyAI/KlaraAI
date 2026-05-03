"""
ERP Cog - Erotic roleplay system with automatic DM responses.
Once /erp start is launched, the bot replies automatically to messages.
"""
import discord
from discord import app_commands
from discord.ext import commands
import json
import os
from config import DEFAULT_CHARACTERS, CHARACTERS_FILE, SYSTEM_PROMPT, HISTORY_FILE, PROFILES_FILE
from utils.db import HistoryDB, ProfilesDB
from utils.groq_client import GroqClient


class ERPCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.groq = GroqClient()
        self.characters_file = CHARACTERS_FILE
        self.history_db = HistoryDB(HISTORY_FILE)
        self.profiles_db = ProfilesDB(PROFILES_FILE)
        self._ensure_characters_file()

    def _ensure_characters_file(self):
        if not os.path.exists(self.characters_file):
            with open(self.characters_file, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_CHARACTERS, f, indent=2, ensure_ascii=False)

    def _load_characters(self) -> dict:
        with open(self.characters_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _build_messages(self, character: dict, history: list, user_profile: dict, context_limit: int) -> list:
        char_desc = character["desc"]
        if user_profile:
            user_name = user_profile.get("name") or "the user"
            user_age = user_profile.get("age") or "unspecified"
            user_desc = user_profile.get("description") or "unspecified"
            char_desc += f"\n\nThe user's name is {user_name}, age {user_age}. Description: {user_desc}"

        system_content = SYSTEM_PROMPT.format(
            character_name=character["name"],
            character_desc=char_desc
        )
        messages = [{"role": "system", "content": system_content}]

        # Use context_limit from subscription
        for entry in history[-context_limit:]:
            messages.append({"role": entry["role"], "content": entry["content"]})

        return messages

    async def handle_dm_message(self, message: discord.Message) -> bool:
        user_id = message.author.id
        print(f"[DEBUG ERP] handle_dm_message called for {user_id}")

        if not self.history_db.has_active_session(user_id):
            print(f"[DEBUG ERP] No active session for {user_id}")
            return False

        session = self.history_db.get_session(user_id)
        if not session:
            print(f"[DEBUG ERP] Session None for {user_id}")
            return False

        print(f"[DEBUG ERP] Active session found: {session.get('character_name', 'Unknown')}")

        if message.content.startswith("/"):
            print(f"[DEBUG ERP] Message starts with /, ignored")
            return False

        # CHECK DAILY LIMITS
        if not self.profiles_db.can_send_message(user_id):
            limits = self.profiles_db.get_limits(user_id)
            await message.channel.send(
                f"❌ Daily message limit reached ({'unlimited' if limits['daily_msgs'] == -1 else limits['daily_msgs']})/day. "
                f"Try again tomorrow or use `/premium` to upgrade."
            )
            return True

        characters = self._load_characters()
        char_key = session.get("character")
        if char_key not in characters:
            print(f"[DEBUG ERP] Character {char_key} not found")
            await message.channel.send("❌ Your session's character no longer exists. Use `/erp end` then start again.")
            return True

        character = characters[char_key]
        print(f"[DEBUG ERP] Character found: {character['name']}")

        # Get subscription limits
        limits = self.profiles_db.get_limits(user_id)
        max_tokens = limits["max_tokens"]
        context_limit = limits["context"]

        # Adjust max_tokens based on response_length setting
        profile = self.profiles_db.get_profile(user_id)
        response_length = profile.get("response_length", "medium")
        length_multiplier = {"short": 0.5, "medium": 1.0, "long": 1.5}
        max_tokens = int(max_tokens * length_multiplier.get(response_length, 1.0))

        session["messages"].append({"role": "user", "content": message.content})
        self.history_db.set_session(user_id, session)
        print(f"[DEBUG ERP] User message added to history")

        user_profile = self.profiles_db.get_profile(user_id)
        messages = self._build_messages(character, session["messages"], user_profile, context_limit)
        print(f"[DEBUG ERP] Messages prepared for AI ({len(messages)} messages, context={context_limit}, tokens={max_tokens})")

        async with message.channel.typing():
            print(f"[DEBUG ERP] Calling AI (Groq)...")
            ai_response = self.groq.generate(messages, temperature=0.85, max_tokens=max_tokens)
            print(f"[DEBUG ERP] AI response received ({len(ai_response)} chars): {ai_response[:100]}...")

        session["messages"].append({"role": "assistant", "content": ai_response})
        self.history_db.set_session(user_id, session)

        # Increment message counter
        self.profiles_db.increment_messages(user_id)

        # Send as plain text (not embed) - split if too long
        await self._send_split_message(message.channel, ai_response)

        print(f"[DEBUG ERP] Response sent successfully")
        return True

    async def _send_split_message(self, channel, text):
        """Send message, split if it exceeds Discord's 2000 char limit at sentence boundaries."""
        MAX_LENGTH = 2000
        if len(text) <= MAX_LENGTH:
            await channel.send(text)
            return

        chunks = []
        current = ""
        sentence_endings = {'.', '!', '?', '\n'}

        for char in text:
            current += char
            # Split at sentence endings when we're near the limit
            if len(current) >= MAX_LENGTH - 300 and char in sentence_endings:
                chunks.append(current)
                current = ""

        if current:
            chunks.append(current)

        # Merge short tail with previous chunk
        merged = []
        for chunk in chunks:
            if merged and len(chunk) < 100:
                merged[-1] += chunk
            else:
                merged.append(chunk)

        for chunk in merged:
            await channel.send(chunk)

    # =======================================================================
    # SLASH COMMANDS
    # =======================================================================

    @app_commands.command(name="erp", description="Manage your ERP sessions")
    @app_commands.describe(
        character="Character name (for 'start' or 'info')",
        description="Character description (for 'create')",
        personality="Personality traits (for 'create')"
    )
    async def erp(self, interaction: discord.Interaction,
                  character: str = None,
                  description: str = None,
                  personality: str = None):
        await interaction.response.defer(thinking=True)

        # If character is provided, start directly
        if character:
            await self._erp_start(interaction, character)
            return

        # Show button menu
        embed = discord.Embed(
            title="🎭 ERP Session Manager",
            description="Click a button below to manage your ERP session.",
            color=discord.Color.from_rgb(255, 105, 180)
        )

        # Check if user has active session
        has_session = self.history_db.has_active_session(interaction.user.id)
        if has_session:
            session = self.history_db.get_session(interaction.user.id)
            char_name = session.get("character_name", "Unknown")
            embed.add_field(name="Current Session", value=f"Active with **{char_name}**", inline=False)

        view = discord.ui.View()

        start_btn = discord.ui.Button(label="Start", style=discord.ButtonStyle.success, emoji="▶️")
        start_btn.callback = lambda i: self._button_start(i)
        view.add_item(start_btn)

        if has_session:
            end_btn = discord.ui.Button(label="End", style=discord.ButtonStyle.danger, emoji="⏹")
            end_btn.callback = lambda i: self._button_end(i)
            view.add_item(end_btn)

        list_btn = discord.ui.Button(label="List Characters", style=discord.ButtonStyle.primary, emoji="📋")
        list_btn.callback = lambda i: self._button_list(i)
        view.add_item(list_btn)

        info_btn = discord.ui.Button(label="Character Info", style=discord.ButtonStyle.secondary, emoji="ℹ️")
        info_btn.callback = lambda i: self._button_info(i)
        view.add_item(info_btn)

        # Check if user can create custom chars
        limits = self.profiles_db.get_limits(interaction.user.id)
        if limits["custom_chars"] != 0:
            create_btn = discord.ui.Button(label="Create Character", style=discord.ButtonStyle.primary, emoji="🎭")
            create_btn.callback = lambda i: self._button_create(i)
            view.add_item(create_btn)

        await interaction.followup.send(embed=embed, view=view)

    async def _button_start(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        await self._erp_list(interaction, show_buttons=False)

    async def _button_end(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        await self._erp_end(interaction)

    async def _button_list(self, interaction: discord.Interaction, show_buttons: bool = True):
        await interaction.response.defer(thinking=True)
        characters = self._load_characters()
        limits = self.profiles_db.get_limits(interaction.user.id)

        embed = discord.Embed(
            title="Available Characters",
            description="Click a character to start a session!",
            color=discord.Color.from_rgb(147, 112, 219)
        )

        for key, char in characters.items():
            pers = char.get("personality", "N/A")
            embed.add_field(
                name=f"{char['name']} ({key})",
                value=f"{char['desc']}\n*Traits: {pers}*",
                inline=False
            )

        if show_buttons:
            view = discord.ui.View()
            for key, char in list(characters.items())[:5]:  # Limit to 5 buttons
                btn = discord.ui.Button(
                    label=f"Start {char['name']}",
                    style=discord.ButtonStyle.success,
                    emoji="▶️"
                )
                btn.callback = lambda i, k=key: self._start_with_character(i, k)
                view.add_item(btn)
            await interaction.followup.send(embed=embed, view=view)
        else:
            await interaction.followup.send(embed=embed)

    async def _start_with_character(self, interaction: discord.Interaction, char_key: str):
        await interaction.response.defer(thinking=True)
        await self._erp_start(interaction, char_key)

    async def _button_info(self, interaction: discord.Interaction):
        await interaction.response.send_message("❌ Use `/erp info <character>` to get info on a specific character.", ephemeral=True)

    async def _button_create(self, interaction: discord.Interaction):
        # Check if user can create custom characters
        limits = self.profiles_db.get_limits(interaction.user.id)
        custom_chars_allowed = limits["custom_chars"]

        if custom_chars_allowed == 0:
            await interaction.response.send_message("❌ This feature requires **Standard** or **Premium** subscription. Use `/premium` for more info.", ephemeral=True)
            return

        # For Premium, check how many customs have been created
        if custom_chars_allowed != -1:  # Not unlimited
            characters = self._load_characters()
            user_chars = [k for k, v in characters.items() if v.get("creator") == str(interaction.user.id)]
            if len(user_chars) >= custom_chars_allowed:
                await interaction.response.send_message(f"❌ Limit of {custom_chars_allowed} custom characters reached for your subscription.", ephemeral=True)
                return

        # Show modal for character creation
        modal = CharacterCreateModal(self.db, self.characters_file)
        await interaction.response.send_modal(modal)

    async def _erp_start(self, interaction: discord.Interaction, character: str):
        if not character:
            await interaction.followup.send("❌ You must specify a character. Use `/erp list` to see available ones.", ephemeral=True)
            return

        characters = self._load_characters()
        char_key = character.lower()

        if char_key not in characters:
            await interaction.followup.send(f"❌ Character '{character}' not found. Use `/erp list`.", ephemeral=True)
            return

        if self.history_db.has_active_session(interaction.user.id):
            await interaction.followup.send("❌ You already have a session in progress. Use `/erp end` to end it.", ephemeral=True)
            return

        # CHECK DAILY LIMITS
        if not self.profiles_db.can_start_session(interaction.user.id):
            limits = self.profiles_db.get_limits(interaction.user.id)
            await interaction.followup.send(
                f"❌ Daily session limit reached ({'unlimited' if limits['daily_sessions'] == -1 else limits['daily_sessions']})/day. "
                f"Try again tomorrow or use `/premium` to upgrade.",
                ephemeral=True
            )
            return

        char = characters[char_key]

        session = {
            "character": char_key,
            "character_name": char["name"],
            "messages": []
        }
        self.history_db.set_session(interaction.user.id, session)

        # Increment session counter
        self.profiles_db.increment_sessions(interaction.user.id)

        embed = discord.Embed(
            title=f"✅ ERP Session Started with {char['name']}",
            description=f"{char['desc']}\n\n**Write your first message to begin!**\nThe bot will automatically reply to your messages.",
            color=discord.Color.from_rgb(255, 105, 180)
        )
        embed.set_footer(text="Use /erp end to end the session")
        await interaction.followup.send(embed=embed)

    async def _erp_end(self, interaction: discord.Interaction):
        if not self.history_db.has_active_session(interaction.user.id):
            await interaction.followup.send("❌ You have no active session.", ephemeral=True)
            return

        session = self.history_db.get_session(interaction.user.id)
        char_name = session.get("character_name", "Unknown")

        self.history_db.delete_session(interaction.user.id)

        embed = discord.Embed(
            title="✅ Session Ended",
            description=f"Your session with **{char_name}** has ended. Thanks for playing!",
            color=discord.Color.from_rgb(147, 112, 219)
        )
        await interaction.followup.send(embed=embed)

    async def _erp_list(self, interaction: discord.Interaction):
        characters = self._load_characters()
        limits = self.profiles_db.get_limits(interaction.user.id)

        embed = discord.Embed(
            title="Available Characters",
            description="Use `/erp start <character>` to begin.",
            color=discord.Color.from_rgb(147, 112, 219)
        )

        for key, char in characters.items():
            pers = char.get("personality", "N/A")
            embed.add_field(
                name=f"{char['name']} ({key})",
                value=f"{char['desc']}\n*Traits: {pers}*",
                inline=False
            )

        embed.set_footer(text="/erp start <character> to launch a session")
        await interaction.followup.send(embed=embed)

    async def _erp_info(self, interaction: discord.Interaction, character: str):
        if not character:
            await interaction.followup.send("❌ You must specify a character.", ephemeral=True)
            return

        characters = self._load_characters()
        char_key = character.lower()

        if char_key not in characters:
            await interaction.followup.send(f"❌ Character '{character}' not found.", ephemeral=True)
            return

        char = characters[char_key]

        embed = discord.Embed(
            title=char['name'],
            description=char["desc"],
            color=discord.Color.from_rgb(255, 105, 180)
        )
        embed.add_field(name="Personality", value=char.get("personality", "N/A"), inline=False)
        embed.add_field(name="Key", value=f"`{char_key}`", inline=True)
        embed.set_footer(text=f"Use /erp start {char_key} to play this character")
        await interaction.followup.send(embed=embed)

    async def _erp_create(self, interaction: discord.Interaction,
                          name: str, description: str, personality: str):
        # Check if user can create custom chars
        limits = self.profiles_db.get_limits(interaction.user.id)
        custom_chars_allowed = limits["custom_chars"]

        if custom_chars_allowed == 0:
            await interaction.followup.send("❌ This feature requires **Standard** or **Premium** subscription. Use `/premium` for more info.", ephemeral=True)
            return

        # For Premium, check how many customs have been created
        if custom_chars_allowed != -1:  # Not unlimited
            characters = self._load_characters()
            user_chars = [k for k, v in characters.items() if v.get("creator") == str(interaction.user.id)]
            if len(user_chars) >= custom_chars_allowed:
                await interaction.followup.send(f"❌ Limit of {custom_chars_allowed} custom characters reached for your subscription.", ephemeral=True)
                return

        if not name or not description:
            await interaction.followup.send("❌ You must provide at least a name and a description.", ephemeral=True)
            return

        characters = self._load_characters()
        char_key = name.lower().replace(" ", "_")

        if char_key in characters:
            await interaction.followup.send(f"❌ A character with key '{char_key}' already exists.", ephemeral=True)
            return

        characters[char_key] = {
            "name": name,
            "desc": description,
            "personality": personality or "undefined",
            "creator": str(interaction.user.id)
        }

        with open(self.characters_file, "w", encoding="utf-8") as f:
            json.dump(characters, f, indent=2, ensure_ascii=False)

        embed = discord.Embed(
            title="✅ Character Created!",
            description=f"**{name}** has been added to the character list.",
            color=discord.Color.green()
        )
        embed.add_field(name="Key", value=f"`{char_key}`", inline=True)
        embed.set_footer(text=f"Use /erp start {char_key} to begin")
        await interaction.followup.send(embed=embed)


class CharacterCreateModal(discord.ui.Modal):
    def __init__(self, characters_file):
        super().__init__(title="Create Custom Character")
        self.characters_file = characters_file

        self.name_input = discord.ui.TextInput(
            label="Character Name",
            placeholder="Enter character name...",
            max_length=50
        )
        self.add_item(self.name_input)

        self.desc_input = discord.ui.TextInput(
            label="Description",
            placeholder="Physical appearance, personality, etc...",
            style=discord.TextStyle.long,
            max_length=1000
        )
        self.add_item(self.desc_input)

        self.personality_input = discord.ui.TextInput(
            label="Personality Traits",
            placeholder="e.g., seductive, mysterious, dominant...",
            max_length=200
        )
        self.add_item(self.personality_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)

        # Load characters
        import json
        with open(self.characters_file, "r", encoding="utf-8") as f:
            characters = json.load(f)

        char_key = self.name_input.value.lower().replace(" ", "_")

        if char_key in characters:
            await interaction.followup.send(f"❌ A character with key '{char_key}' already exists.", ephemeral=True)
            return

        characters[char_key] = {
            "name": self.name_input.value,
            "desc": self.desc_input.value,
            "personality": self.personality_input.value or "undefined",
            "creator": str(interaction.user.id)
        }

        with open(self.characters_file, "w", encoding="utf-8") as f:
            json.dump(characters, f, indent=2, ensure_ascii=False)

        embed = discord.Embed(
            title="✅ Character Created!",
            description=f"**{self.name_input.value}** has been added to the character list.",
            color=discord.Color.green()
        )
        embed.add_field(name="Key", value=f"`{char_key}`", inline=True)
        embed.set_footer(text=f"Use /erp start {char_key} to begin")
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(ERPCog(bot))
