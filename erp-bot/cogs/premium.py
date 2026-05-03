"""
Premium Cog - Subscription management.
"""
import discord
from discord import app_commands
from discord.ext import commands
from utils.db import ProfilesDB
from utils.api_client import get_credits, add_credits
import config
import asyncio


class PremiumCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = ProfilesDB(config.PROFILES_FILE)

    @app_commands.command(name="premium", description="Manage your subscription")
    async def premium(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)

        user_id = str(interaction.user.id)
        profile = self.db.get_profile(user_id)
        sub_type = self.db.get_sub_type(user_id)
        limits = self.db.get_limits(user_id)

        # Get credits from API
        credits_data = await asyncio.to_thread(get_credits, user_id)
        credits = credits_data.get("credits", 0)

        # Calculate daily usage
        daily_msgs_used = profile.get("daily_msgs_used", 0)
        daily_sessions_used = profile.get("daily_sessions_used", 0)
        msgs_limit = "unlimited" if limits["daily_msgs"] == -1 else limits["daily_msgs"]
        sessions_limit = "unlimited" if limits["daily_sessions"] == -1 else limits["daily_sessions"]

        embed = discord.Embed(
            title="💎 Subscription Management",
            description=f"Your current plan: **{limits['name']}**",
            color=discord.Color.gold()
        )

        embed.add_field(
            name="📊 Today's Usage",
            value=f"Messages: {daily_msgs_used}/{msgs_limit}\n"
                  f"Sessions: {daily_sessions_used}/{sessions_limit}\n"
                  f"Credits: {credits}",
            inline=False
        )

        # Show all 3 plans
        for sub_key in ["free", "standard", "premium"]:
            sub = config.SUBSCRIPTIONS[sub_key]
            if sub_key == sub_type:
                title = f"✅ {sub['name']} (current)"
            else:
                title = sub["name"]

            if sub_key != "free":
                value = f"Price: {sub['price_month']} credits/month\n"
            else:
                value = "Free\n"
            value += "\n".join(f"• {feat}" for feat in sub["features"])

            embed.add_field(
                name=title,
                value=value,
                inline=False
            )

        # Buttons to upgrade
        view = discord.ui.View()

        if sub_type != "standard":
            std_btn = discord.ui.Button(
                label=f"Switch to Standard ({config.SUBSCRIPTIONS['standard']['price_month']} credits)",
                style=discord.ButtonStyle.primary,
                emoji="💎"
            )
            std_btn.callback = self._upgrade_standard
            view.add_item(std_btn)

        if sub_type != "premium":
            prem_btn = discord.ui.Button(
                label=f"Switch to Premium ({config.SUBSCRIPTIONS['premium']['price_month']} credits)",
                style=discord.ButtonStyle.success,
                emoji="💎"
            )
            prem_btn.callback = self._upgrade_premium
            view.add_item(prem_btn)

        # Buy Credits button - redirects to website
        buy_btn = discord.ui.Button(
            label="Buy Credits",
            style=discord.ButtonStyle.link,
            emoji="🛒",
            url="https://klaraai.vercel.app"
        )
        view.add_item(buy_btn)

        await interaction.followup.send(embed=embed, view=view)

    async def _upgrade_standard(self, interaction: discord.Interaction):
        await self._upgrade(interaction, "standard")

    async def _upgrade_premium(self, interaction: discord.Interaction):
        await self._upgrade(interaction, "premium")

    async def _upgrade(self, interaction: discord.Interaction, new_type: str):
        await interaction.response.defer(thinking=True)

        user_id = str(interaction.user.id)
        profile = self.db.get_profile(user_id)
        current_sub = self.db.get_sub_type(user_id)

        # Get credits from API
        credits_data = await asyncio.to_thread(get_credits, user_id)
        credits = credits_data.get("credits", 0)

        new_price = config.SUBSCRIPTIONS[new_type]["price_month"]
        current_price = config.SUBSCRIPTIONS.get(current_sub, config.SUBSCRIPTIONS["free"])["price_month"]

        # Only deduct the difference
        price_to_pay = new_price - current_price

        if credits >= price_to_pay:
            # Deduct credits via API (negative amount)
            from utils.api_client import add_credits
            result = await asyncio.to_thread(add_credits, user_id, -price_to_pay, profile.get("name", ""), f"Upgrade to {config.SUBSCRIPTIONS[new_type]['name']}")
            if result.get("success"):
                # Update subscription type in local DB
                self.db.update_profile(user_id, sub_type=new_type)
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
