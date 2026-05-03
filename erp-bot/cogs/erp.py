"""
ERP Cog - Système de roleplay érotique avec réponse automatique en DM.
Une fois /erp start lancé, le bot répond automatiquement aux messages.
"""
import discord
from discord import app_commands
from discord.ext import commands
import json
import os
from config import DEFAULT_CHARACTERS, CHARACTERS_FILE, SYSTEM_PROMPT, HISTORY_FILE, PROFILES_FILE
from utils.db import HistoryDB, ProfilesDB
from utils.groq_client import GroqClient


class ERPCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.groq = GroqClient()
        self.characters_file = CHARACTERS_FILE
        self.history_db = HistoryDB(HISTORY_FILE)
        self.profiles_db = ProfilesDB(PROFILES_FILE)
        self._ensure_characters_file()

    def _ensure_characters_file(self):
        if not os.path.exists(self.characters_file):
            with open(self.characters_file, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_CHARACTERS, f, indent=2, ensure_ascii=False)

    def _load_characters(self) -> dict:
        with open(self.characters_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _build_messages(self, character: dict, history: list, user_profile: dict, context_limit: int) -> list:
        char_desc = character["desc"]
        if user_profile:
            user_name = user_profile.get("name") or "l'utilisateur"
            user_age = user_profile.get("age") or "non spécifié"
            user_desc = user_profile.get("description") or "non spécifiée"
            char_desc += f"\n\nL'utilisateur s'appelle {user_name}, a {user_age} ans. Description : {user_desc}"

        system_content = SYSTEM_PROMPT.format(
            character_name=character["name"],
            character_desc=char_desc
        )
        messages = [{"role": "system", "content": system_content}]

        # Use context_limit from subscription
        for entry in history[-context_limit:]:
            messages.append({"role": entry["role"], "content": entry["content"]})

        return messages

    async def handle_dm_message(self, message: discord.Message) -> bool:
        user_id = message.author.id
        print(f"[DEBUG ERP] handle_dm_message appelé pour {user_id}")

        if not self.history_db.has_active_session(user_id):
            print(f"[DEBUG ERP] Pas de session active pour {user_id}")
            return False

        session = self.history_db.get_session(user_id)
        if not session:
            print(f"[DEBUG ERP] Session None pour {user_id}")
            return False

        print(f"[DEBUG ERP] Session active trouvée: {session.get('character_name', 'Inconnu')}")

        if message.content.startswith("/"):
            print(f"[DEBUG ERP] Message commence par /, ignoré")
            return False

        # VÉRIFICATION DES LIMITES QUOTIDIENNES
        if not self.profiles_db.can_send_message(user_id):
            limits = self.profiles_db.get_limits(user_id)
            await message.channel.send(
                f"❌ Limite de messages quotidiens atteinte ({'illimité' if limits['daily_msgs'] == -1 else limits['daily_msgs']}/jour). "
                f"Réessaie demain ou utilise `/premium` pour upgrader."
            )
            return True

        characters = self._load_characters()
        char_key = session.get("character")
        if char_key not in characters:
            print(f"[DEBUG ERP] Personnage {char_key} introuvable")
            await message.channel.send("❌ Le personnage de ta session n'existe plus. Fais `/erp end` puis recommence.")
            return True

        character = characters[char_key]
        print(f"[DEBUG ERP] Personnage trouvé: {character['name']}")

        # Get subscription limits
        limits = self.profiles_db.get_limits(user_id)
        max_tokens = limits["max_tokens"]
        context_limit = limits["context"]

        # Adjust max_tokens based on response_length setting
        profile = self.profiles_db.get_profile(user_id)
        response_length = profile.get("response_length", "medium")
        length_multiplier = {"short": 0.5, "medium": 1.0, "long": 1.5}
        max_tokens = int(max_tokens * length_multiplier.get(response_length, 1.0))

        session["messages"].append({"role": "user", "content": message.content})
        self.history_db.set_session(user_id, session)
        print(f"[DEBUG ERP] Message utilisateur ajouté à l'historique")

        user_profile = self.profiles_db.get_profile(user_id)
        messages = self._build_messages(character, session["messages"], user_profile, context_limit)
        print(f"[DEBUG ERP] Messages préparés pour l'IA ({len(messages)} messages, context={context_limit}, tokens={max_tokens})")

        async with message.channel.typing():
            print(f"[DEBUG ERP] Appel de l'IA (Groq)...")
            ai_response = self.groq.generate(messages, temperature=0.85, max_tokens=max_tokens)
            print(f"[DEBUG ERP] Réponse IA reçue ({len(ai_response)} caractères): {ai_response[:100]}...")

        session["messages"].append({"role": "assistant", "content": ai_response})
        self.history_db.set_session(user_id, session)

        # Incrémenter le compteur de messages
        self.profiles_db.increment_messages(user_id)

        # Send as plain text (not embed) - actions in *asterisks*, dialogue as normal text
        # Split message if it exceeds Discord's 2000 char limit
        max_length = 2000
        if len(ai_response) <= max_length:
            await message.channel.send(ai_response)
        else:
            # Split into chunks at sentence boundaries
            chunks = []
            current = ""
            for char in ai_response:
                current += char
                if len(current) >= max_length - 100 and char in ".!?\n":
                    chunks.append(current)
                    current = ""
            if current:
                chunks.append(current)
            for chunk in chunks:
                await message.channel.send(chunk)
        print(f"[DEBUG ERP] Réponse envoyée avec succès")
        return True

    # ========================================================================
    # COMMANDES SLASH
    # ========================================================================

    @app_commands.command(name="erp", description="Gère tes sessions ERP")
    @app_commands.describe(
        action="Action à effectuer",
        character="Nom du personnage (pour 'start' ou 'info')",
        description="Description du personnage (pour 'create')",
        personality="Traits de personnalité (pour 'create')"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="start - Commencer avec un perso", value="start"),
        app_commands.Choice(name="end - Terminer la séance", value="end"),
        app_commands.Choice(name="list - Lister les personnages", value="list"),
        app_commands.Choice(name="info - Infos sur un perso", value="info"),
        app_commands.Choice(name="create - Créer un perso (premium)", value="create"),
    ])
    async def erp(self, interaction: discord.Interaction,
                  action: str,
                  character: str = None,
                  description: str = None,
                  personality: str = None):
        await interaction.response.defer(thinking=True)

        action = action.lower()

        if action == "start":
            await self._erp_start(interaction, character)
        elif action == "end":
            await self._erp_end(interaction)
        elif action == "list":
            await self._erp_list(interaction)
        elif action == "info":
            await self._erp_info(interaction, character)
        elif action == "create":
            await self._erp_create(interaction, character, description, personality)

    async def _erp_start(self, interaction: discord.Interaction, character: str):
        if not character:
            await interaction.followup.send("❌ Tu dois spécifier un personnage. Utilise `/erp list` pour voir les disponibles.", ephemeral=True)
            return

        characters = self._load_characters()
        char_key = character.lower()

        if char_key not in characters:
            await interaction.followup.send(f"❌ Personnage '{character}' introuvable. Utilise `/erp list`.", ephemeral=True)
            return

        if self.history_db.has_active_session(interaction.user.id):
            await interaction.followup.send("❌ Tu as déjà une séance en cours. Utilise `/erp end` pour la terminer.", ephemeral=True)
            return

        # VÉRIFICATION DES LIMITES QUOTIDIENNES
        if not self.profiles_db.can_start_session(interaction.user.id):
            limits = self.profiles_db.get_limits(interaction.user.id)
            await interaction.followup.send(
                f"❌ Limite de séances quotidiennes atteinte ({'illimité' if limits['daily_sessions'] == -1 else limits['daily_sessions']}/jour). "
                f"Réessaie demain ou utilise `/premium` pour upgrader.",
                ephemeral=True
            )
            return

        char = characters[char_key]

        session = {
            "character": char_key,
            "character_name": char["name"],
            "messages": []
        }
        self.history_db.set_session(interaction.user.id, session)

        # Incrémenter le compteur de séances
        self.profiles_db.increment_sessions(interaction.user.id)

        embed = discord.Embed(
            title=f"✅ Séance ERP lancée avec {char['name']}",
            description=f"{char['desc']}\n\n**Écris ton premier message pour commencer !**\nLe bot répondra automatiquement à tes messages.",
            color=discord.Color.from_rgb(255, 105, 180)
        )
        embed.set_footer(text="Utilise /erp end pour terminer la séance")
        await interaction.followup.send(embed=embed)

    async def _erp_end(self, interaction: discord.Interaction):
        if not self.history_db.has_active_session(interaction.user.id):
            await interaction.followup.send("❌ Tu n'as aucune séance en cours.", ephemeral=True)
            return

        session = self.history_db.get_session(interaction.user.id)
        char_name = session.get("character_name", "Inconnu")

        self.history_db.delete_session(interaction.user.id)

        embed = discord.Embed(
            title="✅ Séance terminée",
            description=f"Ta séance avec **{char_name}** est terminée. Merci d'avoir joué !",
            color=discord.Color.from_rgb(147, 112, 219)
        )
        await interaction.followup.send(embed=embed)

    async def _erp_list(self, interaction: discord.Interaction):
        characters = self._load_characters()
        limits = self.profiles_db.get_limits(interaction.user.id)

        embed = discord.Embed(
            title="Personnages disponibles",
            description="Utilise `/erp start <personnage>` pour commencer.",
            color=discord.Color.from_rgb(147, 112, 219)
        )

        for key, char in characters.items():
            pers = char.get("personality", "N/A")
            embed.add_field(
                name=f"{char['name']} ({key})",
                value=f"{char['desc']}\n*Traits : {pers}*",
                inline=False
            )

        embed.set_footer(text="/erp start <personnage> pour lancer une séance")
        await interaction.followup.send(embed=embed)

    async def _erp_info(self, interaction: discord.Interaction, character: str):
        if not character:
            await interaction.followup.send("❌ Tu dois spécifier un personnage.", ephemeral=True)
            return

        characters = self._load_characters()
        char_key = character.lower()

        if char_key not in characters:
            await interaction.followup.send(f"❌ Personnage '{character}' introuvable.", ephemeral=True)
            return

        char = characters[char_key]

        embed = discord.Embed(
            title=char['name'],
            description=char["desc"],
            color=discord.Color.from_rgb(255, 105, 180)
        )
        embed.add_field(name="Personnalité", value=char.get("personality", "N/A"), inline=False)
        embed.add_field(name="Clé", value=f"`{char_key}`", inline=True)
        embed.set_footer(text=f"Utilise /erp start {char_key} pour jouer ce personnage")
        await interaction.followup.send(embed=embed)

    async def _erp_create(self, interaction: discord.Interaction,
                          name: str, description: str, personality: str):
        # Vérifier si l'utilisateur peut créer un perso custom
        limits = self.profiles_db.get_limits(interaction.user.id)
        custom_chars_allowed = limits["custom_chars"]

        if custom_chars_allowed == 0:
            await interaction.followup.send("❌ Cette fonctionnalité nécessite l'abonnement **Standard** ou **Premium**. Utilise `/premium` pour plus d'infos.", ephemeral=True)
            return

        # Pour Premium, vérifier combien de persos customs ont été créés
        if custom_chars_allowed != -1:  # Pas illimité
            characters = self._load_characters()
            user_chars = [k for k, v in characters.items() if v.get("creator") == str(interaction.user.id)]
            if len(user_chars) >= custom_chars_allowed:
                await interaction.followup.send(f"❌ Limite de {custom_chars_allowed} personnages customs atteinte pour ton abonnement.", ephemeral=True)
                return

        if not name or not description:
            await interaction.followup.send("❌ Tu dois fournir au moins un nom et une description.", ephemeral=True)
            return

        characters = self._load_characters()
        char_key = name.lower().replace(" ", "_")

        if char_key in characters:
            await interaction.followup.send(f"❌ Un personnage avec la clé '{char_key}' existe déjà.", ephemeral=True)
            return

        characters[char_key] = {
            "name": name,
            "desc": description,
            "personality": personality or "indéfini",
            "creator": str(interaction.user.id)  # Marquer comme créé par l'utilisateur
        }

        with open(self.characters_file, "w", encoding="utf-8") as f:
            json.dump(characters, f, indent=2, ensure_ascii=False)

        embed = discord.Embed(
            title="✅ Personnage créé !",
            description=f"**{name}** a été ajouté à la liste.",
            color=discord.Color.green()
        )
        embed.add_field(name="Clé", value=f"`{char_key}`", inline=True)
        embed.set_footer(text=f"Utilise /erp start {char_key} pour commencer")
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(ERPCog(bot))
