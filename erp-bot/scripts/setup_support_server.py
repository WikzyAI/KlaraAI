"""
One-shot setup script for the KlaraAI Discord support server.

Creates all roles, categories and channels with the right permissions
so a freshly created server is ready in seconds.

USAGE
-----
1. Create a new empty Discord server ("KlaraAI Support")
2. Invite your KlaraAI bot with Administrator permission, e.g.:
   https://discord.com/oauth2/authorize?client_id=<APP_ID>&permissions=8&scope=bot+applications.commands
3. Copy the server's Guild ID (Right-click server icon -> Copy ID, requires
   Developer Mode in Discord settings)
4. From the project root, run:
   python erp-bot/scripts/setup_support_server.py <GUILD_ID>

It is safe to re-run the script: existing roles/categories/channels are
skipped, only missing items get created.

AFTER SETUP
-----------
- Invite a captcha bot (Wick / Captcha.bot / MEE6) to the same server,
  configure it to grant the "Captcha Verified" role on success.
- Set SUPPORT_GUILD_ID=<GUILD_ID> in the bot's Render env vars and
  restart the bot, so the persistent "I am 18+" button keeps working
  across restarts.
"""
import asyncio
import os
import sys
import traceback

# Allow running this script directly: add the parent (erp-bot) folder
# to the Python path so `config` and `utils.*` imports work.
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(THIS_DIR)
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

import discord
from dotenv import load_dotenv

load_dotenv(os.path.join(PARENT_DIR, ".env"))
TOKEN = os.getenv("DISCORD_TOKEN")

if len(sys.argv) < 2:
    print("Usage: python erp-bot/scripts/setup_support_server.py <GUILD_ID>")
    sys.exit(1)

try:
    GUILD_ID = int(sys.argv[1])
except ValueError:
    print(f"[ERROR] GUILD_ID must be a number, got: {sys.argv[1]}")
    sys.exit(1)


# ============================================================================
# CONFIGURATION
# ============================================================================
# (name, color_hex, hoist, mentionable, permissions)
ROLES = [
    ("KlaraAI Admin",    0xef4444, True,  True,  discord.Permissions(administrator=True)),
    ("Premium",          0xf59e0b, True,  True,  discord.Permissions.none()),
    ("Standard",         0x9b59b6, True,  True,  discord.Permissions.none()),
    ("Verified 18+",     0x10b981, False, False, discord.Permissions.none()),
    ("Captcha Verified", 0x60a5fa, False, False, discord.Permissions.none()),
    ("Muted",            0x6b7280, False, False, discord.Permissions(send_messages=False, add_reactions=False, speak=False)),
]

# Channels listed as (name, topic, nsfw, verified_only, read_only_everyone)
# - verified_only: only members with "Verified 18+" can see the channel
# - read_only_everyone: visible to @everyone but nobody can post except admins
CATEGORIES = [
    ("🤖 VERIFICATION", [
        ("welcome",      "Welcome to KlaraAI Support. Start here.",                              False, False, True),
        ("rules",        "Please read carefully before participating.",                          False, False, True),
        ("captcha",      "Step 1 - Solve the captcha to prove you are human.",                   False, False, False),
        ("age-verify",   "Step 2 - Click the button to confirm you are 18+.",                    False, False, False),
    ]),
    ("📢 INFO", [
        ("announcements", "Bot updates, news, releases.",                                        False, True,  True),
        ("changelog",     "Patch notes and version history.",                                    False, True,  True),
        ("status",        "Uptime and incident reports.",                                        False, True,  True),
    ]),
    ("💬 COMMUNITY", [
        ("general",       "General chat for 18+ verified members.",                              False, True,  False),
        ("introductions", "Say hi to the community.",                                            False, True,  False),
        ("feedback",      "Suggestions and feature requests.",                                   False, True,  False),
    ]),
    ("🛠️ SUPPORT", [
        ("help",           "Ask for help using the bot.",                                        False, True,  False),
        ("bug-reports",    "Report bugs here. Please include /erp logs if possible.",            False, True,  False),
        ("payment-issues", "Credit / Stripe / refund issues.",                                   False, True,  False),
    ]),
    ("🎨 SHOWCASE", [
        ("scenes",         "Share your favorite RP scenes. NSFW allowed (still no minors).",     True,  True,  False),
        ("characters",     "Show off your custom characters.",                                   True,  True,  False),
        ("screenshots",    "Cool moments from your sessions.",                                   True,  True,  False),
    ]),
    ("🤖 BOT", [
        ("bot-commands",   "Try out bot commands here.",                                         False, True,  False),
        ("commands-help",  "List and description of all bot commands.",                          False, True,  True),
    ]),
]


# ============================================================================
# CLIENT
# ============================================================================
intents = discord.Intents.default()
intents.guilds = True
client = discord.Client(intents=intents)


