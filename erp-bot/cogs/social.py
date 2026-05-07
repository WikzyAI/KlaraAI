"""
Social Cog — referral + memories management.
Both commands are button-driven, matching the rest of the bot.
"""
import asyncio
import traceback
import discord
from discord import app_commands
from discord.ext import commands

from utils.db import PostgresDB
from utils.api_client import add_credits, set_referrer

# How many credits each side gets. Tuned to keep unit economics positive.
REFEREE_SIGNUP_BONUS = 50      # given to the new user when they apply a code
REFERRER_PURCHASE_BONUS = 200  # given to the referrer once referee buys >= $5
REFERRER_PURCHASE_THRESHOLD = 500  # in credits ($5 worth)


class SocialCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ============================================================
    # /referral
    # ============================================================
    @app_commands.command(name="referral", description="Get your referral code & invite friends")
    async def referral(self, interaction: discord.Interaction):
        await self._render_referral(interaction)

    async def _render_referral(self, interaction: discord.Interaction):
        try:
            if not interaction.response.is_done():
                await interaction.response.defer(thinking=True)

            user_id = interaction.user.id
            code = await PostgresDB.get_or_create_referral_code(user_id)
            stats = await PostgresDB.get_referral_stats(user_id)
            already_used = await PostgresDB.has_used_referral(user_id)

            embed = discord.Embed(
                title="✦ Your Referral Code ✦",
                description=(
                    f"Share your code — when a friend uses it and makes a purchase of "
                    f"`$5+`, **you both win**.\n\n"
                    f"**Your code:** `{code}`"
                ),
                color=discord.Color.from_rgb(232, 67, 147)
            )
            embed.add_field(
                name="🎁 Rewards",
                value=(
                    f"› They get **+{REFEREE_SIGNUP_BONUS} credits** the moment they apply your code\n"
                    f"› You get **+{REFERRER_PURCHASE_BONUS} credits** when they spend `$5+`"
                ),
                inline=False
            )
            embed.add_field(
                name="📊 Your Stats",
                value=(
                    f"Friends invited: **{stats['total']}**\n"
                    f"Converted (paid): **{stats['converted']}**\n"
                    f"Total earned: **{stats['converted'] * REFERRER_PURCHASE_BONUS}** credits"
                ),
                inline=False
            )
            if not already_used:
                embed.add_field(
                    name="💡 Got a code from a friend?",
                    value="Tap **Apply Code** below to claim your bonus.",
                    inline=False
                )
            embed.set_footer(text="One referral per new user. Self-referrals don't count.")

            view = discord.ui.View(timeout=300)
            if not already_used:
                apply_btn = discord.ui.Button(
                    label="Apply a Code",
                    style=discord.ButtonStyle.primary,
                    emoji="🎟️"
                )
                apply_btn.callback = self._open_apply_modal
                view.add_item(apply_btn)

            buy_btn = discord.ui.Button(
                label="Buy Credits",
                style=discord.ButtonStyle.link,
                emoji="💎",
                url="https://klaraai.vercel.app/buy-credits.html"
            )
            view.add_item(buy_btn)

            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        except Exception as e:
            print(f"[Referral] ERROR: {e}")
            traceback.print_exc()
            try:
                await interaction.followup.send("An error occurred.", ephemeral=True)
            except Exception:
                pass

    async def _open_apply_modal(self, interaction: discord.Interaction):
        modal = ApplyReferralModal(self)
        await interaction.response.send_modal(modal)

    async def apply_referral_code(self, interaction: discord.Interaction, code: str):
        """Logic to apply a referral code. Defers and replies ephemerally."""
        await interaction.response.defer(thinking=True, ephemeral=True)
        code = (code or "").strip().upper().replace(" ", "")
        if not code or len(code) < 4 or len(code) > 12:
            await interaction.followup.send("❌ Invalid code format.", ephemeral=True)
            return

        user_id = interaction.user.id
        if await PostgresDB.has_used_referral(user_id):
            await interaction.followup.send(
                "❌ You've already used a referral code. Only one per account.",
                ephemeral=True
            )
            return

        referrer_id = await PostgresDB.get_referrer_by_code(code)
        if referrer_id is None:
            await interaction.followup.send("❌ This code doesn't exist.", ephemeral=True)
            return
        if int(referrer_id) == int(user_id):
            await interaction.followup.send("❌ You can't refer yourself, smart guy.", ephemeral=True)
            return

        recorded = await PostgresDB.record_referral(user_id, referrer_id, code)
        if not recorded:
            await interaction.followup.send(
                "❌ Could not register your referral. Try again.", ephemeral=True
            )
            return

        # Tell the API about the referral so the webhook can reward the referrer
        # automatically on the user's first qualifying purchase.
        try:
            await asyncio.to_thread(set_referrer, str(user_id), str(referrer_id))
        except Exception as e:
            print(f"[Referral] set_referrer API call failed: {e}")

        # Grant the signup bonus to the referee right away
        username = interaction.user.name
        result = await asyncio.to_thread(
            add_credits, str(user_id), REFEREE_SIGNUP_BONUS, username,
            f"Referral signup bonus (code {code})"
        )
        if result.get("success", False):
            await PostgresDB.mark_signup_bonus_granted(user_id)
            embed = discord.Embed(
                title="🎉 Code applied!",
                description=(
                    f"You just earned **+{REFEREE_SIGNUP_BONUS} credits**.\n"
                    f"When you make a purchase of `$5+`, your referrer also gets a reward."
                ),
                color=discord.Color.from_rgb(46, 204, 113)
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send(
                "⚠️ Code applied but the credit grant failed. Contact support.",
                ephemeral=True
            )

    # ============================================================
    # /memories
    # ============================================================
    @app_commands.command(name="memories", description="View what your characters remember about you")
    async def memories(self, interaction: discord.Interaction):
        await self._render_memories(interaction)

    async def _render_memories(self, interaction: discord.Interaction):
        try:
            if not interaction.response.is_done():
                await interaction.response.defer(thinking=True, ephemeral=True)

            user_id = interaction.user.id
            grouped = await PostgresDB.get_all_memories_grouped(user_id)
            characters = await PostgresDB.get_all_characters()

            embed = discord.Embed(
                title="💭 Long-term Memories",
                description=(
                    "*Each of your companions builds a private memory of your sessions.*\n"
                    "These memories are injected at the start of every new scene to keep the "
                    "story consistent and intimate."
                ),
                color=discord.Color.from_rgb(155, 89, 182)
            )

            if not grouped:
                embed.add_field(
                    name="No memories yet",
                    value=(
                        "Memories are saved automatically when you end a scene with `/erp` → "
                        "**End Session**. Make sure your scene has at least a few exchanges."
                    ),
                    inline=False
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            for char_key, items in grouped.items():
                char_name = characters.get(char_key, {}).get("name", char_key)
                shown = items[:8]
                bullets = "\n".join(f"• {m['content']}" for m in shown)
                if len(items) > 8:
                    bullets += f"\n*…and {len(items) - 8} more*"
                embed.add_field(
                    name=f"💋 {char_name}  ·  {len(items)} memories",
                    value=bullets[:1024] or "*(empty)*",
                    inline=False
                )

            embed.set_footer(text="Use the buttons below to wipe memories per character or all.")

            view = discord.ui.View(timeout=300)
            for idx, char_key in enumerate(list(grouped.keys())[:4]):
                char_name = characters.get(char_key, {}).get("name", char_key)
                btn = discord.ui.Button(
                    label=f"Forget {char_name}",
                    style=discord.ButtonStyle.secondary,
                    emoji="🧹",
                    row=idx // 2
                )
                btn.callback = lambda i, k=char_key, n=char_name: self._wipe_character_memories(i, k, n)
                view.add_item(btn)

            wipe_all = discord.ui.Button(
                label="Forget Everything",
                style=discord.ButtonStyle.danger,
                emoji="🗑️",
                row=2
            )
            wipe_all.callback = self._wipe_all_memories
            view.add_item(wipe_all)

            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        except Exception as e:
            print(f"[Memories] ERROR: {e}")
            traceback.print_exc()
            try:
                await interaction.followup.send("An error occurred.", ephemeral=True)
            except Exception:
                pass

    async def _wipe_character_memories(self, interaction: discord.Interaction,
                                       char_key: str, char_name: str):
        await interaction.response.defer(thinking=True, ephemeral=True)
        deleted = await PostgresDB.clear_memories(interaction.user.id, char_key)
        await interaction.followup.send(
            f"🧹 Wiped **{deleted}** memories with **{char_name}**.",
            ephemeral=True
        )

    async def _wipe_all_memories(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)
        deleted = await PostgresDB.clear_memories(interaction.user.id)
        await interaction.followup.send(
            f"🗑️ Wiped **{deleted}** memories across all characters.",
            ephemeral=True
        )


class ApplyReferralModal(discord.ui.Modal):
    def __init__(self, cog: SocialCog):
        super().__init__(title="Apply a referral code")
        self.cog = cog
        self.code_input = discord.ui.TextInput(
            label="Code",
            placeholder="e.g. KLARA1",
            min_length=4,
            max_length=12,
            required=True
        )
        self.add_item(self.code_input)

    async def on_submit(self, interaction: discord.Interaction):
        await self.cog.apply_referral_code(interaction, self.code_input.value)


async def setup(bot: commands.Bot):
    await bot.add_cog(SocialCog(bot))
