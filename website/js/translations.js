// ============================================
// KlaraAI - Translations (FR, EN, ES, IT)
// ============================================

const translations = {
    fr: {
        // Nav
        nav_home: "Accueil",
        nav_pricing: "Tarifs",
        nav_buy: "Acheter",
        nav_buy_credits: "Acheter des crédits",
        nav_login: "Se connecter",

        // Age Verify
        age_title: "⚠️ Accès Réservé",
        age_desc: "Ce site et ce bot sont strictement réservés aux personnes de 18 ans et plus.",
        age_18plus: "Le contenu est à caractère érotique/pornographique.",
        age_deny: "J'ai moins de 18 ans",
        age_confirm: "J'ai 18 ans ou plus",

        // Hero
        hero_title: "KlaraAI",
        hero_desc: "Bot Discord d'ERP privé • Roleplay érotique avec IA • 18+",
        hero_btn_pricing: "Voir les tarifs",
        hero_btn_buy: "Acheter des crédits",
        hero_btn_invite: "🤖 Inviter le bot",
        hero_btn_commands: "📋 Commandes",

        // Features
        feat_title: "Fonctionnalités",
        feat_subtitle: "Un bot Discord privé qui fonctionne exclusivement en messages privés (DM)",
        feat_3chars_title: "3 Personnages Uniques",
        feat_3chars_desc: "Lilith (Succube), Isabelle (Belle-mère), Chloé (Belle-sœur). Chaque perso a sa propre personnalité et son style.",
        feat_ia_title: "IA Avancée",
        feat_ia_desc: "Réponses générées par IA (llama-3.3-70b) avec contexte mémorisé jusqu'à 50 messages.",
        feat_auto_title: "Réponse Automatique",
        feat_auto_desc: "Une fois la séance lancée avec /erp start, le bot répond automatiquement à tous tes messages.",
        feat_private_title: "100% Privé",
        feat_private_desc: "Le bot fonctionne exclusivement en DM (messages privés). Aucun serveur, aucune trace publique.",
        feat_actions_title: "Actions Formatées",
        feat_actions_desc: "Les actions sont écrites entre astérisques : *elle s'approche de toi* pour une immersion totale.",
        feat_nsfw_title: "NSFW Total",
        feat_nsfw_desc: "Contenu érotique explicite autorisé et encouragé en DM. Aucune censure, aucune restriction.",

        // How it works
        how_title: "Comment ça marche ?",
        how_subtitle: "3 étapes simples pour commencer ton RP érotique",

        // Rewards (streak + referral)
        rewards_title: "Récompenses & Crédits Gratuits",
        rewards_subtitle: "Reste actif, invite des amis — gagne des crédits sans dépenser un centime.",
        rewards_streak_title: "Streak Quotidien",
        rewards_streak_desc: "Envoie un message dans <code>/erp</code> chaque jour pour maintenir ton streak. Plus il est long, plus les récompenses sont belles.",
        rewards_streak_fine: "Au-delà du jour 30 : <strong>+15 crédits tous les 7 jours</strong>. Le streak repart à zéro si tu sautes un jour.",
        rewards_referral_title: "Invite des Amis",
        rewards_referral_desc: "Récupère ton code unique avec <code>/referral</code>. Quand un ami l'utilise et essaie le bot, vous gagnez tous les deux.",
        rewards_referral_s1_t: "Partage ton code",
        rewards_referral_s1_d: "ex: <code>K8M3PR</code>",
        rewards_referral_s2_t: "Ton ami essaie le bot",
        rewards_referral_s2_d: "Après 5 messages, il reçoit <strong>+25 crédits</strong>",
        rewards_referral_s3_t: "Ton ami achète $5+",
        rewards_referral_s3_d: "Tu reçois <strong>+200 crédits ($2)</strong> instantanément",
        rewards_referral_fine: "Anti-fraude : compte Discord ≥14 jours, bonus livré après activité réelle, plafond de 100 parrainages par code.",
        step1_title: "Ajoute le bot",
        step1_desc: "Invite KlaraAI en DM sur Discord. Aucun serveur requis, tout se passe en privé.",
        step2_title: "Lance une séance",
        step2_desc: "Utilise /erp start <personnage> pour commencer avec Lilith, Isabelle ou Chloé.",
        step3_title: "Profite",
        step3_desc: "Écris tes messages, le bot répond automatiquement avec des réponses immersives et détaillées.",

        // Bot Card
        bot_title: "🤖 Utiliser le bot sur Discord",
        bot_desc: "Ajoute KlaraAI à tes contacts Discord et envoie-lui /help en DM pour commencer.<br>Le bot ne fonctionne qu'en messages privés (DM).",
        bot_help: "/help - Aide",
        bot_profile: "/profile - Ton profil",
        bot_premium: "/premium - Abonnement",
        bot_start: "/erp start - Commencer",
        bot_end: "/erp end - Terminer",
        bot_list: "/erp list - Personnages",

        // Pricing
        pricing_title: "Nos Tarifs",
        pricing_subtitle: "100 crédits = 1 USD • Paiement sécurisé • Annulable à tout moment",
        pricing_credits_info: "💡 Le système de crédits :",
        pricing_credits_desc: "Le bot utilise un système de crédits.<br>100 crédits = 1 USD. Les abonnements sont débités en crédits chaque mois.",

        // Free
        free_title: "Free Trial",
        free_full: "0 /mois",
        free_credits: "0 crédits / mois",

        // Standard
        standard_title: "Standard",
        standard_full: "1600 crédits /mois",
        standard_eur: "~16$ / 15€",
        sub_standard_1600: "1600 crédits",

        // Premium
        premium_title: "Premium",
        premium_full: "3200 crédits /mois",
        premium_eur: "~32$ / 30€",
        sub_premium_3200: "3200 crédits",

        // Credits Shop
        shop_title: "Acheter des Crédits",
        shop_subtitle: "100 crédits = 1 USD • Paiement sécurisé • Livraison instantanée",
        shop_example: "💡 Exemple de conversion :",
        shop_example_desc: "100 crédits = 1 USD • 500 crédits = 5 USD • 1000 crédits = 10 USD<br><small>Les abonnements coutent 1600 crédits/mois (Standard) ou 3200 crédits/mois (Premium).</small>",

        pack_starter: "Starter Pack",
        pack_starter_100: "100 crédits",
        pack_starter_price: "1 USD / 0.90€",
        pack_starter_desc: "Suffisant pour environ 5 séances complètes",

        pack_popular: "Popular Pack",
        pack_popular_500: "500 crédits",
        pack_popular_price: "5 USD / 4.50€",
        pack_popular_desc: "Suffisant pour environ 25 séances complètes",

        pack_pro: "Pro Pack",
        pack_pro_1000: "1000 crédits",
        pack_pro_price: "10 USD / 9€",
        pack_pro_desc: "Suffisant pour environ 50 séances complètes",

        pack_elite: "Elite Pack",
        pack_elite_5000: "5000 crédits",
        pack_elite_price: "50 USD / 45€",
        pack_elite_desc: "Suffisant pour environ 250 séances complètes",

        // Commons
        btn_buy: "Acheter",
        btn_buy_credits: "Acheter des crédits",
        btn_view_pricing: "Voir les tarifs",
        btn_start: "Commencer",
        btn_start_free: "Commencer gratuitement",
        btn_coming_soon: "Système de paiement en cours de développement.\nRevenez plus tard !",
        shop_login_required: "Vous devez vous connecter avec Discord pour acheter des crédits.",
        shop_purchase_success: "Achat réussi ! {amount} crédits ({pack}) ajoutés. Nouveau solde : {balance} crédits.",
        how_it_works_title: "📝 Comment ça marche ?",
        how_it_works_desc1: "1. <strong>Achetez des crédits</strong> sur ce site (système en cours de développement)",
        how_it_works_desc2: "2. <strong>Les crédits sont ajoutés</strong> à votre profil Discord via le bot",
        how_it_works_desc3: "3. <strong>Utilisez /premium</strong> dans Discord pour voir votre solde et upgradez",
        how_it_works_desc4: "4. <strong>Profitez !</strong> Le bot débite automatiquement les crédits selon votre abonnement",
        note_title: "⚠️ Note :",
        note_desc: "Le système de paiement est en cours de développement.<br>Pour l'instant, les crédits sont simulés dans le bot. Le paiement réel sera ajouté prochainement.",

        // Footer
        footer_desc: "Bot Discord d'ERP privé pour adultes.",
        footer_18plus: "⚠️ Site et bot réservés aux 18+ ans",
        footer_links: "Liens",
        footer_legal: "Légal",
        footer_terms: "Conditions d'utilisation",
        footer_privacy: "Politique de confidentialité",
        footer_legal_notice: "Mentions légales",
        footer_copyright: "© 2026 KlaraAI. Tous droits réservés. Site réservé aux adultes (18+).",

        // Features list
        f_3chars: "3 personnages de base",
        f_20msg: "20 messages/jour",
        f_2sess: "2 séances/jour",
        f_ctx10: "Context: 10 messages",
        f_basic_resp: "Réponses de base",
        f_3plus2: "3 personnages de base + 2 customs",
        f_100msg: "100 messages/jour",
        f_5sess: "5 séances/jour",
        f_ctx20: "Context: 20 messages",
        f_normal_resp: "Réponses IA normales",
        f_2custom: "2 personnages customs max",
        f_unlimited_chars: "Personnages illimités",
        f_unlimited_msg: "Messages illimités",
        f_unlimited_sess: "Séances illimitées",
        f_ctx50: "Context: 50 messages",
        f_priority: "Réponses IA prioritaires",
        f_unlimited_custom: "Personnages customs illimités",
        f_adv_profile: "Configuration profil avancée",
        f_no_custom: "Personnages customs",
        f_no_priority: "Réponses prioritaires",

        // Tech details
        tech_title: "📊 Détails techniques :",
        tech_ctx: "<strong>Context</strong> = nombre de messages retenus dans l'historique de la séance (permanent, pas quotidien)",
        tech_daily: "<strong>Messages/jour</strong> et <strong>Séances/jour</strong> = limites quotidiennes (raz à minuit)",
        tech_tokens: "<strong>Tokens</strong> = longueur max de la réponse IA (400, 800 ou 1200)",
        tech_custom: "<strong>Personnages customs</strong> = personnages créés par l'utilisateur",

        // Subscription
        sub_standard: "Standard (1 mois)",
        sub_premium: "Premium (1 mois)",
        sub_standard_2: "Standard",
        sub_premium_2: "Premium",
        sub_price: "Prix",
    },

    en: {
        // Nav
        nav_home: "Home",
        nav_pricing: "Pricing",
        nav_buy: "Shop",
        nav_buy_credits: "Buy Credits",
        nav_login: "Login",

        // Age Verify
        age_title: "⚠️ Restricted Access",
        age_desc: "This site and bot are strictly reserved for persons 18 years and older.",
        age_18plus: "Content is erotic/pornographic in nature.",
        age_deny: "I am under 18",
        age_confirm: "I am 18 or older",

        // Hero
        hero_title: "KlaraAI",
        hero_desc: "Private ERP Discord Bot • Erotic Roleplay with AI • 18+",
        hero_btn_pricing: "View Pricing",
        hero_btn_buy: "Buy Credits",
        hero_btn_invite: "🤖 Invite Bot",
        hero_btn_commands: "📋 Commands",

        // Features
        feat_title: "Features",
        feat_subtitle: "A private Discord bot that works exclusively in DMs",
        feat_3chars_title: "3 Unique Characters",
        feat_3chars_desc: "Lilith (Succubus), Isabelle (Stepmom), Chloé (Stepsister). Each character has their own personality and style.",
        feat_ia_title: "Advanced AI",
        feat_ia_desc: "AI-generated responses (llama-3.3-70b) with memory context up to 50 messages.",
        feat_auto_title: "Auto Reply",
        feat_auto_desc: "Once the session is started with /erp start, the bot automatically replies to all your messages.",
        feat_private_title: "100% Private",
        feat_private_desc: "Bot works exclusively in DMs. No server, no public traces.",
        feat_actions_title: "Formatted Actions",
        feat_actions_desc: "Actions are written between asterisks: *she approaches you* for total immersion.",
        feat_nsfw_title: "Full NSFW",
        feat_nsfw_desc: "Explicit erotic content allowed and encouraged in DMs. No censorship, no restrictions.",

        // How it works
        how_title: "How It Works?",
        how_subtitle: "3 simple steps to start your erotic RP",

        // Rewards (streak + referral)
        rewards_title: "Rewards & Free Credits",
        rewards_subtitle: "Stay engaged, invite friends — earn credits without spending a cent.",
        rewards_streak_title: "Daily Streak",
        rewards_streak_desc: "Send a message in <code>/erp</code> every day to keep your streak alive. The longer the streak, the better the rewards.",
        rewards_streak_fine: "Beyond day 30: <strong>+15 credits every 7 days</strong>. Streak resets if you skip a day.",
        rewards_referral_title: "Invite Friends",
        rewards_referral_desc: "Get a unique code via <code>/referral</code>. When a friend uses it and tries the bot, you both earn.",
        rewards_referral_s1_t: "Share your code",
        rewards_referral_s1_d: "e.g. <code>K8M3PR</code>",
        rewards_referral_s2_t: "Friend tries the bot",
        rewards_referral_s2_d: "After 5 messages they get <strong>+25 credits</strong>",
        rewards_referral_s3_t: "Friend buys $5+",
        rewards_referral_s3_d: "You get <strong>+200 credits ($2)</strong> instantly",
        rewards_referral_fine: "Anti-fraud: Discord account ≥14 days, bonus delivered after real activity, lifetime cap of 100 referrals per code.",
        step1_title: "Add the bot",
        step1_desc: "Invite KlaraAI to DM on Discord. No server required, everything happens privately.",
        step2_title: "Start a session",
        step2_desc: "Use /erp start <character> to begin with Lilith, Isabelle, or Chloé.",
        step3_title: "Enjoy",
        step3_desc: "Write your messages, the bot automatically replies with immersive and detailed responses.",

        // Bot Card
        bot_title: "🤖 Using the bot on Discord",
        bot_desc: "Add KlaraAI to your Discord contacts and send /help in DM to start.<br>The bot only works in DMs.",
        bot_help: "/help - Help",
        bot_profile: "/profile - Your profile",
        bot_premium: "/premium - Subscription",
        bot_start: "/erp start - Start",
        bot_end: "/erp end - End",
        bot_list: "/erp list - Characters",

        // Pricing
        pricing_title: "Our Pricing",
        pricing_subtitle: "100 credits = 1 USD • Secure Payment • Cancel Anytime",
        pricing_credits_info: "💡 Credits System:",
        pricing_credits_desc: "The bot uses a credit system.<br>100 credits = 1 USD. Subscriptions are billed in credits each month.",

        free_title: "Free Trial",
        free_full: "0 /month",
        free_credits: "0 credits / month",

        standard_title: "Standard",
        standard_full: "1600 credits/month",
        standard_eur: "~$16 / €15",
        sub_standard_1600: "1600 credits",

        premium_title: "Premium",
        premium_full: "3200 credits/month",
        premium_eur: "~$32 / €30",
        sub_premium_3200: "3200 credits",

        // Credits Shop
        shop_title: "Buy Credits",
        shop_subtitle: "100 credits = 1 USD • Secure Payment • Instant Delivery",
        shop_example: "💡 Conversion Example:",
        shop_example_desc: "100 credits = $1 • 500 credits = $5 • 1000 credits = $10<br><small>Subscriptions cost 1600 credits/month (Standard) or 3200 credits/month (Premium).</small>",

        pack_starter: "Starter Pack",
        pack_starter_100: "100 credits",
        pack_starter_price: "$1 / €0.90",
        pack_starter_desc: "Enough for about 5 complete sessions",

        pack_popular: "Popular Pack",
        pack_popular_500: "500 credits",
        pack_popular_price: "$5 / €4.50",
        pack_popular_desc: "Enough for about 25 complete sessions",

        pack_pro: "Pro Pack",
        pack_pro_1000: "1000 credits",
        pack_pro_price: "$10 / €9",
        pack_pro_desc: "Enough for about 50 complete sessions",

        pack_elite: "Elite Pack",
        pack_elite_5000: "5000 credits",
        pack_elite_price: "$50 / €45",
        pack_elite_desc: "Enough for about 250 complete sessions",

        // Commons
        btn_buy: "Buy",
        btn_buy_credits: "Buy Credits",
        btn_view_pricing: "View Pricing",
        btn_start: "Get Started",
        btn_start_free: "Start Free",
        btn_coming_soon: "Payment system under development.\nCome back later!",
        shop_login_required: "You must login with Discord to purchase credits.",
        shop_purchase_success: "Purchase successful! {amount} credits ({pack}) added. New balance: {balance} credits.",
        how_it_works_title: "📝 How It Works?",
        how_it_works_desc1: "1. <strong>Buy credits</strong> on this site (system under development)",
        how_it_works_desc2: "2. <strong>Credits are added</strong> to your Discord profile via the bot",
        how_it_works_desc3: "3. <strong>Use /premium</strong> in Discord to view your balance and upgrade",
        how_it_works_desc4: "4. <strong>Enjoy!</strong> The bot automatically debits credits based on your subscription",
        note_title: "⚠️ Note:",
        note_desc: "Payment system is under development.<br>For now, credits are simulated in the bot. Real payment will be added soon.",

        // Footer
        footer_desc: "Private ERP Discord bot for adults.",
        footer_18plus: "⚠️ Site and bot reserved for 18+ only",
        footer_links: "Links",
        footer_legal: "Legal",
        footer_terms: "Terms of Service",
        footer_privacy: "Privacy Policy",
        footer_legal_notice: "Legal Notices",
        footer_copyright: "© 2026 KlaraAI. All rights reserved. Site reserved for adults (18+).",

        // Features list
        f_3chars: "3 base characters",
        f_20msg: "20 messages/day",
        f_2sess: "2 sessions/day",
        f_ctx10: "Context: 10 messages",
        f_basic_resp: "Basic responses",
        f_3plus2: "3 base characters + 2 customs",
        f_100msg: "100 messages/day",
        f_5sess: "5 sessions/day",
        f_ctx20: "Context: 20 messages",
        f_normal_resp: "Normal AI responses",
        f_2custom: "Max 2 custom characters",
        f_unlimited_chars: "Unlimited characters",
        f_unlimited_msg: "Unlimited messages",
        f_unlimited_sess: "Unlimited sessions",
        f_ctx50: "Context: 50 messages",
        f_priority: "Priority AI responses",
        f_unlimited_custom: "Unlimited customs",
        f_adv_profile: "Advanced profile config",
        f_no_custom: "Custom characters",
        f_no_priority: "Priority responses",

        // Tech details
        tech_title: "📊 Technical Details:",
        tech_ctx: "<strong>Context</strong> = number of messages kept in session history (permanent, not daily)",
        tech_daily: "<strong>Messages/day</strong> and <strong>Sessions/day</strong> = daily limits (reset at midnight)",
        tech_tokens: "<strong>Tokens</strong> = max response length (400, 800 or 1200)",
        tech_custom: "<strong>Custom characters</strong> = user-created characters",

        // Subscription
        sub_standard: "Standard (1 month)",
        sub_premium: "Premium (1 month)",
        sub_standard_2: "Standard",
        sub_premium_2: "Premium",
        sub_price: "Price",
    },

    es: {
        // Nav
        nav_home: "Inicio",
        nav_pricing: "Precios",
        nav_buy: "Tienda",
        nav_buy_credits: "Comprar Créditos",
        nav_login: "Iniciar sesión",

        // Age Verify
        age_title: "⚠️ Acceso Restringido",
        age_desc: "Este sitio y bot están estrictamente reservados para personas de 18 años o más.",
        age_18plus: "El contenido es de carácter erótico/pornográfico.",
        age_deny: "Tengo menos de 18 años",
        age_confirm: "Tengo 18 años o más",

        // Hero
        hero_title: "KlaraAI",
        hero_desc: "Bot Discord ERP Privado • Roleplay Erótico con IA • 18+",
        hero_btn_pricing: "Ver Precios",
        hero_btn_buy: "Comprar Créditos",
        hero_btn_invite: "🤖 Invitar Bot",
        hero_btn_commands: "📋 Comandos",

        // Features
        feat_title: "Características",
        feat_subtitle: "Un bot de Discord privado que funciona exclusivamente en DMs",
        feat_3chars_title: "3 Personajes Únicos",
        feat_3chars_desc: "Lilith (Súcubo), Isabelle (Madrastra), Chloé (Hermanastra). Cada personaje tiene su propia personalidad y estilo.",
        feat_ia_title: "IA Avanzada",
        feat_ia_desc: "Respuestas generadas por IA (llama-3.3-70b) con memoria de hasta 50 mensajes.",
        feat_auto_title: "Respuesta Automática",
        feat_auto_desc: "Una vez iniciada la sesión con /erp start, el bot responde automáticamente a todos tus mensajes.",
        feat_private_title: "100% Privado",
        feat_private_desc: "El bot funciona exclusivamente en DMs. Sin servidor, sin rastros públicos.",
        feat_actions_title: "Acciones Formateadas",
        feat_actions_desc: "Las acciones se escriben entre asteriscos: *ella se acerca a ti* para una inmersión total.",
        feat_nsfw_title: "NSFW Total",
        feat_nsfw_desc: "Contenido erótico explícito permitido y fomentado en DMs. Sin censura, sin restricciones.",

        // How it works
        how_title: "¿Cómo Funciona?",
        how_subtitle: "3 pasos simples para comenzar tu RP erótico",
        step1_title: "Agrega el bot",
        step1_desc: "Invita a KlaraAI a tu DM en Discord. No requiere servidor, todo es privado.",
        step2_title: "Inicia una sesión",
        step2_desc: "Usa /erp start <personaje> para comenzar con Lilith, Isabelle o Chloé.",
        step3_title: "Disfruta",
        step3_desc: "Escribe tus mensajes, el bot responde automáticamente con respuestas inmersivas y detalladas.",

        // Bot Card
        bot_title: "🤖 Usar el bot en Discord",
        bot_desc: "Agrega a KlaraAI a tus contactos de Discord y envíale /help en DM para comenzar.<br>El bot solo funciona en DMs.",
        bot_help: "/help - Ayuda",
        bot_profile: "/profile - Tu perfil",
        bot_premium: "/premium - Suscripción",
        bot_start: "/erp start - Comenzar",
        bot_end: "/erp end - Terminar",
        bot_list: "/erp list - Personajes",

        // Pricing
        pricing_title: "Nuestros Precios",
        pricing_subtitle: "100 créditos = 1 USD • Pago Seguro • Cancelar Cuando Quieras",
        pricing_credits_info: "💡 Sistema de Créditos:",
        pricing_credits_desc: "El bot usa un sistema de créditos.<br>100 créditos = 1 USD. Las suscripciones se cobran en créditos cada mes.",

        free_title: "Prueba Gratuita",
        free_full: "0 /mes",
        free_credits: "0 créditos / mes",

        standard_title: "Standard",
        standard_full: "1600 créditos/mes",
        standard_eur: "~16$ / 15€",
        sub_standard_1600: "1600 créditos",

        premium_title: "Premium",
        premium_full: "3200 créditos/mes",
        premium_eur: "~32$ / 30€",
        sub_premium_3200: "3200 créditos",

        // Credits Shop
        shop_title: "Comprar Créditos",
        shop_subtitle: "100 créditos = 1 USD • Pago Seguro • Entrega Instantánea",
        shop_example: "💡 Ejemplo de conversión:",
        shop_example_desc: "100 créditos = 1 USD • 500 créditos = 5 USD • 1000 créditos = 10 USD<br><small>Las suscripciones cuestan 1600 créditos/mes (Standard) o 3200 créditos/mes (Premium).</small>",

        pack_starter: "Paquete Inicial",
        pack_starter_100: "100 créditos",
        pack_starter_price: "1 USD / 0.90€",
        pack_starter_desc: "Suficiente para unas 5 sesiones completas",

        pack_popular: "Paquete Popular",
        pack_popular_500: "500 créditos",
        pack_popular_price: "5 USD / 4.50€",
        pack_popular_desc: "Suficiente para unas 25 sesiones completas",

        pack_pro: "Paquete Pro",
        pack_pro_1000: "1000 créditos",
        pack_pro_price: "10 USD / 9€",
        pack_pro_desc: "Suficiente para unas 50 sesiones completas",

        pack_elite: "Paquete Elite",
        pack_elite_5000: "5000 créditos",
        pack_elite_price: "50 USD / 45€",
        pack_elite_desc: "Suficiente para unas 250 sesiones completas",

        // Commons
        btn_buy: "Comprar",
        btn_buy_credits: "Comprar Créditos",
        btn_view_pricing: "Ver Precios",
        btn_start: "Comenzar",
        btn_start_free: "Comenzar Gratis",
        btn_coming_soon: "Sistema de pago en desarrollo.\n¡Vuelve más tarde!",
        shop_login_required: "Debes iniciar sesión con Discord para comprar créditos.",
        shop_purchase_success: "¡Compra exitosa! {amount} créditos ({pack}) añadidos. Nuevo saldo: {balance} créditos.",
        how_it_works_title: "📝 ¿Cómo Funciona?",
        how_it_works_desc1: "1. <strong>Comprar créditos</strong> en este sitio (sistema en desarrollo)",
        how_it_works_desc2: "2. <strong>Los créditos se agregan</strong> a tu perfil de Discord vía el bot",
        how_it_works_desc3: "3. <strong>Usa /premium</strong> en Discord para ver tu saldo y actualizar",
        how_it_works_desc4: "4. <strong>¡Disfruta!</strong> El bot debita automáticamente los créditos según tu suscripción",
        note_title: "⚠️ Nota:",
        note_desc: "El sistema de pago está en desarrollo.<br>Por ahora, los créditos son simulados en el bot. El pago real se agregará pronto.",

        // Footer
        footer_desc: "Bot Discord ERP privado para adultos.",
        footer_18plus: "⚠️ Sitio y bot reservados solo para 18+",
        footer_links: "Enlaces",
        footer_legal: "Legal",
        footer_terms: "Términos de Servicio",
        footer_privacy: "Política de Privacidad",
        footer_legal_notice: "Avisos Legales",
        footer_copyright: "© 2026 KlaraAI. Todos los derechos reservados. Sitio reservado para adultos (18+).",

        // Features list
        f_3chars: "3 personajes base",
        f_20msg: "20 mensajes/día",
        f_2sess: "2 sesiones/día",
        f_ctx10: "Contexto: 10 mensajes",
        f_basic_resp: "Respuestas básicas",
        f_3plus2: "3 personajes base + 2 customs",
        f_100msg: "100 mensajes/día",
        f_5sess: "5 sesiones/día",
        f_ctx20: "Contexto: 20 mensajes",
        f_normal_resp: "Respuestas IA normales",
        f_2custom: "Máx 2 personajes customs",
        f_unlimited_chars: "Personajes ilimitados",
        f_unlimited_msg: "Mensajes ilimitados",
        f_unlimited_sess: "Sesiones ilimitadas",
        f_ctx50: "Contexto: 50 mensajes",
        f_priority: "Respuestas IA prioritarias",
        f_unlimited_custom: "Customs ilimitados",
        f_adv_profile: "Config avanzada de perfil",
        f_no_custom: "Personajes customs",
        f_no_priority: "Respuestas prioritarias",

        // Tech details
        tech_title: "📊 Detalles Técnicos:",
        tech_ctx: "<strong>Contexto</strong> = número de mensajes guardados en el historial de la sesión (permanente, no diario)",
        tech_daily: "<strong>Mensajes/día</strong> y <strong>Sesiones/día</strong> = límites diarios (reinician a medianoche)",
        tech_tokens: "<strong>Tokens</strong> = longitud máxima de respuesta (400, 800 o 1200)",
        tech_custom: "<strong>Personajes customs</strong> = personajes creados por el usuario",

        // Subscription
        sub_standard: "Standard (1 mes)",
        sub_premium: "Premium (1 mes)",
        sub_standard_2: "Standard",
        sub_premium_2: "Premium",
        sub_price: "Precio",
    },

    it: {
        // Nav
        nav_home: "Home",
        nav_pricing: "Prezzi",
        nav_buy: "Negozio",
        nav_buy_credits: "Compra Crediti",
        nav_login: "Accedi",

        // Age Verify
        age_title: "⚠️ Accesso Riservato",
        age_desc: "Questo sito e bot sono strettamente riservati a persone di 18 anni o più.",
        age_18plus: "Il contenuto è di natura erotica/pornografica.",
        age_deny: "Ho meno di 18 anni",
        age_confirm: "Ho 18 anni o più",

        // Hero
        hero_title: "KlaraAI",
        hero_desc: "Bot Discord ERP Privato • Roleplay Erotico con IA • 18+",
        hero_btn_pricing: "Vedi Prezzi",
        hero_btn_buy: "Compra Crediti",
        hero_btn_invite: "🤖 Invita Bot",
        hero_btn_commands: "📋 Comandi",

        // Features
        feat_title: "Funzionalità",
        feat_subtitle: "Un bot Discord privato che funziona esclusivamente nei DM",
        feat_3chars_title: "3 Personaggi Unici",
        feat_3chars_desc: "Lilith (Succubo), Isabelle (Matrigna), Chloé (Sorellastra). Ogni personaggio ha la propria personalità e stile.",
        feat_ia_title: "IA Avanzata",
        feat_ia_desc: "Risposte generate dall'IA (llama-3.3-70b) con memoria fino a 50 messaggi.",
        feat_auto_title: "Risposta Automatica",
        feat_auto_desc: "Una volta avviata la sessione con /erp start, il bot risponde automaticamente a tutti i tuoi messaggi.",
        feat_private_title: "100% Privato",
        feat_private_desc: "Il bot funziona esclusivamente nei DM. Nessun server, nessuna traccia pubblica.",
        feat_actions_title: "Azioni Formattate",
        feat_actions_desc: "Le azioni sono scritte tra asterischi: *lei si avvicina a te* per un'immersione totale.",
        feat_nsfw_title: "NSFW Totale",
        feat_nsfw_desc: "Contenuto erotico esplicito consentito e incoraggiato nei DM. Nessuna censura, nessuna restrizione.",

        // How it works
        how_title: "Come Funziona?",
        how_subtitle: "3 semplici passi per iniziare il tuo RP erotico",
        step1_title: "Aggiungi il bot",
        step1_desc: "Invita KlaraAI nei DM su Discord. Nessun server richiesto, tutto avviene in privato.",
        step2_title: "Inizia una sessione",
        step2_desc: "Usa /erp start <personaggio> per iniziare con Lilith, Isabelle o Chloé.",
        step3_title: "Goditi",
        step3_desc: "Scrivi i tuoi messaggi, il bot risponde automaticamente con risposte immersive e dettagliate.",

        // Bot Card
        bot_title: "🤖 Usare il bot su Discord",
        bot_desc: "Aggiungi KlaraAI ai tuoi contatti Discord e inviagli /help in DM per iniziare.<br>Il bot funziona solo nei DM.",
        bot_help: "/help - Aiuto",
        bot_profile: "/profile - Tuo profilo",
        bot_premium: "/premium - Abbonamento",
        bot_start: "/erp start - Inizia",
        bot_end: "/erp end - Termina",
        bot_list: "/erp list - Personaggi",

        // Pricing
        pricing_title: "I Nostri Prezzi",
        pricing_subtitle: "100 crediti = 1 USD • Pagamento Sicuro • Cancella Quando Vuoi",
        pricing_credits_info: "💡 Sistema Crediti:",
        pricing_credits_desc: "Il bot usa un sistema a crediti.<br>100 crediti = 1 USD. Gli abbonamenti sono addebitati in crediti ogni mese.",

        free_title: "Prova Gratuita",
        free_full: "0 /mese",
        free_credits: "0 crediti / mese",

        standard_title: "Standard",
        standard_full: "1600 crediti/mese",
        standard_eur: "~16$ / 15€",
        sub_standard_1600: "1600 crediti",

        premium_title: "Premium",
        premium_full: "3200 crediti/mese",
        premium_eur: "~32$ / 30€",
        sub_premium_3200: "3200 crediti",

        // Credits Shop
        shop_title: "Compra Crediti",
        shop_subtitle: "100 crediti = 1 USD • Pagamento Sicuro • Consegna Istantanea",
        shop_example: "💡 Esempio di conversione:",
        shop_example_desc: "100 crediti = 1 USD • 500 crediti = 5 USD • 1000 crediti = 10 USD<br><small>Gli abbonamenti costano 1600 crediti/mese (Standard) o 3200 crediti/mese (Premium).</small>",

        pack_starter: "Starter Pack",
        pack_starter_100: "100 crediti",
        pack_starter_price: "1 USD / 0.90€",
        pack_starter_desc: "Sufficiente per circa 5 sessioni complete",

        pack_popular: "Popular Pack",
        pack_popular_500: "500 crediti",
        pack_popular_price: "5 USD / 4.50€",
        pack_popular_desc: "Sufficiente per circa 25 sessioni complete",

        pack_pro: "Pro Pack",
        pack_pro_1000: "1000 crediti",
        pack_pro_price: "10 USD / 9€",
        pack_pro_desc: "Sufficiente per circa 50 sessioni complete",

        pack_elite: "Elite Pack",
        pack_elite_5000: "5000 crediti",
        pack_elite_price: "50 USD / 45€",
        pack_elite_desc: "Sufficiente per circa 250 sessioni complete",

        // Commons
        btn_buy: "Compra",
        btn_buy_credits: "Compra Crediti",
        btn_view_pricing: "Vedi Prezzi",
        btn_start: "Inizia",
        btn_start_free: "Inizia Gratis",
        btn_coming_soon: "Sistema di pagamento in sviluppo.\nTorna più tardi!",
        shop_login_required: "Devi accedere con Discord per acquistare crediti.",
        shop_purchase_success: "Acquisto riuscito! {amount} crediti ({pack}) aggiunti. Nuovo saldo: {balance} crediti.",
        how_it_works_title: "📝 Come Funziona?",
        how_it_works_desc1: "1. <strong>Compra crediti</strong> su questo sito (sistema in sviluppo)",
        how_it_works_desc2: "2. <strong>I crediti sono aggiunti</strong> al tuo profilo Discord via il bot",
        how_it_works_desc3: "3. <strong>Usa /premium</strong> in Discord per vedere il saldo e fare upgrade",
        how_it_works_desc4: "4. <strong>Goditi!</strong> Il bot addebita automaticamente i crediti in base al tuo abbonamento",
        note_title: "⚠️ Nota:",
        note_desc: "Il sistema di pagamento è in sviluppo.<br>Per ora, i crediti sono simulati nel bot. Il pagamento reale sarà aggiunto presto.",

        // Footer
        footer_desc: "Bot Discord ERP privato per adulti.",
        footer_18plus: "⚠️ Sito e bot riservati solo per 18+",
        footer_links: "Collegamenti",
        footer_legal: "Legale",
        footer_terms: "Termini di Servizio",
        footer_privacy: "Politica sulla Privacy",
        footer_legal_notice: "Avvisi Legali",
        footer_copyright: "© 2026 KlaraAI. Tutti i diritti riservati. Sito riservato agli adulti (18+).",

        // Features list
        f_3chars: "3 personaggi base",
        f_20msg: "20 messaggi/giorno",
        f_2sess: "2 sessioni/giorno",
        f_ctx10: "Contesto: 10 messaggi",
        f_basic_resp: "Risposte base",
        f_3plus2: "3 personaggi base + 2 customs",
        f_100msg: "100 messaggi/giorno",
        f_5sess: "5 sessioni/giorno",
        f_ctx20: "Contesto: 20 messaggi",
        f_normal_resp: "Risposte IA normali",
        f_2custom: "Max 2 personaggi customs",
        f_unlimited_chars: "Personaggi illimitati",
        f_unlimited_msg: "Messaggi illimitati",
        f_unlimited_sess: "Sessioni illimitate",
        f_ctx50: "Contesto: 50 messaggi",
        f_priority: "Risposte IA prioritàrie",
        f_unlimited_custom: "Customs illimitati",
        f_adv_profile: "Config profilo avanzata",
        f_no_custom: "Personaggi customs",
        f_no_priority: "Risposte prioritàrie",

        // Tech details
        tech_title: "📊 Dettagli Tecnici:",
        tech_ctx: "<strong>Contesto</strong> = numero di messaggi salvati nella cronologia della sessione (permanentemente, non giornaliero)",
        tech_daily: "<strong>Messaggi/giorno</strong> e <strong>Sessioni/giorno</strong> = limiti giornalieri (azzerati a mezzanotte)",
        tech_tokens: "<strong>Tokens</strong> = lunghezza massima risposta (400, 800 o 1200)",
        tech_custom: "<strong>Personaggi customs</strong> = personaggi creati dall'utente",

        // Subscription
        sub_standard: "Standard (1 mese)",
        sub_premium: "Premium (1 mese)",
        sub_standard_2: "Standard",
        sub_premium_2: "Premium",
        sub_price: "Prezzo",
    }
};
