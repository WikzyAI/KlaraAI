"""
Premium Cog - Subscription management.
"""
import discord
from discord import app_commands
from discord.ext import commands
from utils.db import PostgresDB
from utils.api_client import get_credits, add_credits
import config
import asyncio


class PremiumCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="premium", description="Manage your subscription")
    async def premium(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)

        user_id = str(interaction.user.id)
        profile = await PostgresDB.get_profile(user_id)
        sub_type = await PostgresDB.get_sub_type(user_id)
        limits = await PostgresDB.get_limits(user_id)

        credits_data = await asyncio.to_thread(get_credits, user_id)
        credits = credits_data.get("credits", 0)

        daily_msgs_used = profile.get("daily_msgs_used", 0)
        daily_sessions_used = profile.get("daily_sessions_used", 0)
        msgs_limit = "unlimited" if limits["daily_msgs"] == -1 else limits["daily_msgs"]
        sessions_limit = "unlimited" if limits["daily_sessions"] == -1 else limits["daily_sessions"]

        sub_emoji = {"free": "🌿", "standard": "💎", "premium": "👑"}.get(sub_type, "✨")

        embed = discord.Embed(
            title="👑 Subscription & Credits",
            description=f"Current plan: {sub_emoji} **{limits['name']}**",
            color=discord.Color.from_rgb(241, 196, 15)
        )

        embed.add_field(
            name="💰 Wallet",
            value=f"**{credits}** credits  *(${credits/100:.2f})*",
            inline=True
        )
        embed.add_field(
            name="💬 Messages today",
            value=f"{daily_msgs_used} / {msgs_limit}",
            inline=True
        )
        embed.add_field(
            name="🎬 Sessions today",
            value=f"{daily_sessions_used} / {sessions_limit}",
            inline=True
        )

        # Show exact reset countdown when at least one quota is limited.
        if limits["daily_msgs"] != -1 or limits["daily_sessions"] != -1:
            reset_at = PostgresDB.get_reset_at(profile)
            if reset_at is None:
                reset_text = "🔄 Window not started — full quota available."
            else:
                ts = int(reset_at.timestamp())
                reset_text = f"🔄 Quota resets <t:{ts}:R> *(at <t:{ts}:t>)*"
            embed.add_field(name="⏳ Reset", value=reset_text, inline=False)

        plan_titles = {
            "free": "🌿 Free Trial",
            "standard": "💎 Standard",
            "premium": "👑 Premium"
        }
        for sub_key in ["free", "standard", "premium"]:
            sub = config.SUBSCRIPTIONS[sub_key]
            title = plan_titles[sub_key]
            if sub_key == sub_type:
                title = f"{title} — ✅ active"

            if sub_key != "free":
                value = f"`{sub['price_month']}` credits / month\n"
            else:
                value = "Free forever\n"
            value += "\n".join(f"› {feat}" for feat in sub["features"])

            embed.add_field(
                name=title,
                value=value,
                inline=False
            )

        view = discord.ui.View(timeout=300)

        if sub_type != "standard":
            std_btn = discord.ui.Button(
                label=f"Standard — {config.SUBSCRIPTIONS['standard']['price_month']} cr",
                style=discord.ButtonStyle.primary,
                emoji="💎",
                row=0
            )
            std_btn.callback = self._upgrade_standard
            view.add_item(std_btn)

        if sub_type != "premium":
            prem_btn = discord.ui.Button(
                label=f"Premium — {config.SUBSCRIPTIONS['premium']['price_month']} cr",
                style=discord.ButtonStyle.success,
                emoji="👑",
                row=0
            )
            prem_btn.callback = self._upgrade_premium
            view.add_item(prem_btn)

        buy_btn = discord.ui.Button(
            label="Buy Credits",
            style=discord.ButtonStyle.link,
            emoji="🛒",
            url="https://klaraai.me/buy-credits",
            row=1
        )
        view.add_item(buy_btn)

        site_btn = discord.ui.Button(
            label="View on Website",
            style=discord.ButtonStyle.link,
            emoji="🌐",
            url="https://klaraai.me/pricing",
            row=1
        )
        view.add_item(site_btn)

        await interaction.followup.send(embed=embed, view=view)

    async def _upgrade_standard(self, interaction: discord.Interaction):
        await self._upgrade(interaction, "standard")

    async def _upgrade_premium(self, interaction: discord.Interaction):
        await self._upgrade(interaction, "premium")

    async def _upgrade(self, interaction: discord.Interaction, new_type: str):
        await interaction.response.defer(thinking=True)

        user_id = str(interaction.user.id)
        profile = await PostgresDB.get_profile(user_id)
        current_sub = await PostgresDB.get_sub_type(user_id)

        credits_data = await asyncio.to_thread(get_credits, user_id)
        credits = credits_data.get("credits", 0)

        new_price = config.SUBSCRIPTIONS[new_type]["price_month"]
        current_price = config.SUBSCRIPTIONS.get(current_sub, config.SUBSCRIPTIONS["free"])["price_month"]

        price_to_pay = new_price - current_price

        if credits >= price_to_pay:
            result = await asyncio.to_thread(
                add_credits, user_id, -price_to_pay, profile.get("name", ""),
                f"Upgrade to {config.SUBSCRIPTIONS[new_type]['name']}"
            )
            if result.get("success"):
                await PostgresDB.update_profile(user_id, sub_type=new_type)
                embed = discord.Embed(
                    title="✅ Purchase Successful!",
                    description=f"Congratulations! You are now subscribed to **{config.SUBSCRIPTIONS[new_type]['name']}**! 💎\n"
                                f"**{price_to_pay} credits** have been deducted (difference from your current plan).\n"
                                f"Your new balance: **{result.get('new_balance', credits - price_to_pay)} credits**.",
                    color=discord.Color.gold()
                )
            else:
                embed = discord.Embed(
                    title="❌ API Error",
                    description=f"Error deducting credits. Details: {result.get('error', 'unknown')}. Check API_SECRET is set on Render.",
                    color=discord.Color.red()
                )
        else:
            embed = discord.Embed(
                title="❌ Insufficient Credits",
                description=f"You need **{price_to_pay} more credits** to upgrade to {config.SUBSCRIPTIONS[new_type]['name']}.\n"
                            f"You currently have: **{credits} credits**.\n"
                            f"(New plan price: {new_price}, your current plan: {current_price})",
                color=discord.Color.red()
            )

        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(PremiumCog(bot))
