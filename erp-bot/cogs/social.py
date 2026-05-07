"""
Social Cog — referral + memories management.
Both commands are button-driven, matching the rest of the bot.
"""
import asyncio
import traceback
from datetime import datetime, timezone
import discord
from discord import app_commands
from discord.ext import commands

from utils.db import PostgresDB
from utils.api_client import add_credits, set_referrer

# Tuned to keep unit economics positive AND deter sock-puppet farming.
REFEREE_SIGNUP_BONUS = 25                # credits, granted only AFTER the gate
REFEREE_ACTIVITY_GATE = 5                # ERP messages required before signup bonus
REFERRER_PURCHASE_BONUS = 200            # credits, on first $5+ purchase by referee
REFERRER_PURCHASE_THRESHOLD = 500        # in credits ($5 worth)
MIN_DISCORD_ACCOUNT_AGE_DAYS = 14        # block fresh sock-puppets
MAX_REFERRALS_PER_CODE = 100             # lifetime cap per referrer


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
                    f"Share your code — invite real friends, earn credits when they "
                    f"actually use the bot.\n\n"
                    f"**Your code:** `{code}`"
                ),
                color=discord.Color.from_rgb(232, 67, 147)
            )
            embed.add_field(
                name="🎁 Rewards",
                value=(
                    f"› They get **+{REFEREE_SIGNUP_BONUS} credits** "
                    f"after sending {REFEREE_ACTIVITY_GATE} messages in `/erp`\n"
                    f"› You get **+{REFERRER_PURCHASE_BONUS} credits** when they spend `$5+`"
                ),
                inline=False
            )
            embed.add_field(
                name="🛡️ Anti-fraud",
                value=(
                    f"› Referee's Discord account must be **≥{MIN_DISCORD_ACCOUNT_AGE_DAYS} days old**\n"
                    f"› One code per new user · Self-referrals blocked\n"
                    f"› Lifetime cap: **{MAX_REFERRALS_PER_CODE}** uses per code"
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
                url="https://klaraai.vercel.app/buy-credits"
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

        # Anti-fraud #1: Discord account age must be ≥ MIN_DISCORD_ACCOUNT_AGE_DAYS.
        try:
            account_age = datetime.now(timezone.utc) - interaction.user.created_at
            if account_age.days < MIN_DISCORD_ACCOUNT_AGE_DAYS:
                await interaction.followup.send(
                    f"❌ Your Discord account must be at least "
                    f"**{MIN_DISCORD_ACCOUNT_AGE_DAYS} days old** to use a referral code.\n"
                    f"*(Current age: {account_age.days} day{'s' if account_age.days != 1 else ''}.)*",
                    ephemeral=True
                )
                return
        except Exception as e:
            print(f"[Referral] Age check failed: {e}")

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

        # Anti-fraud #2: per-code lifetime cap.
        ref_stats = await PostgresDB.get_referral_stats(referrer_id)
        if ref_stats["total"] >= MAX_REFERRALS_PER_CODE:
            await interaction.followup.send(
                f"❌ This code has reached its limit of **{MAX_REFERRALS_PER_CODE}** uses.",
                ephemeral=True
            )
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

        # Anti-fraud #3: signup bonus is GATED behind {REFEREE_ACTIVITY_GATE} ERP
        # messages. We only record the link here; the bonus is granted later
        # from the ERP cog when the user actually engages.
        embed = discord.Embed(
            title="🎟️ Code linked",
            description=(
                f"Your referral is registered.\n\n"
                f"› Send **{REFEREE_ACTIVITY_GATE} messages in `/erp`** and you'll receive "
                f"**+{REFEREE_SIGNUP_BONUS} credits**.\n"
                f"› When you spend `$5+`, your referrer also gets a reward."
            ),
            color=discord.Color.from_rgb(46, 204, 113)
        )
        embed.set_footer(text="The bonus is delivered automatically after activity.")
        await interaction.followup.send(embed=embed, ephemeral=True)

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
