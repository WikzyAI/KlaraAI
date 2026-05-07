"""
Profile Cog - User profile management.
"""
import discord
from discord import app_commands
from discord.ext import commands
from utils.db import PostgresDB
from utils.api_client import get_credits
import config
import asyncio
import traceback


class ProfileCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="profile", description="View or update your profile")
    @app_commands.describe(
        name="Your name or nickname",
        age="Your age (must be >= 18)",
        description="A description of yourself (appearance, personality, etc.)"
    )
    async def profile(self, interaction: discord.Interaction,
                     name: str = None,
                     age: int = None,
                     description: str = None):
        try:
            await interaction.response.defer(thinking=True)

            user_id = interaction.user.id

            profile = await asyncio.wait_for(
                PostgresDB.get_profile(user_id), timeout=10.0
            )

            if name is None and age is None and description is None:
                credits = None
                try:
                    credits_data = await asyncio.wait_for(
                        asyncio.to_thread(get_credits, str(user_id)),
                        timeout=10.0
                    )
                    credits = credits_data.get("credits", 0)
                except Exception as e:
                    print(f"[Profile] Credits fetch failed: {e}")

                embed = await self._build_profile_embed_async(interaction.user, profile, credits=credits)

                view = discord.ui.View(timeout=300)

                edit_btn = discord.ui.Button(
                    label="Edit Profile",
                    style=discord.ButtonStyle.primary,
                    emoji="✏️",
                    row=0
                )
                edit_btn.callback = lambda i: self._edit_profile_modal(i)
                view.add_item(edit_btn)

                settings_btn = discord.ui.Button(
                    label="Settings",
                    style=discord.ButtonStyle.secondary,
                    emoji="⚙️",
                    row=0
                )
                settings_btn.callback = self._render_settings
                view.add_item(settings_btn)

                if profile.get("sub_type", "free") != "free":
                    create_btn = discord.ui.Button(
                        label="Create Character",
                        style=discord.ButtonStyle.success,
                        emoji="✨",
                        row=0
                    )
                    create_btn.callback = self._create_character_start
                    view.add_item(create_btn)

                buy_btn = discord.ui.Button(
                    label="Buy Credits",
                    style=discord.ButtonStyle.link,
                    emoji="💎",
                    url="https://klaraai.vercel.app/buy-credits.html",
                    row=1
                )
                view.add_item(buy_btn)

                await interaction.followup.send(embed=embed, view=view)
                return

            if age is not None and age < 18:
                await interaction.followup.send("You must be at least 18 years old to use this bot.", ephemeral=True)
                return

            updates = {}
            if name is not None:
                updates["name"] = name
            if age is not None:
                updates["age"] = age
            if description is not None:
                updates["description"] = description

            profile = await asyncio.wait_for(
                PostgresDB.update_profile(user_id, **updates),
                timeout=10.0
            )

            credits = None
            try:
                credits_data = await asyncio.wait_for(
                    asyncio.to_thread(get_credits, str(user_id)),
                    timeout=10.0
                )
                credits = credits_data.get("credits", 0)
            except Exception as e:
                print(f"[Profile] Credits fetch failed: {e}")

            try:
                streak_info = await asyncio.wait_for(
                    PostgresDB.get_streak(interaction.user.id), timeout=5.0
                )
            except Exception:
                streak_info = None
            embed = discord.Embed(
                title="✅ Profile Updated",
                description="Your profile has been saved.",
                color=discord.Color.from_rgb(46, 204, 113)
            )
            embed = self._build_profile_embed(interaction.user, profile, credits=credits, embed=embed, streak_info=streak_info)
            await interaction.followup.send(embed=embed)

        except Exception as e:
            print(f"[Profile] ERROR: {type(e).__name__}: {e}")
            traceback.print_exc()
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("An error occurred. Please try again.", ephemeral=True)
                else:
                    await interaction.followup.send("An error occurred. Please try again.", ephemeral=True)
            except Exception:
                pass

    async def _edit_profile_modal(self, interaction: discord.Interaction):
        """Open a modal to edit name, age, description."""
        modal = ProfileEditModal(self)
        await interaction.response.send_modal(modal)

    async def _build_profile_embed_async(self, user: discord.User, profile: dict, credits: int = None) -> discord.Embed:
        """Async wrapper that also pulls streak info before building the embed."""
        try:
            streak_info = await asyncio.wait_for(
                PostgresDB.get_streak(user.id), timeout=5.0
            )
        except Exception as e:
            print(f"[Profile] Streak fetch failed: {e}")
            streak_info = {"streak": 0, "max": 0, "active": False}
        return self._build_profile_embed(user, profile, credits=credits, streak_info=streak_info)

    def _build_profile_embed(self, user: discord.User, profile: dict, credits: int = None, embed: discord.Embed = None, streak_info: dict = None) -> discord.Embed:
        sub_type = profile.get("sub_type", "free")
        sub_info = config.SUBSCRIPTIONS.get(sub_type, config.SUBSCRIPTIONS["free"])
        sub_name = sub_info["name"]
        sub_emoji = {"free": "🌿", "standard": "💎", "premium": "👑"}.get(sub_type, "✨")
        accent = {"free": 0x95a5a6, "standard": 0x9b59b6, "premium": 0xf1c40f}.get(sub_type, 0x9b59b6)

        if embed is None:
            embed = discord.Embed(
                title=f"✦ {user.name}'s Profile ✦",
                color=accent
            )

        try:
            avatar_url = user.display_avatar.url
            embed.set_thumbnail(url=avatar_url)
        except Exception:
            pass

        response_length = profile.get("response_length", "short")
        length_names = {
            "short": "Short (1-2 paragraphs)",
            "medium": "Medium (2-4 paragraphs)",
            "long": "Long (4-6 paragraphs)",
        }

        embed.add_field(name="👤 Name", value=profile.get("name") or "*Not set*", inline=True)
        embed.add_field(name="🎂 Age", value=str(profile.get("age")) if profile.get("age") else "*Not set*", inline=True)
        embed.add_field(name=f"{sub_emoji} Plan", value=f"**{sub_name}**", inline=True)

        credits_value = credits if credits is not None else 0
        embed.add_field(
            name="💰 Credits",
            value=f"**{credits_value}** credits  ·  *${credits_value/100:.2f}*",
            inline=True
        )
        embed.add_field(
            name="📏 Response Length",
            value=length_names.get(response_length, response_length),
            inline=True
        )
        embed.add_field(name="​", value="​", inline=True)  # spacer

        # Daily quota with exact reset countdown (skipped only when both
        # messages AND sessions are unlimited, e.g. Premium).
        quota_value = self._build_quota_value(profile, sub_info)
        if quota_value:
            embed.add_field(name="⏳ Daily Quota", value=quota_value, inline=False)

        # Streak display — always shown so users discover the system.
        if streak_info is not None:
            streak = streak_info.get("streak", 0)
            best = streak_info.get("max", 0)
            active = streak_info.get("active", False)

            if streak >= 1 and active:
                fire = "🔥" * min(streak // 7 + 1, 5)
                streak_text = f"{fire} Current: **{streak} day{'s' if streak != 1 else ''}**"
                if best > streak:
                    streak_text += f"  ·  Best: **{best}**"
                if streak < 30:
                    next_milestones = [3, 7, 14, 30]
                    next_target = next((n for n in next_milestones if n > streak), None)
                    if next_target:
                        rewards = {3: 3, 7: 10, 14: 20, 30: 50}
                        streak_text += f"\n*Next reward: **+{rewards[next_target]} credits** at day {next_target}*"
                else:
                    streak_text += "\n*+15 credits every 7 days from here on*"
            elif best >= 1:
                streak_text = (
                    f"💤 Current: **0 days**  ·  Best ever: **{best}**\n"
                    f"*Send a message in `/erp` today to start a new streak.*"
                )
            else:
                streak_text = (
                    "💤 No streak yet.\n"
                    "*Chat in `/erp` daily to build one — rewards at day **3, 7, 14, 30**.*"
                )

            embed.add_field(name="🔥 Streak", value=streak_text, inline=False)

        desc = profile.get("description")
        embed.add_field(
            name="📝 Description",
            value=desc[:1024] if desc else "*No description set yet — click 'Edit Profile' below.*",
            inline=False
        )

        embed.set_footer(text="Edit your profile or buy credits below ↓")
        return embed

    @staticmethod
    def _build_quota_value(profile: dict, sub_info: dict) -> str:
        msg_limit = sub_info["daily_msgs"]
        sess_limit = sub_info["daily_sessions"]
        if msg_limit == -1 and sess_limit == -1:
            return ""

        msgs_used = profile.get("daily_msgs_used", 0)
        sess_used = profile.get("daily_sessions_used", 0)

        msgs_line = (
            f"💬 Messages: `{msgs_used}/∞`" if msg_limit == -1
            else f"💬 Messages: `{msgs_used}/{msg_limit}`"
        )
        sess_line = (
            f"🎬 Sessions: `{sess_used}/∞`" if sess_limit == -1
            else f"🎬 Sessions: `{sess_used}/{sess_limit}`"
        )

        reset_at = PostgresDB.get_reset_at(profile)
        if reset_at is None:
            reset_line = "🔄 Window not started yet — full quota available."
        else:
            ts = int(reset_at.timestamp())
            reset_line = f"🔄 Resets <t:{ts}:R> *(at <t:{ts}:t>)*"

        return f"{msgs_line}\n{sess_line}\n{reset_line}"

    @app_commands.command(name="settings", description="Configure bot settings (response length, custom characters)")
    async def settings(self, interaction: discord.Interaction):
        await self._render_settings(interaction)

    async def _render_settings(self, interaction: discord.Interaction):
        try:
            if not interaction.response.is_done():
                await interaction.response.defer(thinking=True)

            user_id = interaction.user.id
            profile = await asyncio.wait_for(
                PostgresDB.get_profile(user_id), timeout=10.0
            )
            limits = await asyncio.wait_for(
                PostgresDB.get_limits(user_id), timeout=10.0
            )

            print(f"[Settings] User {user_id} - sub_type={profile.get('sub_type')} - allowed_lengths={limits.get('allowed_lengths')}")

            current_length = profile.get("response_length", "short")
            length_names = {
                "short": "Short (1-2 paragraphs)",
                "medium": "Medium (2-4 paragraphs)",
                "long": "Long (4-6 paragraphs)",
            }
            allowed_lengths = limits.get("allowed_lengths", ["short"])
            custom_chars_allowed = limits["custom_chars"]

            embed = discord.Embed(
                title="⚙️ Settings",
                description="*Tune your experience.* Pick a response length below.",
                color=discord.Color.from_rgb(155, 89, 182)
            )
            embed.add_field(
                name="📏 Current Length",
                value=f"**{length_names.get(current_length, current_length)}**",
                inline=False
            )
            embed.add_field(
                name="🎭 Custom Characters",
                value="Unlimited" if custom_chars_allowed == -1 else f"{custom_chars_allowed} max",
                inline=True
            )
            embed.add_field(
                name="✅ Unlocked Lengths",
                value=", ".join([l.capitalize() for l in allowed_lengths]),
                inline=True
            )

            view = discord.ui.View(timeout=300)

            length_emojis = {"short": "📝", "medium": "📄", "long": "📜"}
            for length in ["short", "medium", "long"]:
                if length in allowed_lengths:
                    is_current = current_length == length
                    btn = discord.ui.Button(
                        label=length.capitalize() + (" ✓" if is_current else ""),
                        style=discord.ButtonStyle.success if is_current else discord.ButtonStyle.secondary,
                        emoji=length_emojis[length],
                        row=0,
                        disabled=is_current
                    )
                    btn.callback = lambda i, l=length: self._set_response_length(i, l)
                    view.add_item(btn)

            create_btn = discord.ui.Button(
                label="Create Character",
                style=discord.ButtonStyle.primary,
                emoji="✨",
                row=1
            )
            create_btn.callback = self._create_character_start
            view.add_item(create_btn)

            await interaction.followup.send(embed=embed, view=view)

        except Exception as e:
            print(f"[Settings] ERROR: {type(e).__name__}: {e}")
            traceback.print_exc()
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("An error occurred. Please try again.", ephemeral=True)
                else:
                    await interaction.followup.send("An error occurred. Please try again.", ephemeral=True)
            except Exception:
                pass

    async def _set_response_length(self, interaction: discord.Interaction, length: str):
        try:
            await interaction.response.defer(thinking=True)
            user_id = interaction.user.id

            limits = await asyncio.wait_for(
                PostgresDB.get_limits(user_id), timeout=10.0
            )
            allowed_lengths = limits.get("allowed_lengths", ["short"])

            if length not in allowed_lengths:
                await interaction.followup.send(f"Your subscription doesn't allow **{length}** responses.", ephemeral=True)
                return

            await asyncio.wait_for(
                PostgresDB.update_profile(user_id, response_length=length),
                timeout=10.0
            )
            length_names = {"short": "Short (1-2 paragraphs)", "medium": "Medium (2-4 paragraphs)", "long": "Long (4-6 paragraphs)"}
            embed = discord.Embed(
                title="Setting Updated",
                description=f"Response length set to: **{length_names.get(length, length)}**",
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            print(f"[Settings] _set_response_length ERROR: {e}")
            traceback.print_exc()
            try:
                await interaction.followup.send("An error occurred.", ephemeral=True)
            except Exception:
                pass

    async def _create_character_start(self, interaction: discord.Interaction):
        try:
            profile = await asyncio.wait_for(
                PostgresDB.get_profile(interaction.user.id), timeout=10.0
            )
            limits = await asyncio.wait_for(
                PostgresDB.get_limits(interaction.user.id), timeout=10.0
            )
            custom_chars_allowed = limits["custom_chars"]

            if custom_chars_allowed == 0:
                await interaction.response.send_message("This feature requires **Standard** or **Premium** subscription.", ephemeral=True)
                return

            if custom_chars_allowed != -1:
                characters = await asyncio.wait_for(
                    PostgresDB.get_all_characters(), timeout=10.0
                )
                user_chars = [k for k, v in characters.items() if v.get("creator") == str(interaction.user.id)]
                if len(user_chars) >= custom_chars_allowed:
                    await interaction.response.send_message(f"Limit of {custom_chars_allowed} custom characters reached.", ephemeral=True)
                    return

            from cogs.erp import CharacterCreateModal
            modal = CharacterCreateModal()
            await interaction.response.send_modal(modal)
        except Exception as e:
            print(f"[Settings] _create_character_start ERROR: {e}")
            traceback.print_exc()
            try:
                await interaction.response.send_message("An error occurred.", ephemeral=True)
            except Exception:
                pass


class ProfileEditModal(discord.ui.Modal):
    def __init__(self, cog):
        super().__init__(title="Edit Profile")
        self.cog = cog

        self.name_input = discord.ui.TextInput(
            label="Name / Nickname",
            placeholder="Enter your name...",
            max_length=50,
            required=False
        )
        self.add_item(self.name_input)

        self.age_input = discord.ui.TextInput(
            label="Age (must be >= 18)",
            placeholder="Enter your age...",
            max_length=3,
            required=False
        )
        self.add_item(self.age_input)

        self.desc_input = discord.ui.TextInput(
            label="Description",
            placeholder="Describe yourself (appearance, personality, etc.)...",
            style=discord.TextStyle.long,
            max_length=1000,
            required=False
        )
        self.add_item(self.desc_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(thinking=True)

            updates = {}
            if self.name_input.value:
                updates["name"] = self.name_input.value
            if self.age_input.value:
                try:
                    age = int(self.age_input.value)
                    if age < 18:
                        await interaction.followup.send("You must be at least 18 years old.", ephemeral=True)
                        return
                    updates["age"] = age
                except ValueError:
                    await interaction.followup.send("Invalid age. Please enter a number.", ephemeral=True)
                    return
            if self.desc_input.value:
                updates["description"] = self.desc_input.value

            if not updates:
                await interaction.followup.send("No changes made.", ephemeral=True)
                return

            profile = await asyncio.wait_for(
                PostgresDB.update_profile(interaction.user.id, **updates),
                timeout=10.0
            )

            credits = None
            try:
                credits_data = await asyncio.wait_for(
                    asyncio.to_thread(get_credits, str(interaction.user.id)),
                    timeout=10.0
                )
                credits = credits_data.get("credits", 0)
            except Exception as e:
                print(f"[ProfileEditModal] Credits fetch failed: {e}")

            try:
                streak_info = await asyncio.wait_for(
                    PostgresDB.get_streak(interaction.user.id), timeout=5.0
                )
            except Exception:
                streak_info = None
            embed = discord.Embed(
                title="✅ Profile Updated",
                description="Your profile has been saved.",
                color=discord.Color.from_rgb(46, 204, 113)
            )
            embed = self.cog._build_profile_embed(interaction.user, profile, credits=credits, embed=embed, streak_info=streak_info)
            await interaction.followup.send(embed=embed)

        except Exception as e:
            print(f"[ProfileEditModal] ERROR: {e}")
            traceback.print_exc()
            try:
                await interaction.followup.send("An error occurred.", ephemeral=True)
            except Exception:
                pass


async def setup(bot: commands.Bot):
    await bot.add_cog(ProfileCog(bot))
