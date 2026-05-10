"""
Admin Cog — operator-only commands.

Authorization is purely runtime: every command checks
`interaction.user.id in config.ADMIN_USER_IDS`. Admins are configured
via the ADMIN_USER_IDS env var (comma-separated Discord user IDs):

    ADMIN_USER_IDS=926474936518856775

For *anyone else*, the commands are silent — they appear in Discord's
slash-command picker but do nothing visible (we just respond with a
generic "unknown command" ephemeral message). This avoids advertising
their existence to regular users.

Available commands:
    /admincredits user:<User> amount:<int> [reason:<str>]
        Grant (positive) or revoke (negative) credits.
    /adminban user:<User> reason:<str>
        Ban a user from the bot. Their active session and archived
        conversations are wiped immediately.
    /adminunban user:<User>
        Lift a ban.
    /admininfo user:<User>
        Display the user's full state (profile, credits, streak,
        referrals, ban status).
    /adminbans
        List all currently banned users.
"""
import asyncio
import traceback
from datetime import datetime, timezone

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
        await interaction.response.send_message(
            "Unknown command.", ephemeral=True
        )
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
    # /adminban — ban a user
    # ============================================================
    @app_commands.command(
        name="adminban",
        description="[ADMIN] Ban a user from using the bot."
    )
    @app_commands.describe(
        user="Discord user to ban",
        reason="Reason for the ban (visible to the user)",
    )
    async def adminban(
        self,
        interaction: discord.Interaction,
        user: discord.User,
        reason: str,
    ):
        if not _is_admin(interaction):
            return await _silent_decline(interaction)

        await interaction.response.defer(thinking=True, ephemeral=True)

        if int(user.id) in config.ADMIN_USER_IDS:
            return await interaction.followup.send(
                "❌ You can't ban another admin. Remove them from ADMIN_USER_IDS env var first.",
                ephemeral=True
            )

        if int(user.id) == int(interaction.user.id):
            return await interaction.followup.send(
                "❌ You can't ban yourself.", ephemeral=True
            )

        try:
            await PostgresDB.ban_user(user.id, reason, interaction.user.id)
        except Exception as e:
            traceback.print_exc()
            return await interaction.followup.send(f"❌ Ban failed: `{e}`", ephemeral=True)

        embed = discord.Embed(
            title="🔨 User banned",
            description=(
                f"**{user.name}** (`{user.id}`) is now banned.\n"
                f"Reason: *{reason}*\n"
                f"Their active session + archived conversations have been wiped."
            ),
            color=discord.Color.from_rgb(231, 76, 60)
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        print(f"[ADMIN BAN] {interaction.user} ({interaction.user.id}) banned {user} ({user.id}) - reason: {reason}")

        # Try to notify the banned user via DM (best-effort).
        try:
            try:
                dm = user.dm_channel or await user.create_dm()
            except Exception:
                dm = None
            if dm:
                ban_embed = discord.Embed(
                    title="🚫 You have been banned from KlaraAI",
                    description=(
                        f"You can no longer use this bot.\n\n"
                        f"**Reason:** {reason}\n\n"
                        f"If you believe this is a mistake, contact support: "
                        f"`support@klaraai.me`"
                    ),
                    color=discord.Color.from_rgb(231, 76, 60)
                )
                await dm.send(embed=ban_embed)
        except Exception as e:
            print(f"[ADMIN BAN] Could not DM banned user {user.id}: {e}")

    # ============================================================
    # /adminunban — lift a ban
    # ============================================================
    @app_commands.command(
        name="adminunban",
        description="[ADMIN] Lift a user's ban."
    )
    @app_commands.describe(user="Discord user to unban")
    async def adminunban(self, interaction: discord.Interaction, user: discord.User):
        if not _is_admin(interaction):
            return await _silent_decline(interaction)

        await interaction.response.defer(thinking=True, ephemeral=True)

        ok = await PostgresDB.unban_user(user.id)
        if not ok:
            return await interaction.followup.send(
                f"⚠️ User `{user.id}` was not banned (or doesn't exist in the DB).",
                ephemeral=True
            )

        embed = discord.Embed(
            title="✅ Ban lifted",
            description=f"**{user.name}** (`{user.id}`) can use the bot again.",
            color=discord.Color.from_rgb(46, 204, 113)
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        print(f"[ADMIN UNBAN] {interaction.user} ({interaction.user.id}) unbanned {user} ({user.id})")

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
            ban = await PostgresDB.get_ban_info(user.id)
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
            color=discord.Color.from_rgb(155, 89, 182) if not ban else discord.Color.from_rgb(231, 76, 60)
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

        if ban:
            ban_at = ban.get("banned_at")
            ban_at_str = ban_at.strftime("%Y-%m-%d %H:%M UTC") if isinstance(ban_at, datetime) else "?"
            embed.add_field(
                name="🚫 BANNED",
                value=(
                    f"Reason: *{ban.get('reason')}*\n"
                    f"Banned at: {ban_at_str}\n"
                    f"Banned by: `{ban.get('banned_by')}`"
                ),
                inline=False
            )
        else:
            embed.add_field(name="Status", value="✅ Not banned", inline=False)

        await interaction.followup.send(embed=embed, ephemeral=True)

    # ============================================================
    # /adminbans — list all current bans
    # ============================================================
    @app_commands.command(
        name="adminbans",
        description="[ADMIN] List all currently banned users."
    )
    async def adminbans(self, interaction: discord.Interaction):
        if not _is_admin(interaction):
            return await _silent_decline(interaction)

        await interaction.response.defer(thinking=True, ephemeral=True)

        try:
            bans = await PostgresDB.list_banned_users(limit=50)
        except Exception as e:
            return await interaction.followup.send(f"❌ Lookup failed: `{e}`", ephemeral=True)

        if not bans:
            embed = discord.Embed(
                title="🛡️ No banned users",
                description="The ban list is empty.",
                color=discord.Color.from_rgb(46, 204, 113)
            )
            return await interaction.followup.send(embed=embed, ephemeral=True)

        embed = discord.Embed(
            title=f"🚫 Banned users ({len(bans)})",
            color=discord.Color.from_rgb(231, 76, 60)
        )
        lines = []
        for b in bans:
            uid = b.get("user_id")
            name = b.get("name") or "—"
            reason = (b.get("ban_reason") or "—")[:80]
            at = b.get("banned_at")
            at_str = at.strftime("%Y-%m-%d") if isinstance(at, datetime) else "?"
            lines.append(f"`{uid}` · **{name}** · *{reason}* · {at_str}")
        # Discord embed field caps at 1024 chars — split if needed
        chunk = ""
        for line in lines:
            if len(chunk) + len(line) + 1 > 1000:
                embed.add_field(name="​", value=chunk, inline=False)
                chunk = ""
            chunk += line + "\n"
        if chunk:
            embed.add_field(name="​", value=chunk, inline=False)

        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))
