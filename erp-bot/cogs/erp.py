"""
ERP Cog - Erotic roleplay system with automatic DM responses.
Once a session is started via /erp (buttons), the bot replies automatically to messages.
"""
import discord
from discord import app_commands
from discord.ext import commands
import json
import os
import asyncio
from config import DEFAULT_CHARACTERS, SYSTEM_PROMPT, LANGUAGE_DIRECTIVES
from utils.db import PostgresDB
from utils.groq_client import GroqClient
from utils.ai_queue import AIQueue
from utils.api_client import add_credits
from utils.memory_extractor import extract_memories, format_memories_for_prompt


class ERPCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.groq = GroqClient()
        self.ai_queue = AIQueue(self.groq)
        self.characters_file = "characters.json"

    async def cog_load(self):
        await self.ai_queue.start()

    # Hard cap on the total char count of the chat history we send.
    # Some Groq models (qwen3-32b, gpt-oss-20b, allam-2-7b) reject large
    # payloads with HTTP 413. ~22k chars ≈ 5500 tokens which fits
    # comfortably in any 8k-context model alongside the system prompt
    # and the requested max_tokens output.
    MAX_HISTORY_CHARS = 22000

    def _build_messages(self, character: dict, history: list, user_profile: dict,
                        context_limit: int, memories: list = None) -> list:
        char_desc = character["desc"]
        if user_profile:
            user_name = user_profile.get("name") or "the user"
            user_age = user_profile.get("age") or "unspecified"
            user_desc = user_profile.get("description") or "unspecified"
            char_desc += f"\n\nThe user's name is {user_name}, age {user_age}. Description: {user_desc}"

        # Inject persistent long-term memories from previous sessions.
        if memories:
            char_desc += format_memories_for_prompt(memories, character["name"])

        # Resolve the language directive from the user's preference. Defaults
        # to "auto" — the model mirrors whatever language the user wrote in.
        lang_code = (user_profile or {}).get("language") or "auto"
        if lang_code not in LANGUAGE_DIRECTIVES:
            lang_code = "auto"
        language_directive = LANGUAGE_DIRECTIVES[lang_code]

        system_content = SYSTEM_PROMPT.format(
            character_name=character["name"],
            character_desc=char_desc,
            language_directive=language_directive,
        )
        messages = [{"role": "system", "content": system_content}]

        # Take the last N messages then trim from the OLDEST end if the total
        # char count exceeds the cap — keeps the most recent context intact.
        history_slice = list(history[-context_limit:])
        total_chars = sum(len(m.get("content", "")) for m in history_slice)
        dropped = 0
        while total_chars > self.MAX_HISTORY_CHARS and len(history_slice) > 1:
            removed = history_slice.pop(0)
            total_chars -= len(removed.get("content", ""))
            dropped += 1
        if dropped:
            print(f"[ERP] Trimmed {dropped} oldest messages to fit context cap "
                  f"({total_chars} chars / {self.MAX_HISTORY_CHARS})")

        for entry in history_slice:
            messages.append({"role": entry["role"], "content": entry["content"]})

        return messages

    async def handle_dm_message(self, message: discord.Message) -> bool:
        user_id = message.author.id
        print(f"[DEBUG ERP] handle_dm_message called for {user_id}")

        if not await PostgresDB.has_active_session(user_id):
            print(f"[DEBUG ERP] No active session for {user_id}")
            return False

        session = await PostgresDB.get_session(user_id)
        if not session:
            print(f"[DEBUG ERP] Session None for {user_id}")
            return False

        print(f"[DEBUG ERP] Active session found: {session.get('character_name', 'Unknown')}")

        if message.content.startswith("/"):
            print(f"[DEBUG ERP] Message starts with /, ignored")
            return False

        # CHECK DAILY LIMITS
        if not await PostgresDB.can_send_message(user_id):
            limits = await PostgresDB.get_limits(user_id)
            await message.channel.send(
                f"❌ Daily message limit reached ({'unlimited' if limits['daily_msgs'] == -1 else limits['daily_msgs']})/day. "
                f"Try again tomorrow or use `/premium` to upgrade your subscription."
            )
            return True

        # Load characters from DB
        characters = await PostgresDB.get_all_characters()
        char_key = session.get("character")
        if char_key not in characters:
            print(f"[DEBUG ERP] Character {char_key} not found")
            await message.channel.send("❌ Your session's character no longer exists. Use `/erp` and click 'End' to close the session.")
            return True

        character = characters[char_key]
        print(f"[DEBUG ERP] Character found: {character['name']}")

        # Get subscription limits
        limits = await PostgresDB.get_limits(user_id)
        max_tokens_limit = limits["max_tokens"]
        context_limit = limits["context"]
        allowed_lengths = limits.get("allowed_lengths", ["short"])

        # Adjust max_tokens based on response_length setting
        profile = await PostgresDB.get_profile(user_id)
        response_length = profile.get("response_length", "short")

        if response_length not in allowed_lengths:
            response_length = allowed_lengths[0]
            await PostgresDB.update_profile(user_id, response_length=response_length)

        length_tokens = {"short": 400, "medium": 800, "long": 1200}
        desired_tokens = length_tokens.get(response_length, 400)
        max_tokens = min(desired_tokens, max_tokens_limit)

        session["messages"].append({"role": "user", "content": message.content})
        await PostgresDB.set_session(user_id, session)
        print(f"[DEBUG ERP] User message added to history")

        user_profile = await PostgresDB.get_profile(user_id)

        # Pull up to 12 long-term memories for this user/character pair.
        try:
            memories = await PostgresDB.get_memories(user_id, char_key, limit=12)
        except Exception as e:
            print(f"[DEBUG ERP] Memory load failed: {e}")
            memories = []

        messages = self._build_messages(character, session["messages"], user_profile, context_limit, memories=memories)
        print(f"[DEBUG ERP] Messages prepared ({len(messages)} msgs, ctx={context_limit}, tokens={max_tokens}, memories={len(memories)})")

        sub_type = limits["type"]
        async with message.channel.typing():
            print(f"[DEBUG ERP] Calling AI via queue (priority for {sub_type})...")
            try:
                ai_response = await self.ai_queue.enqueue(
                    messages, 0.95, max_tokens, user_id, sub_type
                )
            except Exception as e:
                print(f"[DEBUG ERP] AI request failed: {e}")
                await message.channel.send("❌ The AI is taking too long to respond. Please try again in a moment.")
                return
            print(f"[DEBUG ERP] AI response received ({len(ai_response)} chars): {ai_response[:100]}...")

        session["messages"].append({"role": "assistant", "content": ai_response})
        await PostgresDB.set_session(user_id, session)

        # Increment message counter
        await PostgresDB.increment_messages(user_id)

        # Send as plain text (not embed) - split if too long
        await self._send_split_message(message.channel, ai_response)

        # Streak: bump and reward on milestones (background, never blocks the reply)
        asyncio.create_task(self._handle_streak(message, user_id, user_profile))
        # Referral activity gate: grant the gated signup bonus once the referee
        # has sent enough ERP messages.
        asyncio.create_task(self._handle_referral_activity(message, user_id, user_profile))

        print(f"[DEBUG ERP] Response sent successfully")
        return True

    async def _handle_referral_activity(self, message: discord.Message, user_id: int, user_profile: dict):
        try:
            # Only proceed if the user actually has an unfulfilled referral.
            row = await PostgresDB.increment_referee_msg_count(user_id)
            if row is None:
                return
            if row["signup_bonus_granted"]:
                return

            # Late-bound to avoid circular config: grab the gate + bonus from social cog constants.
            from cogs.social import REFEREE_ACTIVITY_GATE, REFEREE_SIGNUP_BONUS
            if (row["referee_msg_count"] or 0) < REFEREE_ACTIVITY_GATE:
                return

            username = user_profile.get("name") or message.author.name
            granted = await asyncio.to_thread(
                add_credits, str(user_id), REFEREE_SIGNUP_BONUS, username,
                "Referral signup bonus (activated)"
            )
            if granted.get("success", False):
                await PostgresDB.mark_signup_bonus_granted(user_id)
                embed = discord.Embed(
                    title="🎉 Referral bonus unlocked!",
                    description=(
                        f"You just earned **+{REFEREE_SIGNUP_BONUS} credits** for being active.\n"
                        f"*Your referrer also gets a reward when you spend `$5+`.*"
                    ),
                    color=discord.Color.from_rgb(46, 204, 113)
                )
                try:
                    await message.channel.send(embed=embed)
                except Exception:
                    pass
        except Exception as e:
            print(f"[Referral] Activity gate failed: {e}")

    async def _handle_streak(self, message: discord.Message, user_id: int, user_profile: dict):
        try:
            res = await PostgresDB.update_streak(user_id)
            reward = res.get("milestone_reward", 0)
            streak = res.get("streak", 0)
            if reward > 0:
                username = user_profile.get("name") or message.author.name
                granted = await asyncio.to_thread(
                    add_credits, str(user_id), reward, username, f"Streak day {streak}"
                )
                if granted.get("success", False):
                    embed = discord.Embed(
                        title=f"🔥 {streak}-day streak!",
                        description=(
                            f"You just earned **+{reward} credits** for keeping the streak alive.\n"
                            f"*Come back tomorrow to keep it going.*"
                        ),
                        color=discord.Color.from_rgb(255, 165, 0)
                    )
                    embed.set_footer(text=f"New balance reflected in /profile")
                    try:
                        await message.channel.send(embed=embed)
                    except Exception:
                        pass
        except Exception as e:
            print(f"[Streak] handle_streak failed: {e}")

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
            # If we're near the limit and find a sentence ending, split here
            if len(current) >= MAX_LENGTH - 500 and char in sentence_endings:
                chunks.append(current)
                current = ""
            # Hard limit: never exceed MAX_LENGTH
            elif len(current) >= MAX_LENGTH:
                chunks.append(current)
                current = ""

        if current:
            chunks.append(current)

        for chunk in chunks:
            if chunk.strip():
                await channel.send(chunk)

    # =======================================================================
    # SLASH COMMANDS
    # =======================================================================

    @app_commands.command(name="erp", description="Manage your ERP sessions - shows button menu")
    async def erp(self, interaction: discord.Interaction):
        """Show ERP session manager with buttons."""
        await interaction.response.defer(thinking=True)

        has_session = await PostgresDB.has_active_session(interaction.user.id)
        limits = await PostgresDB.get_limits(interaction.user.id)

        embed = discord.Embed(
            title="✦ ERP Session Manager ✦",
            description="*Step into your private playroom.* Pick an action below.",
            color=discord.Color.from_rgb(232, 67, 147)
        )

        if has_session:
            session = await PostgresDB.get_session(interaction.user.id)
            char_name = session.get("character_name", "Unknown")
            embed.add_field(
                name="🔥 Active Session",
                value=f"**{char_name}** is waiting for you...",
                inline=False
            )
        else:
            embed.add_field(
                name="💤 No Active Session",
                value="Click **Play** to begin a new scene.",
                inline=False
            )

        embed.set_footer(text=f"Plan: {limits['name']} • Click any button to continue")

        view = discord.ui.View(timeout=300)

        # Row 0: primary actions
        play_btn = discord.ui.Button(
            label="Play" if not has_session else "Switch",
            style=discord.ButtonStyle.success,
            emoji="🎭",
            row=0
        )
        play_btn.callback = lambda i: self._button_start(i)
        view.add_item(play_btn)

        if has_session:
            end_btn = discord.ui.Button(label="End Session", style=discord.ButtonStyle.danger, emoji="⛔", row=0)
            end_btn.callback = lambda i: self._button_end(i)
            view.add_item(end_btn)

        # Row 1: discovery
        list_btn = discord.ui.Button(label="Browse", style=discord.ButtonStyle.primary, emoji="🌹", row=1)
        list_btn.callback = lambda i: self._button_list(i)
        view.add_item(list_btn)

        if limits["custom_chars"] != 0:
            create_btn = discord.ui.Button(label="Create Character", style=discord.ButtonStyle.primary, emoji="✨", row=1)
            create_btn.callback = lambda i: self._button_create(i)
            view.add_item(create_btn)

        await interaction.followup.send(embed=embed, view=view)

    async def _button_start(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        await self._erp_list(interaction, show_buttons=True)

    async def _button_end(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        await self._erp_end(interaction)

    def _is_character_visible(self, char_key: str, char_data: dict, user_id: str) -> bool:
        creator = char_data.get("creator")
        if not creator:
            return True
        return str(creator) == str(user_id)

    async def _get_visible_characters(self, user_id: str) -> dict:
        all_chars = await PostgresDB.get_all_characters()
        return {k: v for k, v in all_chars.items() if self._is_character_visible(k, v, user_id)}

    async def _button_list(self, interaction: discord.Interaction, show_buttons: bool = True):
        await interaction.response.defer(thinking=True)
        user_id = str(interaction.user.id)
        characters = await self._get_visible_characters(user_id)

        embed = discord.Embed(
            title="🌹 Choose Your Companion",
            description="*Each one is waiting for a different kind of night...*",
            color=discord.Color.from_rgb(232, 67, 147)
        )

        char_emojis = ["💋", "🔥", "💜", "🌙", "⚡", "🥀", "🍷", "🖤"]

        for idx, (key, char) in enumerate(characters.items()):
            pers = char.get("personality", "N/A")
            emoji = char_emojis[idx % len(char_emojis)]
            is_private = " 🔒" if char.get("creator") else ""
            short_desc = char['desc'][:180] + ("..." if len(char['desc']) > 180 else "")
            embed.add_field(
                name=f"{emoji} {char['name']}{is_private}",
                value=f"{short_desc}\n*— {pers}*",
                inline=False
            )

        embed.set_footer(text="Click a name below to start instantly")

        if show_buttons:
            view = discord.ui.View(timeout=300)
            button_styles = [
                discord.ButtonStyle.danger,
                discord.ButtonStyle.success,
                discord.ButtonStyle.primary,
                discord.ButtonStyle.secondary,
                discord.ButtonStyle.danger,
            ]
            for idx, (key, char) in enumerate(list(characters.items())[:5]):
                emoji = char_emojis[idx % len(char_emojis)]
                btn = discord.ui.Button(
                    label=char['name'],
                    style=button_styles[idx % len(button_styles)],
                    emoji=emoji,
                    row=idx // 3
                )
                btn.callback = lambda i, k=key: self._start_with_character(i, k)
                view.add_item(btn)
            await interaction.followup.send(embed=embed, view=view)
        else:
            await interaction.followup.send(embed=embed)

    async def _start_with_character(self, interaction: discord.Interaction, char_key: str):
        await interaction.response.defer(thinking=True)
        characters = await PostgresDB.get_all_characters()
        if char_key not in characters:
            await interaction.followup.send(f"❌ Character '{char_key}' not found.", ephemeral=True)
            return
        char = characters[char_key]
        creator = char.get("creator")
        if creator and str(creator) != str(interaction.user.id):
            await interaction.followup.send("❌ This is a private character. You cannot use it.", ephemeral=True)
            return
        await self._erp_start(interaction, char_key)

    async def _button_info(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "❌ Use `/erp` and click 'Character Info' to get info on a specific character.",
            ephemeral=True
        )

    async def _button_create(self, interaction: discord.Interaction):
        limits = await PostgresDB.get_limits(interaction.user.id)
        custom_chars_allowed = limits["custom_chars"]

        if custom_chars_allowed == 0:
            await interaction.response.send_message(
                "❌ This feature requires **Standard** or **Premium** subscription. Use `/premium` for more info.",
                ephemeral=True
            )
            return

        if custom_chars_allowed != -1:
            characters = await PostgresDB.get_all_characters()
            user_chars = [k for k, v in characters.items() if v.get("creator") == str(interaction.user.id)]
            if len(user_chars) >= custom_chars_allowed:
                await interaction.response.send_message(
                    f"❌ Limit of {custom_chars_allowed} custom characters reached for your subscription.",
                    ephemeral=True
                )
                return

        modal = CharacterCreateModal()
        await interaction.response.send_modal(modal)

    async def _erp_start(self, interaction: discord.Interaction, character: str):
        if not character:
            await interaction.followup.send(
                "❌ You must specify a character. Use `/erp` and click 'List Characters'.",
                ephemeral=True
            )
            return

        characters = await PostgresDB.get_all_characters()
        char_key = character.lower()

        if char_key not in characters:
            await interaction.followup.send(
                f"❌ Character '{character}' not found. Use `/erp` and click 'List Characters'.",
                ephemeral=True
            )
            return

        char = characters[char_key]
        creator = char.get("creator")
        if creator and str(creator) != str(interaction.user.id):
            await interaction.followup.send("❌ This is a private character. You cannot use it.", ephemeral=True)
            return

        if await PostgresDB.has_active_session(interaction.user.id):
            await interaction.followup.send(
                "❌ You already have a session in progress. Use `/erp` and click 'End' to end it.",
                ephemeral=True
            )
            return

        if not await PostgresDB.can_start_session(interaction.user.id):
            limits = await PostgresDB.get_limits(interaction.user.id)
            await interaction.followup.send(
                f"❌ Daily session limit reached ({'unlimited' if limits['daily_sessions'] == -1 else limits['daily_sessions']})/day. "
                f"Try again tomorrow or use `/premium` to upgrade.",
                ephemeral=True
            )
            return

        session = {
            "character": char_key,
            "character_name": char["name"],
            "messages": []
        }
        await PostgresDB.set_session(interaction.user.id, session)
        await PostgresDB.increment_sessions(interaction.user.id)

        embed = discord.Embed(
            title=f"💋 The scene begins with {char['name']}",
            description=f"{char['desc']}\n\n**✨ Write your first message — she's listening.**",
            color=discord.Color.from_rgb(232, 67, 147)
        )
        embed.set_footer(text="Use /erp → 'End Session' to leave the scene")
        await interaction.followup.send(embed=embed)

    async def _erp_end(self, interaction: discord.Interaction):
        if not await PostgresDB.has_active_session(interaction.user.id):
            await interaction.followup.send("❌ You have no active session.", ephemeral=True)
            return

        session = await PostgresDB.get_session(interaction.user.id)
        char_name = session.get("character_name", "Unknown")
        char_key = session.get("character")
        msgs = session.get("messages", []) or []

        await PostgresDB.delete_session(interaction.user.id)

        embed = discord.Embed(
            title="🌙 Scene Ended",
            description=(
                f"*The lights dim and **{char_name}** fades away...*\n\n"
                f"💭 Saving memories so she remembers next time..."
            ),
            color=discord.Color.from_rgb(147, 112, 219)
        )
        await interaction.followup.send(embed=embed)

        # Extract & persist memories in the background (does not block the user)
        if char_key and len(msgs) >= 4:
            asyncio.create_task(
                self._save_session_memories(interaction.user.id, char_key, char_name, msgs)
            )

    async def _save_session_memories(self, user_id: int, char_key: str,
                                     char_name: str, messages: list):
        try:
            items = await extract_memories(self.groq, char_name, messages)
            if not items:
                return
            await PostgresDB.add_memories_bulk(user_id, char_key, items)
            print(f"[Memory] Saved {len(items)} memories for user {user_id} / {char_key}")
        except Exception as e:
            print(f"[Memory] Failed to save session memories: {e}")

    async def _erp_list(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        characters = await self._get_visible_characters(user_id)

        embed = discord.Embed(
            title="Available Characters",
            description="Use to begin.",
            color=discord.Color.from_rgb(147, 112, 219)
        )

        if not characters:
            embed.description = "No characters available. Use to create your own!"
        else:
            for key, char in characters.items():
                pers = char.get("personality", "N/A")
                is_private = " 🔒" if char.get("creator") else ""
                embed.add_field(
                    name=f"{char['name']} ({key}){is_private}",
                    value=f"{char['desc']}\n*Traits: {pers}*",
                    inline=False
                )

        embed.set_footer(text="Use /erp to launch a session, then click 'Start'")
        await interaction.followup.send(embed=embed)

    async def _erp_info(self, interaction: discord.Interaction, character: str):
        if not character:
            await interaction.followup.send("❌ You must specify a character.", ephemeral=True)
            return

        characters = await PostgresDB.get_all_characters()
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
        embed.set_footer(text=f"Click 'Start' in /erp to play this character")
        await interaction.followup.send(embed=embed)

    async def _erp_create(self, interaction: discord.Interaction,
                          name: str, description: str, personality: str):
        limits = await PostgresDB.get_limits(interaction.user.id)
        custom_chars_allowed = limits["custom_chars"]

        if custom_chars_allowed == 0:
            await interaction.followup.send(
                "❌ This feature requires **Standard** or **Premium** subscription. Use `/premium` for more info.",
                ephemeral=True
            )
            return

        if custom_chars_allowed != -1:
            characters = await PostgresDB.get_all_characters()
            user_chars = [k for k, v in characters.items() if v.get("creator") == str(interaction.user.id)]
            if len(user_chars) >= custom_chars_allowed:
                await interaction.followup.send(
                    f"❌ Limit of {custom_chars_allowed} custom characters reached for your subscription.",
                    ephemeral=True
                )
                return

        if not name or not description:
            await interaction.followup.send("❌ You must provide at least a name and a description.", ephemeral=True)
            return

        char_key = name.lower().replace(" ", "_")
        if await PostgresDB.character_exists(char_key):
            await interaction.followup.send(f"❌ A character with key '{char_key}' already exists.", ephemeral=True)
            return

        await PostgresDB.set_character(char_key, {
            "name": name,
            "desc": description,
            "personality": personality or "undefined",
            "creator": str(interaction.user.id),
        })

        embed = discord.Embed(
            title="✅ Character Created!",
            description=f"**{name}** has been added to the character list.",
            color=discord.Color.green()
        )
        embed.add_field(name="Key", value=f"`{char_key}`", inline=True)
        embed.set_footer(text=f"Click 'Start' in /erp to begin")
        await interaction.followup.send(embed=embed)


class CharacterCreateModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Create Custom Character")
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

        char_key = self.name_input.value.lower().replace(" ", "_")

        if await PostgresDB.character_exists(char_key):
            await interaction.followup.send(f"❌ A character with key '{char_key}' already exists.", ephemeral=True)
            return

        await PostgresDB.set_character(char_key, {
            "name": self.name_input.value,
            "desc": self.desc_input.value,
            "personality": self.personality_input.value or "undefined",
            "creator": str(interaction.user.id),
        })

        embed = discord.Embed(
            title="✅ Character Created!",
            description=f"**{self.name_input.value}** has been added to the character list.",
            color=discord.Color.green()
        )
        embed.add_field(name="Key", value=f"`{char_key}`", inline=True)
        embed.set_footer(text=f"Click 'Start' in /erp to begin")
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(ERPCog(bot))
