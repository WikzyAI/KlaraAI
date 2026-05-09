"""
Chat Cog — real-texting simulator. Different from /erp:
- Texts back like a real person (no narration, no asterisks, short messages)
- 4 fixed personas: Step-sister, Girlfriend, Friend, Step-mom
- User chooses NSFW mode at session start
- Uses lower max_tokens (chat is short by nature)

Shares the AI infra (GroqClient + AIQueue) with ERP. Only one active session
per user at a time, regardless of type — starting a chat ends any active ERP
session and vice versa.
"""
import asyncio
import discord
from discord import app_commands
from discord.ext import commands

from config import (
    CHAT_PERSONAS, CHAT_SYSTEM_PROMPT,
    CHAT_NSFW_BLOCK_ON, CHAT_NSFW_BLOCK_OFF,
    LANGUAGE_DIRECTIVES,
)
from utils.db import PostgresDB
from utils.api_client import add_credits


# Chat replies are short — cap output tokens regardless of subscription tier.
CHAT_MAX_TOKENS = 220
# How many last messages to keep in the prompt window.
CHAT_CONTEXT_LIMIT = 25
# Char-cap on history payload. Combined with the bigger chat system prompt
# (~5k chars after the recent overhaul), keeping this at 8000 lets us fit
# easily under the strictest Groq model context limit even with NSFW examples.
CHAT_MAX_HISTORY_CHARS = 8000


class ChatCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # =======================================================================
    # /chat — open the menu
    # =======================================================================
    @app_commands.command(name="chat", description="Text-message style AI chat — pick a persona and SFW/NSFW mode")
    async def chat(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        await self._render_menu(interaction)

    async def _render_menu(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        session = await PostgresDB.get_session(user_id)
        active_chat = session and session.get("session_type") == "chat"
        active_erp = session and session.get("session_type") == "erp"

        embed = discord.Embed(
            title="💬 Chat — Real texting with an AI",
            description=(
                "*Pick someone to text. They'll reply like a real person — "
                "no roleplay narration, just messages.*"
            ),
            color=discord.Color.from_rgb(99, 102, 241)
        )

        if active_chat:
            persona_key = session.get("character")
            persona_label = session.get("character_name", "Unknown")
            mode = "🔥 NSFW" if session.get("chat_nsfw") else "✨ SFW"
            embed.add_field(
                name="🟢 Active chat",
                value=f"Texting with **{persona_label}**  ·  Mode: {mode}\n*Just send a message in DM to continue.*",
                inline=False
            )
        elif active_erp:
            embed.add_field(
                name="⚠️ You have an active ERP session",
                value=f"You're in an `/erp` scene with **{session.get('character_name')}**.\nEnd it first via `/erp` → End Session, then come back here.",
                inline=False
            )

        # Persona summary
        persona_lines = []
        for key, p in CHAT_PERSONAS.items():
            persona_lines.append(f"{p['emoji']} **{p['label']}** ({p['name']}, {p['age']})")
        embed.add_field(
            name="🎭 Available personas",
            value="\n".join(persona_lines),
            inline=False
        )

        embed.set_footer(text="Pick one below — you'll choose SFW or NSFW next")

        view = discord.ui.View(timeout=300)

        if active_chat:
            end_btn = discord.ui.Button(
                label="End chat",
                style=discord.ButtonStyle.danger,
                emoji="⛔",
                row=0
            )
            end_btn.callback = self._end_chat_button
            view.add_item(end_btn)

        # Persona buttons (4 of them, one row)
        if not active_erp:
            for idx, (key, p) in enumerate(CHAT_PERSONAS.items()):
                style = [
                    discord.ButtonStyle.danger,
                    discord.ButtonStyle.success,
                    discord.ButtonStyle.primary,
                    discord.ButtonStyle.secondary,
                ][idx % 4]
                btn = discord.ui.Button(
                    label=p["label"],
                    style=style,
                    emoji=p["emoji"],
                    row=1
                )
                btn.callback = self._make_persona_picker(key)
                view.add_item(btn)

        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    def _make_persona_picker(self, persona_key: str):
        async def callback(interaction: discord.Interaction):
            await self._show_mode_picker(interaction, persona_key)
        return callback

    async def _show_mode_picker(self, interaction: discord.Interaction, persona_key: str):
        persona = CHAT_PERSONAS.get(persona_key)
        if persona is None:
            await interaction.response.send_message("Unknown persona.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"{persona['emoji']} Texting with {persona['label']}",
            description=(
                f"*{persona['name']}, age {persona['age']}.*\n\n"
                f"Pick a conversation mode :"
            ),
            color=discord.Color.from_rgb(99, 102, 241)
        )
        embed.add_field(
            name="✨ SFW",
            value="Friendly, lightly flirty, no explicit content. Safe for any context.",
            inline=False
        )
        embed.add_field(
            name="🔥 NSFW",
            value="Open to flirting, sexting, explicit conversation. Adult content allowed.",
            inline=False
        )

        view = discord.ui.View(timeout=300)
        sfw_btn = discord.ui.Button(label="SFW", style=discord.ButtonStyle.success, emoji="✨", row=0)
        sfw_btn.callback = self._make_mode_picker(persona_key, False)
        view.add_item(sfw_btn)

        nsfw_btn = discord.ui.Button(label="NSFW", style=discord.ButtonStyle.danger, emoji="🔥", row=0)
        nsfw_btn.callback = self._make_mode_picker(persona_key, True)
        view.add_item(nsfw_btn)

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    def _make_mode_picker(self, persona_key: str, nsfw: bool):
        async def callback(interaction: discord.Interaction):
            await self._start_chat(interaction, persona_key, nsfw)
        return callback

    async def _start_chat(self, interaction: discord.Interaction, persona_key: str, nsfw: bool):
        await interaction.response.defer(thinking=True, ephemeral=True)
        user_id = interaction.user.id
        persona = CHAT_PERSONAS.get(persona_key)
        if persona is None:
            await interaction.followup.send("Unknown persona.", ephemeral=True)
            return

        # Refuse if there's an active ERP session — they have to end it first.
        existing = await PostgresDB.get_session(user_id)
        if existing and existing.get("session_type") == "erp":
            await interaction.followup.send(
                "❌ You have an active `/erp` scene. End it via `/erp` → End Session before starting a chat.",
                ephemeral=True
            )
            return

        # Check daily session quota (shared with ERP for fairness)
        if not await PostgresDB.can_start_session(user_id):
            limits = await PostgresDB.get_limits(user_id)
            await interaction.followup.send(
                f"❌ Daily session limit reached "
                f"({'unlimited' if limits['daily_sessions'] == -1 else limits['daily_sessions']}/day). "
                f"Try again tomorrow or use `/premium` to upgrade.",
                ephemeral=True
            )
            return

        session = {
            "character": persona_key,
            "character_name": persona["label"],
            "messages": [],
            "session_type": "chat",
            "chat_nsfw": nsfw,
        }
        await PostgresDB.set_session(user_id, session)
        await PostgresDB.increment_sessions(user_id)

        mode_label = "🔥 NSFW" if nsfw else "✨ SFW"
        embed = discord.Embed(
            title=f"💬 Now texting with {persona['label']} {persona['emoji']}",
            description=(
                f"*{persona['name']}, {persona['age']}.* Mode: **{mode_label}**\n\n"
                f"Just send a message in this DM — she'll reply like a real person.\n"
                f"Use `/chat` → End chat anytime to stop.\n"
                f"Switch to `/erp` for narrative roleplay (you'll need to end this chat first)."
            ),
            color=discord.Color.from_rgb(99, 102, 241)
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    async def _end_chat_button(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)
        user_id = interaction.user.id
        session = await PostgresDB.get_session(user_id)
        if not session or session.get("session_type") != "chat":
            await interaction.followup.send("❌ You don't have an active chat.", ephemeral=True)
            return

        persona_label = session.get("character_name", "Unknown")
        await PostgresDB.delete_session(user_id)

        embed = discord.Embed(
            title="💤 Chat ended",
            description=f"You stopped texting with **{persona_label}**. Use `/chat` to start again anytime.",
            color=discord.Color.from_rgb(99, 102, 241)
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    # =======================================================================
    # DM message handling
    # =======================================================================
    async def handle_dm_message(self, message: discord.Message) -> bool:
        """
        Returns True if this message was handled (i.e., active chat session
        existed and we replied or deferred), False if the user has no active
        chat session and the dispatcher should try the next handler (ERP).
        """
        user_id = message.author.id

        if message.content == "" or message.content is None:
            # Same intent-disabled diagnostic the ERP cog does.
            return False  # let ERP cog handle the diagnostic message

        if message.content.startswith("/"):
            return False

        session = await PostgresDB.get_session(user_id)
        if not session or session.get("session_type") != "chat":
            return False

        print(f"[DEBUG CHAT] handle_dm_message for {user_id} | persona={session.get('character')} | nsfw={session.get('chat_nsfw')}")

        if not await PostgresDB.can_send_message(user_id):
            limits = await PostgresDB.get_limits(user_id)
            await message.channel.send(
                f"❌ Daily message limit reached "
                f"({'unlimited' if limits['daily_msgs'] == -1 else limits['daily_msgs']}/day). "
                f"Try again tomorrow or use `/premium` to upgrade."
            )
            return True

        persona_key = session.get("character")
        persona = CHAT_PERSONAS.get(persona_key)
        if persona is None:
            await message.channel.send("❌ This chat persona no longer exists. Use `/chat` to pick another.")
            return True

        # Append user's message
        session["messages"].append({"role": "user", "content": message.content})
        await PostgresDB.set_session(user_id, session)

        # Build prompt
        user_profile = await PostgresDB.get_profile(user_id)
        lang_code = (user_profile or {}).get("language") or "auto"
        if lang_code not in LANGUAGE_DIRECTIVES:
            lang_code = "auto"
        language_directive = LANGUAGE_DIRECTIVES[lang_code]
        nsfw_block = CHAT_NSFW_BLOCK_ON if session.get("chat_nsfw") else CHAT_NSFW_BLOCK_OFF

        system_content = CHAT_SYSTEM_PROMPT.format(
            persona_label=persona["label"],
            persona_name=persona["name"],
            persona_age=persona["age"],
            persona_personality=persona["personality"],
            language_directive=language_directive,
            nsfw_block=nsfw_block,
        )
        messages_payload = [{"role": "system", "content": system_content}]

        # Trim history to fit
        history = list(session["messages"][-CHAT_CONTEXT_LIMIT:])
        total_chars = sum(len(m.get("content", "")) for m in history)
        while total_chars > CHAT_MAX_HISTORY_CHARS and len(history) > 1:
            removed = history.pop(0)
            total_chars -= len(removed.get("content", ""))
        for entry in history:
            messages_payload.append({"role": entry["role"], "content": entry["content"]})

        limits = await PostgresDB.get_limits(user_id)
        sub_type = limits["type"]

        # Use the ERP cog's queue if available — same provider, shared priority.
        erp_cog = self.bot.get_cog("ERPCog")
        if erp_cog is None or not hasattr(erp_cog, "ai_queue"):
            await message.channel.send("⚠️ The AI is not ready right now. Try again in a moment.")
            return True

        async with message.channel.typing():
            try:
                # Lower temperature than ERP (0.75 vs 0.95) — chat needs
                # coherence over creativity, and high temp made the model
                # spiral into looped sex-bot lines.
                # disable_refusal_retry=True because the FORCING_PREFIX is
                # narrative ("*Her eyes lock onto yours*") — it would derail
                # a chat conversation. We trust the model's first reply
                # whatever it is — soft deflections are valid in-character
                # for chat.
                ai_response = await erp_cog.ai_queue.enqueue(
                    messages_payload, 0.75, CHAT_MAX_TOKENS, user_id, sub_type,
                    disable_refusal_retry=True,
                )
            except Exception as e:
                print(f"[CHAT] AI request failed: {e}")
                await message.channel.send("⚠️ The AI is taking too long. Try again in a moment.")
                return True

        # Detect the LLM fallback tag — means every provider/model failed
        # or refused. Surface a real error to the user instead of pretending
        # the persona just hesitated.
        if ai_response.startswith("[LLM_FALLBACK]"):
            print(f"[CHAT] All LLM providers failed for user {user_id}. Last user msg: {message.content[:80]!r}")
            await message.channel.send(
                "⚠️ All AI providers are currently rate-limited or refusing this prompt. "
                "Try again in 30 seconds, or rephrase your message. "
                "If this keeps happening, the bot operator should check Render logs."
            )
            return True

        # Strip residual asterisks the model sometimes adds anyway, since
        # chat shouldn't have any narration.
        ai_response = self._strip_chat_narration(ai_response)
        if not ai_response:
            ai_response = "..."

        session["messages"].append({"role": "assistant", "content": ai_response})
        await PostgresDB.set_session(user_id, session)
        await PostgresDB.increment_messages(user_id)

        await self._send_chat(message.channel, ai_response)
        # Streak update (re-uses ERP cog's helper if present)
        if hasattr(erp_cog, "_handle_streak"):
            asyncio.create_task(erp_cog._handle_streak(message, user_id, user_profile))
        return True

    @staticmethod
    def _strip_chat_narration(text: str) -> str:
        """Remove leftover *action* blocks the model may have inserted."""
        if not text:
            return text
        import re
        # Drop *anything* between asterisks (action narration)
        cleaned = re.sub(r"\*[^*]+\*", "", text)
        # Collapse multiple spaces / blank lines
        cleaned = re.sub(r"[ \t]+", " ", cleaned)
        cleaned = re.sub(r"\n{2,}", "\n", cleaned)
        return cleaned.strip()

    @staticmethod
    async def _send_chat(channel, text: str):
        """Send chat message — split if it ever exceeds Discord's 2000 char cap."""
        MAX_LENGTH = 2000
        if len(text) <= MAX_LENGTH:
            await channel.send(text)
            return
        # Defensive split (chat replies should never be this long, but just in case)
        for i in range(0, len(text), MAX_LENGTH):
            await channel.send(text[i:i + MAX_LENGTH])


async def setup(bot: commands.Bot):
    await bot.add_cog(ChatCog(bot))
