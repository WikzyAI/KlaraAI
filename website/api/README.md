# KlaraAI Credits API

API simple pour lier les crédits entre le site web et le bot Discord.

## Installation

```bash
cd api/
npm install
npm start
```

L'API démarre sur `http://localhost:3000`.

## Configuration

Crée un fichier `.env` dans le dossier `api/` :
```
DISCORD_BOT_TOKEN=ton_token_de_bot_ici
API_SECRET=une_cle_secrete_pour_admin
```

- **DISCORD_BOT_TOKEN** : Le token de ton bot Discord (nécessaire pour envoyer les DMs de remerciement).
  - Trouve-le dans [Discord Developer Portal](https://discord.com/developers/applications) → Ton bot → Bot → Token
  - Coche "MESSAGE CONTENT INTENT" dans Bot → Privileged Gateway Intents

- **API_SECRET** : Une clé secrète pour les opérations admin (optionnel)

## Configuration Discord Developer Portal

1. Va sur https://discord.com/developers/applications
2. Sélectionne ton application bot
3. Menu **OAuth2** → **Redirects** :
   - Ajoute `http://localhost:8000` (pour le site)
   - Ajoute `http://localhost:3000` (pour l'API)
4. Coche **"Public Client"** dans OAuth2 → General

## Comment ça marche

### Sur le site web (achat de crédits)
1. Utilisateur clique "Se connecter" → OAuth2 Discord
2. Utilisateur clique "Acheter" sur un pack
3. Le site appelle `POST /api/credits/add` avec le token Discord
4. L'API ajoute les crédits en base (fichier `credits.json`)

### Sur le bot Discord (vérification)
1. Utilisateur tape `/profile` ou `/premium`
2. Le bot appelle `GET /api/credits?discord_id=XXX`
3. Le bot affiche le solde depuis la même base

## Endpoints

| Méthode | URL | Description |
|---------|-----|-------------|
| GET | `/api/health` | Vérifie que l'API fonctionne |
| GET | `/api/credits?discord_id=XXX` | Récupère le solde d'un utilisateur |
| POST | `/api/credits/add` | Ajoute des crédits (token requis) |
| POST | `/api/users/update` | Met à jour le profil utilisateur |
| GET | `/api/leaderboard` | Top 10 des utilisateurs |

## Base de données

Par défaut, l'API utilise un fichier JSON (`credits.json`) pour stocker les données.
Si `better-sqlite3` est installé, elle utilisera SQLite (`credits.db`).

## Intégration Bot Discord

Voir le fichier `bot-integration.js` pour un exemple de code à ajouter à ton bot.

Résumé : ajoute cette fonction dans ton bot :
```javascript
const API_BASE = 'http://localhost:3000';

async function getCredits(discordId) {
    const res = await fetch(`${API_BASE}/api/credits?discord_id=${discordId}`);
    return await res.json();
}
```

Puis utilise-la dans tes commandes `/profile` et `/premium`.
