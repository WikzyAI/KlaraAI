"""
Admin Cog — operator-only commands.

Authorization is purely runtime: every command checks
`interaction.user.id in config.ADMIN_USER_IDS`. Admins are configured
via the ADMIN_USER_IDS env var (comma-separated Discord user IDs):

    ADMIN_USER_IDS=926474936518856775

For non-admins, the commands respond with a generic "Unknown command"
ephemeral message and do nothing — they look broken from the outside,
hiding their existence from regular users.

Available commands:
    /admincredits user:<User> amount:<int> [reason:<str>]
        Grant (positive) or revoke (negative) credits.
    /admininfo user:<User>
        Display the user's full state (profile, credits, streak,
        referrals).

For browsing all users with pagination, the operator uses the web
admin panel at /admin (see website/admin.html).
"""
import asyncio
import traceback

import discord
from discord import app_commands
from discord.ext import commands

import config
from utils.db import PostgresDB
from utils.api_client import add_credits, get_credits


def _is_admin(interaction: discord.Interaction) -> bool:
    return int(interaction.user.id) in config.ADMIN_USER_IDS


async def _silent_decline(interaction: discord.Interaction):
    """Pretend the command doesn't exist for non-admins."""
    try:
        await interaction.response.send_message("Unknown command.", ephemeral=True)
    except Exception:
        pass


class AdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ============================================================
    # /admincredits — grant or revoke credits
    # ============================================================
    @app_commands.command(
        name="admincredits",
        description="[ADMIN] Add or remove credits from any user."
    )
    @app_commands.describe(
        user="Target Discord user",
        amount="Credits to add (positive) or remove (negative)",
        reason="Optional note that goes into the credit history",
    )
    async def admincredits(
        self,
        interaction: discord.Interaction,
        user: discord.User,
        amount: int,
        reason: str = "Admin grant",
    ):
        if not _is_admin(interaction):
            return await _silent_decline(interaction)

        await interaction.response.defer(thinking=True, ephemeral=True)

        if amount == 0:
            return await interaction.followup.send("Amount cannot be zero.", ephemeral=True)

        try:
            result = await asyncio.to_thread(
                add_credits, str(user.id), int(amount), user.name, reason or "Admin grant"
            )
        except Exception as e:
            return await interaction.followup.send(
                f"❌ API call failed: `{e}`", ephemeral=True
            )

        if not result.get("success"):
            return await interaction.followup.send(
                f"❌ Credit grant rejected: `{result.get('error', 'unknown')}`",
                ephemeral=True
            )

        new_balance = result.get("new_balance", "?")
        sign = "+" if amount > 0 else ""
        embed = discord.Embed(
            title="💰 Credits updated",
            description=(
                f"**{sign}{amount}** credits → **{user.name}** (`{user.id}`)\n"
                f"New balance: **{new_balance}** credits\n"
                f"Reason: *{reason}*"
            ),
            color=discord.Color.from_rgb(46, 204, 113) if amount > 0 else discord.Color.from_rgb(241, 196, 15)
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        print(f"[ADMIN] {interaction.user} ({interaction.user.id}) granted {sign}{amount} credits to {user} ({user.id}) - reason: {reason}")

    # ============================================================
    # /admininfo — see all info on a user
    # ============================================================
    @app_commands.command(
        name="admininfo",
        description="[ADMIN] Display all known info on a user."
    )
    @app_commands.describe(user="Target Discord user")
    async def admininfo(self, interaction: discord.Interaction, user: discord.User):
        if not _is_admin(interaction):
            return await _silent_decline(interaction)

        await interaction.response.defer(thinking=True, ephemeral=True)

        try:
            profile = await PostgresDB.get_profile(user.id)
            stats = await PostgresDB.get_referral_stats(user.id)
            streak = await PostgresDB.get_streak(user.id)
            credits_data = await asyncio.to_thread(get_credits, str(user.id))
            current_credits = credits_data.get("credits", 0)
            total_purchased = await PostgresDB.get_total_purchased_credits(user.id)
        except Exception as e:
            traceback.print_exc()
            return await interaction.followup.send(f"❌ Lookup failed: `{e}`", ephemeral=True)

        sub_type = profile.get("sub_type", "free")

        embed = discord.Embed(
            title=f"🔍 {user.name}",
            description=f"Discord ID: `{user.id}`",
            color=discord.Color.from_rgb(155, 89, 182)
        )
        try:
            embed.set_thumbnail(url=user.display_avatar.url)
        except Exception:
            pass

        embed.add_field(
            name="Profile",
            value=(
                f"Name: **{profile.get('name') or '—'}**\n"
                f"Age: **{profile.get('age') or '—'}**\n"
                f"Plan: **{sub_type}**\n"
                f"Language: **{profile.get('language') or 'auto'}**"
            ),
            inline=True
        )
        embed.add_field(
            name="Credits",
            value=(
                f"Balance: **{current_credits}** cr\n"
                f"Lifetime purchased: **{total_purchased}** cr\n"
                f"Daily msgs used: **{profile.get('daily_msgs_used', 0)}**\n"
                f"Daily sessions used: **{profile.get('daily_sessions_used', 0)}**"
            ),
            inline=True
        )
        embed.add_field(
            name="Engagement",
            value=(
                f"Streak: **{streak.get('streak', 0)}** (best: **{streak.get('max', 0)}**)\n"
                f"Referrals: **{stats.get('total', 0)}** invited / **{stats.get('converted', 0)}** converted\n"
                f"Referral code: `{profile.get('referral_code') or '—'}`"
            ),
            inline=False
        )

        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))
