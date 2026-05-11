"""
Verification Cog - Handles the persistent "I am 18+" button posted in the
KlaraAI support server's #age-verify channel.

Flow:
  1. New user joins the support server -> only sees the VERIFICATION category
  2. User solves the captcha in #captcha (handled by an external captcha bot
     like Wick / Captcha.bot / MEE6) -> gets the "Captcha Verified" role
  3. User clicks the "I am 18+ and I agree" button in #age-verify
  4. This cog checks that they ALREADY have "Captcha Verified" before
     granting "Verified 18+", which unlocks the rest of the server.

The button is a persistent view (timeout=None, stable custom_id) so it keeps
working forever, including across bot restarts. The view is re-registered on
on_ready() so Discord knows we still claim that custom_id.
"""
import discord
from discord.ext import commands
import config


AGE_VERIFY_CUSTOM_ID = "klaraai_age_verify"


class AgeVerifyView(discord.ui.View):
    """Persistent view for the age verification button."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="I am 18+ and I agree",
        style=discord.ButtonStyle.danger,
        custom_id=AGE_VERIFY_CUSTOM_ID,
        emoji="✅",
    )
    async def verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Only react inside a guild — clicking from a DM cache makes no sense.
        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ This button only works inside the support server.",
                ephemeral=True,
            )
            return

        # If the bot is configured with a specific support guild, refuse
        # button clicks coming from any other server (defensive — should
        # not happen because the button only exists in that one server).
        if config.SUPPORT_GUILD_ID and interaction.guild.id != config.SUPPORT_GUILD_ID:
            await interaction.response.send_message(
                "❌ This verification button does not belong to this server.",
                ephemeral=True,
            )
            return

        member = interaction.user
        if not isinstance(member, discord.Member):
            await interaction.response.send_message(
                "❌ Could not read your roles. Try refreshing Discord and clicking again.",
                ephemeral=True,
            )
            return

        guild = interaction.guild
        captcha_role = discord.utils.get(guild.roles, name="Captcha Verified")
        verified_role = discord.utils.get(guild.roles, name="Verified 18+")

        if verified_role is None:
            await interaction.response.send_message(
                "❌ The **Verified 18+** role is missing in this server. "
                "Ping an admin to re-run the setup script.",
                ephemeral=True,
            )
            return

        # Already verified — short-circuit cleanly.
        if verified_role in member.roles:
            await interaction.response.send_message(
                "✅ You are already verified. Enjoy the server!",
                ephemeral=True,
            )
            return

        # Require captcha first. If the captcha role does not exist yet we
        # still grant 18+ — the admin probably hasn't installed the captcha
        # bot, no point gating users on a role that nobody can earn.
        if captcha_role is not None and captcha_role not in member.roles:
            await interaction.response.send_message(
                f"⛔ You must first solve the captcha in <#captcha>. "
                f"Once the verification bot grants you the "
                f"**{captcha_role.name}** role, come back here and click again.",
                ephemeral=True,
            )
            return

        try:
            await member.add_roles(verified_role, reason="Age + captcha verified via button")
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I don't have permission to grant the **Verified 18+** role. "
                "Ask an admin to move my role above 'Verified 18+' in the role list.",
                ephemeral=True,
            )
            return
        except Exception as e:
            print(f"[Verification] add_roles failed: {e}")
            await interaction.response.send_message(
                "❌ Something went wrong. Try again, or ping an admin.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            f"🎉 Welcome aboard, {member.mention}! "
            f"You now have access to the whole server. "
            f"Say hi in <#introductions> or jump straight to <#general>.",
            ephemeral=True,
        )


class VerificationCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._view_registered = False

    @commands.Cog.listener()
    async def on_ready(self):
        # Re-register the persistent view exactly once so the button keeps
        # working after bot restarts. on_ready can fire multiple times
        # (reconnects), guard with a flag.
        if not self._view_registered:
            self.bot.add_view(AgeVerifyView())
            self._view_registered = True
            print("[Verification] Persistent age-verify view registered.")


async def setup(bot: commands.Bot):
    await bot.add_cog(VerificationCog(bot))
