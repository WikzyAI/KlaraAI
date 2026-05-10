# 🚀 KlaraAI — Tuto de lancement

Tout ce qu'il te reste à faire pour passer du **"prêt techniquement"** au **"lancé publiquement et qui encaisse"**.

L'auto-entrepreneur est volontairement laissé pour la fin — fais-le après tout le reste.

**Estimation totale :** 4-6h de boulot étalées sur 1-2 sessions.

---

## ✅ Étape 1 — Email de support (10 minutes)

### Pourquoi c'est obligatoire
- Required par Discord pour valider le bot (>75 servers)
- Required par Stripe / CCBill pour les disputes clients
- Required dans tes pages légales (RGPD)
- Empêche d'utiliser ton vrai email perso → meilleure séparation pro/perso

### Comment faire

1. Va sur **[ProtonMail](https://account.proton.me/signup)** ou **[Tutanota](https://app.tuta.com/signup)** (les 2 sont gratuits, chiffrés, sans pub)
2. Crée un compte avec une adresse pro :
   - `klaraai.support@protonmail.com`
   - ou `contact.klaraai@proton.me`
   - ou `support.klaraai@proton.me`
3. Note le mot de passe quelque part en sécurité (pas dans Discord !)
4. Configure une signature simple :
   ```
   — KlaraAI Support
   https://www.klaraai.me
   ```

### Mettre à jour les pages légales

Dans ton repo, ouvre ces 3 fichiers et remplace **`support@klaraai.app`** par ton vraie email :
- `website/terms.html` (2 occurrences)
- `website/privacy.html` (2 occurrences)
- `website/legal.html` (3 occurrences)

`Ctrl+F` sur chaque fichier, "Replace all" → `git push` → Vercel redéploie auto.

---

## ✅ Étape 2 — Avatar et bannière Discord (1 heure)

### Pourquoi
Un bot avec l'icône Discord par défaut convertit ~3× moins. Première impression = première décision.

### Avatar (carré, 512×512 minimum)

**Option A — Génération AI (gratuit ou ~5€)**

1. Va sur **[leonardo.ai](https://leonardo.ai)** (free tier solide), **[Midjourney](https://midjourney.com)** ($10/mois) ou **[DALL-E via Bing](https://www.bing.com/images/create)** (gratuit)
2. Prompt suggéré :
   ```
   Square avatar, anime succubus portrait, soft magenta and violet gradient background,
   glowing pink eyes, sensual smile, minimal subtle horns, neon-noir lighting,
   sharp focus, high detail, 1:1 aspect ratio, no text, no watermark
   ```
3. Génère 4 variantes, choisis ta préférée
4. Vérifie qu'il n'y a **pas de nudité explicite** — Discord rejette les avatars NSFW même pour les bots NSFW

**Option B — Logo abstrait minimaliste (gratuit)**

Si tu veux du clean / non-personnage :
```
Abstract square logo, pink-violet-blue gradient diamond, neon glow,
dark background, minimalist, vector-style, no text, 1:1
```

### Bannière (680×240 minimum)

```
Wide cinematic banner 16:5 aspect, dark lounge interior,
neon pink and violet accents, atmospheric smoke, subtle bokeh,
no people, no text, soft lighting, brand identity feel
```

### Upload sur le Dev Portal

1. https://discord.com/developers/applications → ton app KlaraAI
2. **General Information** → **App Icon** → upload l'avatar (PNG/JPG, max 1MB)
3. Scroll plus bas → **App Banner** → upload la bannière (PNG/JPG)
4. **Save Changes**

→ Le nouvel avatar apparaît dans Discord en quelques minutes (clique sur le bot dans une DM pour vérifier).

---

## ✅ Étape 3 — Discord Developer Portal (30 minutes)

Toujours sur https://discord.com/developers/applications → ton app

### 3.1 — Description et tags

**General Information** → **Description** → colle :

```
✦ KlaraAI — Private 18+ ERP companion. Chat in DMs with three default characters or unlimited custom personas. Persistent long-term memory keeps every scene continuous, fully uncensored AI. Send /help to start, /erp to open the menu.

🌐 klaraai.me · 🔥 Daily streak rewards · 🎟️ /referral
```

**Tags** : `Adult`, `Roleplay`, `AI`, `NSFW`, `Companion`

### 3.2 — URLs légales

Toujours sur **General Information**, scroll vers le bas :

- **Terms of Service URL** : `https://www.klaraai.me/terms`
- **Privacy Policy URL** : `https://www.klaraai.me/privacy`

### 3.3 — Privileged Gateway Intents

Onglet **Bot** dans la sidebar.

Active uniquement :
- ✅ **Message Content Intent** (obligatoire pour lire les DMs)
- ❌ Presence Intent (pas besoin)
- ❌ Server Members Intent (pas besoin, on est en DM only)

Save Changes.

### 3.4 — Public Bot

Toujours **Bot** :
- ✅ **Public Bot** : ON (pour que d'autres puissent inviter le bot)

### 3.5 — OAuth2 Redirects

Onglet **OAuth2** → **Redirects**

Ajoute ces 2 URLs (tu peux les laisser toutes les deux) :
- `https://www.klaraai.me`
- `https://klaraai.vercel.app` (au cas où, tant que l'ancien marche)

Save.

### 3.6 — Vérifier l'install link

Onglet **OAuth2** → **URL Generator** :
- **Scopes** : ✅ `bot` + ✅ `applications.commands`
- **Bot Permissions** : ✅ Send Messages, ✅ Read Message History, ✅ Use Slash Commands

→ L'URL générée doit ressembler à :
```
https://discord.com/api/oauth2/authorize?client_id=1500196432211349634&permissions=414464724032&scope=bot+applications.commands
```

---

## ✅ Étape 4 — Déployer le bot sur Render (15 minutes)

### Pourquoi
Aujourd'hui ton bot tourne **sur ton PC**. Quand tu éteins → bot HS → tu perds tes utilisateurs.

### Steps

1. Va sur **[render.com](https://render.com)** → tu as déjà un compte (l'API tourne dessus)
2. Clique **+ New** → **Web Service**
3. Sélectionne ton repo KlaraAI
4. Render détecte automatiquement le fichier `erp-bot/render.yaml` → il pré-remplit tout

5. **Avant de cliquer "Create"**, va dans l'onglet **Environment** et ajoute ces variables (récupère-les de ton fichier `.env` local) :

   | Key | Value |
   |---|---|
   | `DISCORD_TOKEN` | Le token bot du Dev Portal |
   | `GROQ_API_KEY` | Ta clé Groq depuis console.groq.com |
   | `OPENROUTER_API_KEY` | Ta clé OpenRouter (la nouvelle, pas celle qui a fuité) |
   | `DATABASE_URL` | Idem que ton service API (copie depuis le service Render existant) |
   | `API_BASE` | `https://klaraai.onrender.com` |
   | `API_SECRET` | Idem que ton API service |
   | `LLM_PRIMARY` | `groq` (laisse comme ça) |

6. Clique **Create Web Service**. Premier deploy ~5 minutes.

### Vérifier que ça marche

Quand le deploy finit, ouvre l'URL du service (ex: `https://klaraai-bot.onrender.com`) — tu dois voir :
```
✦ KlaraAI Discord bot is alive ✦
Endpoints: /ping  /health
```

**Sur Discord** : envoie `/ping` au bot en DM. Si tu vois "Pong! Latency: XXms", le déploiement marche.

**Stoppe ton bot local** (Ctrl+C dans le terminal) — désormais c'est Render qui prend le relais.

---

## ✅ Étape 5 — UptimeRobot anti-sleep (5 minutes)

### Pourquoi
Render free tier suspend ton service après 15 min sans trafic HTTP. Sans ce truc, ton bot s'endort la nuit.

### Steps

1. Va sur **[uptimerobot.com](https://uptimerobot.com)** → Free signup
2. Clique **+ New monitor**
3. Settings :
   - **Monitor Type** : `HTTP(s)`
   - **Friendly Name** : `KlaraAI bot keepalive`
   - **URL** : `https://klaraai-bot.onrender.com/ping` *(remplace par ton URL Render exacte)*
   - **Monitoring Interval** : **5 minutes**
4. Clique **Create monitor**.

→ Désormais UptimeRobot ping ton bot toutes les 5 min, il ne s'endort plus jamais. Bonus : si Render crashe, tu reçois un email d'alerte.

---

## ✅ Étape 6 — Stripe Live Mode (30 minutes)

⚠️ **Cette étape est à faire EN DERNIER, après l'auto-entrepreneur.** Stripe va te demander ton SIREN pendant le KYC. Donc fais le test mode end-to-end maintenant, puis active le live mode quand tu auras ton SIREN.

### 6.1 — Tester en mode Test (maintenant, sans SIREN)

1. **[Dashboard Stripe](https://dashboard.stripe.com)** → **Toggle "Test mode"** (en haut à droite, slider en haut)
2. **Developers** → **API keys** → copie la **Test Secret Key** (commence par `sk_test_`)
3. Mets-la dans Render → service API → **Environment** → `STRIPE_SECRET_KEY` = ta clé test
4. **Developers** → **Webhooks** → **Add endpoint**
   - **Endpoint URL** : `https://klaraai.onrender.com/api/stripe-webhook`
   - **Events to listen** : `checkout.session.completed`
   - Save → copie le **Signing secret** (commence par `whsec_`)
5. Mets-le dans Render → API service → `STRIPE_WEBHOOK_SECRET` = whsec_xxx
6. Render redéploie auto

**Tester un achat** :
- Va sur ton site `klaraai.me/buy-credits`
- Login Discord
- Clique "Buy 100 credits"
- À l'écran Stripe Checkout, utilise une carte de test : **`4242 4242 4242 4242`** / CVC `123` / Date future
- → Tu dois recevoir un DM Discord du bot : "Thank you for your purchase!"
- → Sur Discord, `/profile` doit montrer +100 credits

Si ça marche → le pipe est OK. Tu pourras switcher en live mode dès que t'auras ton SIREN.

### 6.2 — Live mode (quand t'auras ton SIREN)

Quand t'auras ton SIREN dans 7-15 jours :

1. Stripe → switch sur **Live mode**
2. **Developers** → **API keys** → cette fois copie la **Live Secret Key** (`sk_live_`)
3. Refais le webhook côté Live mode (le webhook test ne marche QUE en test mode)
4. Mets à jour `STRIPE_SECRET_KEY` et `STRIPE_WEBHOOK_SECRET` sur Render avec les valeurs LIVE
5. Stripe va te demander ton SIREN dans **Settings** → **Business** → **KYC** :
   - Type : Sole proprietor (entrepreneur individuel)
   - SIREN : *(le numéro reçu par URSSAF)*
   - Nom : *(le nom de ta micro-entreprise — souvent ton vrai nom + "Entrepreneur Individuel")*
   - Adresse : *(adresse de domiciliation)*
   - IBAN : ton compte perso ou pro
6. Stripe valide en 1-3 jours. Pendant ce temps tu peux déjà recevoir des paiements (ils sont juste retenus).

⚠️ **Stripe ne durera pas longtemps** vu que tu vends du NSFW. Compte 3-12 mois avant qu'ils suspendent ton compte. Migrer vers CCBill/Segpay reste l'objectif moyen-terme.

---

## ✅ Étape 7 — Test end-to-end complet (30 minutes)

### Pourquoi
Avant de balancer publiquement, faut que TOUT marche sur un compte fresh (pas le tien).

### Setup

- Demande à un pote ou crée un compte Discord secondaire (un que tu n'utilises pas)
- Invite ton bot avec lui via le lien d'install

### Checklist à faire passer (tout coche ✅)

- [ ] **Première interaction** : `/help` en DM répond avec l'embed
- [ ] **Profile vierge** : `/profile` montre les fields "Not set", credits=0, streak 0
- [ ] **Démarrer un ERP** : `/erp` → bouton **Play** → choisir Lilith → message "Scene started"
- [ ] **Premier message** : envoie un message en français → la réponse arrive en français (la directive auto fonctionne)
- [ ] **Refus test** : envoie "*touch her ass*" → tu dois recevoir une réponse explicite, pas un refus
- [ ] **Settings langue** : `/settings` → bouton **EN** → message en français → réponse en anglais
- [ ] **Settings longueur** : pareil avec **Long** → la réponse suivante est plus longue
- [ ] **Streak** : après 1er message ERP, `/profile` montre Streak: 1
- [ ] **End session** : `/erp` → End Session → "Saving memories..." → wait 30s → `/memories` montre des facts
- [ ] **Restart with same character** : nouvelle session avec Lilith → vérifie qu'elle fait référence à un truc de la session précédente (preuve que la mémoire marche)
- [ ] **Référral** : `/referral` montre le code → noté
- [ ] **Achat (test mode)** : sur le site → buy credits → carte test 4242 4242 4242 4242 → DM thank you → `/profile` montre les credits
- [ ] **Site responsive** : ouvre `klaraai.me` sur ton téléphone → toutes les sections affichent bien
- [ ] **Cookie banner** : nouveau navigateur en privé → la bannière s'affiche → clique Accept → recharge → ne réapparaît pas
- [ ] **Pages légales** : `/terms`, `/privacy`, `/legal` chargent toutes correctement
- [ ] **Bot offline test** : éteins ton PC → vérifie que `/ping` répond toujours (= Render + UptimeRobot fonctionnent)

Si **toutes les cases sont cochées** → t'es prêt techniquement.

Si y'en a une qui rate → débug ce point spécifique avant de continuer.

---

## ✅ Étape 8 — Final : auto-entrepreneur + lancement public

Ce que tu fais à la toute fin (volontairement séparé du reste) :

1. **Inscription auto-entrepreneur** sur formalites.entreprises.gouv.fr (15 min)
2. Reçois ton SIREN sous 7-15 jours
3. Mets à jour `legal.html` avec ton vrai SIREN (remplace le placeholder jaune)
4. Active **Stripe Live mode** + KYC (étape 6.2)
5. Annonce sur tes canaux choisis :
   - Reddit : r/AICompanions, r/CharacterAI_NSFW, r/ChatGPTNSFW
   - Twitter/X : `#AIChat #NSFWBot #DiscordBot`
   - Listings adult-friendly : discords.com, discadia
   - Mentionne ton bot dans 1-2 serveurs Discord NSFW (sans spammer)

---

## 📋 Résumé express

Imprime cette checklist mentalement :

| # | Étape | Durée | Bloquant ? |
|---|---|---|---|
| 1 | Email support | 10 min | ✅ |
| 2 | Avatar + bannière | 1h | ✅ |
| 3 | Dev Portal Discord | 30 min | ✅ |
| 4 | Déployer bot sur Render | 15 min | ✅ |
| 5 | UptimeRobot | 5 min | ✅ |
| 6.1 | Stripe Test mode | 30 min | ✅ |
| 7 | Test end-to-end | 30 min | ✅ |
| **TOTAL** | | **~3h30** | |
| 8 | Auto-entrepreneur (puis Live mode + lancement) | + 7-15 jours d'attente | ⏰ |

Fais 1-7 cette semaine → tu es **prêt techniquement**. Tu actives le live mode dès que ton SIREN arrive → tu commences à encaisser le jour même.

---

## 🆘 Si quelque chose foire

Documente ce qui marche pas (logs Render, screenshot Discord, etc.) et reviens me voir. Le code est solide, les bugs viendront probablement de :

1. **Variables d'env mal copiées** sur Render → vérifie qu'il n'y a pas d'espace en début/fin
2. **Webhook Stripe pas signé** → le secret du webhook est différent de la clé API
3. **Discord intent désactivé** → Bot n'arrive pas à lire les DM = check "Message Content Intent"
4. **OAuth redirect manquant** → "Login Discord" qui échoue = ajouter `klaraai.me` dans la liste des redirects

Bonne chance, t'es à 80% du chemin. Le reste c'est juste du remplissage de formulaires.