async def _no_existing_messages(channel: discord.TextChannel) -> bool:
    """Return True if the channel is empty (no messages yet)."""
    async for _ in channel.history(limit=1):
        return False
    return True


@client.event
async def on_ready():
    print(f"[OK] Logged in as {client.user}")
    guild = client.get_guild(GUILD_ID)
    if not guild:
        print(f"[ERROR] Guild {GUILD_ID} not found.")
        print(f"        Is the bot invited to the server? Is the ID correct?")
        await client.close()
        return

    print(f"[OK] Working on guild: {guild.name} ({guild.id})")
    print(f"     Owner: {guild.owner} - Members: {guild.member_count}")
    print()

    try:
        # ----------------------------------------------------------
        # 1. ROLES
        # ----------------------------------------------------------
        print("=== ROLES ===")
        role_map = {}
        existing_roles = {r.name: r for r in guild.roles}
        for name, color, hoist, mentionable, perms in ROLES:
            if name in existing_roles:
                role_map[name] = existing_roles[name]
                print(f"  [SKIP]   {name} (exists)")
            else:
                role = await guild.create_role(
                    name=name,
                    colour=discord.Colour(color),
                    hoist=hoist,
                    mentionable=mentionable,
                    permissions=perms,
                    reason="KlaraAI support server setup",
                )
                role_map[name] = role
                print(f"  [CREATE] {name}")
        print()

        verified_role = role_map["Verified 18+"]
        everyone_role = guild.default_role

        # ----------------------------------------------------------
        # 2. CATEGORIES + CHANNELS
        # ----------------------------------------------------------
        print("=== CATEGORIES + CHANNELS ===")
        for cat_name, channels in CATEGORIES:
            existing_cat = discord.utils.get(guild.categories, name=cat_name)
            if existing_cat:
                category = existing_cat
                print(f"  [SKIP]   {cat_name}")
            else:
                category = await guild.create_category(cat_name, reason="KlaraAI support server setup")
                print(f"  [CREATE] {cat_name}")

            for ch_name, topic, nsfw, verified_only, read_only_everyone in channels:
                existing_ch = discord.utils.get(category.channels, name=ch_name)
                if existing_ch:
                    print(f"    [SKIP]   #{ch_name}")
                    continue

                # Build per-channel permission overwrites.
                overwrites: dict = {}
                if verified_only:
                    # Hide from @everyone; show to verified.
                    overwrites[everyone_role] = discord.PermissionOverwrite(view_channel=False)
                    overwrites[verified_role] = discord.PermissionOverwrite(
                        view_channel=True,
                        send_messages=not read_only_everyone,
                        read_message_history=True,
                        attach_files=True,
                        embed_links=True,
                        add_reactions=True,
                    )
                else:
                    # Visible to @everyone (verification flow needs this).
                    overwrites[everyone_role] = discord.PermissionOverwrite(
                        view_channel=True,
                        send_messages=not read_only_everyone,
                        read_message_history=True,
                    )

                channel = await category.create_text_channel(
                    name=ch_name,
                    topic=topic,
                    nsfw=nsfw,
                    overwrites=overwrites,
                    reason="KlaraAI support server setup",
                )
                print(f"    [CREATE] #{ch_name}")
        print()

        # ----------------------------------------------------------
        # 3. SEED MESSAGES (only when channel is empty)
        # ----------------------------------------------------------
        print("=== SEED MESSAGES ===")

        async def seed(channel_name: str, embed: discord.Embed, view=None):
            ch = discord.utils.get(guild.text_channels, name=channel_name)
            if not ch:
                print(f"  [MISS]   #{channel_name} not found")
                return
            if not await _no_existing_messages(ch):
                print(f"  [SKIP]   #{channel_name} (already has messages)")
                return
            if view is not None:
                await ch.send(embed=embed, view=view)
            else:
                await ch.send(embed=embed)
            print(f"  [POST]   #{channel_name}")

        # -- welcome --
        welcome_embed = discord.Embed(
            title="✦ Welcome to KlaraAI Support ✦",
            description=(
                "**KlaraAI** is a private 18+ ERP Discord bot.\n\n"
                "**To get access to the whole server:**\n"
                "1️⃣  Solve the captcha in <#captcha>\n"
                "2️⃣  Click the button in <#age-verify>\n"
                "3️⃣  Read the rules in <#rules>\n\n"
                "Then the rest of the server unlocks.\n\n"
                "🌐 Website: https://klaraai.me\n"
                "💎 Pricing: https://klaraai.me/pricing\n"
                "📨 The bot only operates in **DMs** — invite it here:\n"
                "https://klaraai.me/home"
            ),
            color=0x9b59b6,
        )
        await seed("welcome", welcome_embed)

        # -- rules --
        rules_embed = discord.Embed(
            title="📜 Server Rules",
            description=(
                "**1.**  You must be **18 years or older** to participate.\n"
                "**2.**  No sharing of CSAM or any content involving minors — "
                "**instant ban and report to authorities.**\n"
                "**3.**  Keep NSFW content inside <#scenes>, <#characters>, "
                "<#screenshots>. Other channels are SFW.\n"
                "**4.**  No spam, no advertising other bots/services.\n"
                "**5.**  No harassment, no hate speech, no doxxing.\n"
                "**6.**  Do not leak other users' private DMs or paid content.\n"
                "**7.**  Bug reports → <#bug-reports>. Payment issues → "
                "<#payment-issues>. Don't derail <#general>.\n"
                "**8.**  Respect mods. We can mute/kick/ban at our discretion.\n\n"
                "*Breaking these rules may result in mute, kick, or permanent ban.*\n"
                "*By staying in this server you agree to our "
                "[Terms](https://klaraai.me/terms) and "
                "[Privacy Policy](https://klaraai.me/privacy).*"
            ),
            color=0xef4444,
        )
        await seed("rules", rules_embed)

        # -- captcha placeholder --
        captcha_embed = discord.Embed(
            title="🤖 Step 1 — Captcha Verification",
            description=(
                "Before we let you in, prove you're not a bot.\n\n"
                "**Solve the captcha posted by our verification bot below.**\n"
                "Once solved you'll receive the **Captcha Verified** role.\n\n"
                "Then head to <#age-verify> to confirm you're 18+ and unlock "
                "the rest of the server.\n\n"
                "_If no captcha bot is here yet, the server admin still needs "
                "to invite one. Recommended:_\n"
                "• [Wick](https://wickbot.com/) — captcha + anti-raid (best)\n"
                "• [Captcha.bot](https://captcha.bot/) — captcha only\n"
                "• [MEE6](https://mee6.xyz/) — captcha as a module"
            ),
            color=0x60a5fa,
        )
        await seed("captcha", captcha_embed)

        # -- age verify with persistent button --
        # custom_id matches the persistent view declared in cogs/verification.py
        # so the bot reclaims the button across restarts.
        age_view = discord.ui.View(timeout=None)
        age_view.add_item(discord.ui.Button(
            label="I am 18+ and I agree",
            style=discord.ButtonStyle.danger,
            custom_id="klaraai_age_verify",
            emoji="✅",
        ))
        age_embed = discord.Embed(
            title="🔞 Step 2 — Age Verification",
            description=(
                "This server contains **adult content (18+)**.\n\n"
                "By clicking the button below you confirm that:\n"
                "• You are at least **18 years old**.\n"
                "• You consent to viewing sexually explicit fictional content.\n"
                "• You agree to our "
                "[Terms of Service](https://klaraai.me/terms) and "
                "[Privacy Policy](https://klaraai.me/privacy).\n\n"
                "_You must have already solved the captcha in <#captcha> — "
                "otherwise the button will reject you._"
            ),
            color=0xef4444,
        )
        await seed("age-verify", age_embed, view=age_view)

        # -- commands help --
        cmds_embed = discord.Embed(
            title="🤖 Bot Commands",
            description=(
                "All commands are slash commands, used in **DMs** with the bot.\n\n"
                "**Core**\n"
                "• `/erp` — Pick a character and start a scene\n"
                "• `/profile` — View your profile, plan, credits, streak\n"
                "• `/settings` — Response length, language, custom characters\n"
                "• `/premium` — Manage your subscription\n\n"
                "**Social**\n"
                "• `/referral` — Get your invite code and stats\n\n"
                "**Help**\n"
                "• `/help` — Quick command list\n\n"
                "👉 The bot does **not** answer commands inside this server. "
                "Send it a Direct Message instead."
            ),
            color=0x9b59b6,
        )
        await seed("commands-help", cmds_embed)

        print()
        print("=" * 60)
        print("[OK] Setup complete!")
        print("=" * 60)
        print()
        print("NEXT STEPS:")
        print(f"  1. Invite a captcha bot (e.g. Wick) to '{guild.name}'.")
        print(f"     Configure it to grant the 'Captcha Verified' role on success.")
        print(f"  2. On Render, set this env var on the bot service:")
        print(f"         SUPPORT_GUILD_ID={guild.id}")
        print(f"  3. Restart the bot so the persistent '18+' button works.")
        print(f"  4. Move the KlaraAI bot role to the top of the role list")
        print(f"     in Server Settings -> Roles, so it can grant 'Verified 18+'.")
        print()

    except discord.Forbidden as e:
        print(f"[ERROR] Permission denied: {e}")
        print("        Make sure the bot has the Administrator permission in this guild.")
    except Exception as e:
        print(f"[ERROR] {type(e).__name__}: {e}")
        traceback.print_exc()
    finally:
        await client.close()


if __name__ == "__main__":
    if not TOKEN:
        print("[ERROR] DISCORD_TOKEN missing. Set it in erp-bot/.env or as an env var.")
        sys.exit(1)
    client.run(TOKEN)
