// ============================================
// KlaraAI Website - Main JavaScript
// ============================================

// Language management
let currentLang = 'fr';

function changeLanguage(lang) {
    currentLang = lang;
    localStorage.setItem('klaraai_lang', lang);
    applyTranslations(lang);
    document.documentElement.lang = lang;
}

function applyTranslations(lang) {
    if (!translations[lang]) return;

    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        if (translations[lang][key]) {
            if (el.tagName === 'TITLE') {
                el.textContent = translations[lang][key];
            } else {
                el.innerHTML = translations[lang][key];
            }
        }
    });

    const selector = document.getElementById('lang-selector');
    if (selector) {
        selector.value = lang;
    }
}

function translate(key) {
    return translations[currentLang] && translations[currentLang][key]
        ? translations[currentLang][key]
        : translations['fr'][key] || key;
}

// Age Verification
function confirmAge() {
    document.getElementById('age-verify').classList.add('hidden');
    localStorage.setItem('klaraai_age_verified', 'true');
}

function denyAge() {
    document.body.innerHTML = `
        <div style="display: flex; justify-content: center; align-items: center; height: 100vh; background: #1a1a2e; color: #eee; text-align: center; padding: 2rem;">
            <div>
                <h1 style="color: #e74c3c; font-size: 3rem;">⚠️ Accès Refusé</h1>
                <p style="font-size: 1.2rem; margin-top: 1rem;">${translate('age_desc')}</p>
                <p style="margin-top: 2rem;"><a href="https://www.google.com" style="color: #9b59b6;">${translate('age_deny')}</a></p>
            </div>
        </div>
    `;
}

// ============================================
// Theme Management
// ============================================
function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'light' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('klaraai_theme', newTheme);
    updateThemeButton(newTheme);
}

function updateThemeButton(theme) {
    const btn = document.getElementById('theme-toggle-btn');
    if (btn) {
        btn.textContent = theme === 'light' ? '🌙' : '☀️';
        btn.title = theme === 'light' ? 'Mode sombre' : 'Mode clair';
    }
}

// ============================================
// Discord Authentication
// ============================================
const DISCORD_CLIENT_ID = '1500196432211349634';
const DISCORD_REDIRECT_URI = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
    ? 'http://localhost:8000'
    : 'https://www.klaraai.me';
const DISCORD_SCOPES = 'identify';

function loginWithDiscord() {
    const authUrl = `https://discord.com/api/oauth2/authorize?client_id=${DISCORD_CLIENT_ID}&redirect_uri=${encodeURIComponent(DISCORD_REDIRECT_URI)}&response_type=token&scope=${DISCORD_SCOPES}`;
    window.location.href = authUrl;
}

function handleAuthCallback() {
    const hash = window.location.hash.substring(1);
    if (!hash) return;

    const params = new URLSearchParams(hash);
    const accessToken = params.get('access_token');
    const tokenType = params.get('token_type');
    const expiresIn = params.get('expires_in');

    if (accessToken) {
        localStorage.setItem('discord_access_token', accessToken);
        localStorage.setItem('discord_token_type', tokenType);
        localStorage.setItem('discord_token_expires', Date.now() + (expiresIn * 1000));

        window.history.replaceState({}, document.title, window.location.pathname + window.location.search);

        fetchDiscordUser(accessToken);
    }
}

async function fetchDiscordUser(token) {
    try {
        const response = await fetch('https://discord.com/api/users/@me', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (response.ok) {
            const user = await response.json();
            localStorage.setItem('discord_user', JSON.stringify(user));

            // Update user in API
            try {
                await apiRequest('/api/users/update', {
                    method: 'POST'
                });
            } catch(e) {}

            updateDiscordUI(user);
            updateCreditsDisplay(user);
            loadUserDashboard(user);
        } else {
            console.error('Failed to fetch Discord user');
            logoutDiscord();
        }
    } catch (error) {
        console.error('Error fetching Discord user:', error);
    }
}

function updateDiscordUI(user) {
    const authDiv = document.getElementById('discord-auth');
    const userDiv = document.getElementById('discord-user');
    const avatarImg = document.getElementById('user-avatar');
    const nameSpan = document.getElementById('user-name');

    if (authDiv) authDiv.style.display = 'none';
    if (userDiv) userDiv.style.display = 'flex';

    if (user && avatarImg && nameSpan) {
        const avatarUrl = user.avatar
            ? `https://cdn.discordapp.com/avatars/${user.id}/${user.avatar}.png?size=64`
            : `https://cdn.discordapp.com/embed/avatars/${user.discriminator % 5}.png`;
        avatarImg.src = avatarUrl;
        nameSpan.textContent = user.username;
    }
}

function logoutDiscord() {
    localStorage.removeItem('discord_access_token');
    localStorage.removeItem('discord_token_type');
    localStorage.removeItem('discord_token_expires');
    localStorage.removeItem('discord_user');

    const authDiv = document.getElementById('discord-auth');
    const userDiv = document.getElementById('discord-user');

    if (authDiv) authDiv.style.display = 'flex';
    if (userDiv) userDiv.style.display = 'none';
}

function getDiscordUser() {
    const userStr = localStorage.getItem('discord_user');
    return userStr ? JSON.parse(userStr) : null;
}

function isDiscordLoggedIn() {
    const token = localStorage.getItem('discord_access_token');
    const expires = localStorage.getItem('discord_token_expires');
    if (!token) return false;
    if (expires && Date.now() > parseInt(expires)) {
        logoutDiscord();
        return false;
    }
    return true;
}

// ============================================
// Credits Management (API-based)
// ============================================
const API_BASE = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
    ? 'http://localhost:3000'
    : 'https://klaraai.onrender.com';

async function apiRequest(endpoint, options = {}) {
    const token = localStorage.getItem('discord_access_token');
    const headers = {
        'Content-Type': 'application/json',
        ...options.headers
    };
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }
    try {
        const res = await fetch(`${API_BASE}${endpoint}`, {
            ...options,
            headers
        });
        return await res.json();
    } catch (e) {
        console.error('[API] Request failed:', e);
        return null;
    }
}

async function updateCreditsDisplay(user) {
    if (!user) return;

    const bar = document.getElementById('user-credits-bar');
    const username = document.getElementById('credits-username');
    const balance = document.getElementById('credits-balance');

    if (bar && username && balance) {
        bar.style.display = 'block';
        username.textContent = user.username;
        const credits = await getUserCredits(user.id);
        balance.textContent = credits;
    }
}

async function getUserCredits(discordId) {
    const data = await apiRequest(`/api/credits?discord_id=${discordId}`);
    return data ? data.credits : 0;
}

async function loadUserDashboard(user) {
    if (!user) return;
    const panel = document.getElementById('user-dashboard');
    if (!panel) return;

    let dash = null;
    try {
        dash = await apiRequest(`/api/user/dashboard?discord_id=${user.id}`);
    } catch (e) {
        console.warn('[Dashboard] fetch failed:', e);
    }

    panel.style.display = 'block';

    const avatarUrl = user.avatar
        ? `https://cdn.discordapp.com/avatars/${user.id}/${user.avatar}.png?size=64`
        : `https://cdn.discordapp.com/embed/avatars/${(user.discriminator || 0) % 5}.png`;
    const avatarEl = document.getElementById('dash-avatar');
    if (avatarEl) avatarEl.src = avatarUrl;

    const usernameEl = document.getElementById('dash-username');
    if (usernameEl) usernameEl.textContent = user.username;

    if (!dash) {
        // Render empty defaults; avoid showing "Welcome —, 0/0/0".
        document.getElementById('dash-credits').textContent = '0';
        document.getElementById('dash-credits-usd').textContent = '$0.00';
        document.getElementById('dash-total-purchased').textContent = '0';
        document.getElementById('dash-referrals').textContent = '0';
        return;
    }

    const credits = dash.credits || 0;
    document.getElementById('dash-credits').textContent = credits.toLocaleString();
    document.getElementById('dash-credits-usd').textContent = '$' + (credits / 100).toFixed(2);
    document.getElementById('dash-total-purchased').textContent = (dash.total_purchased || 0).toLocaleString();
    document.getElementById('dash-referrals').textContent = (dash.referral_count || 0);

    const histWrap = document.getElementById('dash-history-wrap');
    const histList = document.getElementById('dash-history-list');
    const history = Array.isArray(dash.history) ? dash.history : [];
    if (histWrap && histList && history.length) {
        histList.innerHTML = '';
        history.forEach(h => {
            const li = document.createElement('li');
            const amount = parseInt(h.amount) || 0;
            const sign = amount >= 0 ? '+' : '';
            const cls = amount >= 0 ? 'up' : 'down';
            const date = h.timestamp ? new Date(h.timestamp).toLocaleDateString() : '';
            const label = h.pack_name || (amount >= 0 ? 'Credits added' : 'Credits used');
            li.innerHTML = `
                <span class="h-amount ${cls}">${sign}${amount.toLocaleString()}</span>
                <span class="h-label">${label.replace(/[<>]/g, '')}</span>
                <span class="h-date">${date}</span>
            `;
            histList.appendChild(li);
        });
        histWrap.style.display = 'block';
    } else if (histWrap) {
        histWrap.style.display = 'none';
    }
}

async function buyCredits(amount, packName, priceUSD) {
    if (!isDiscordLoggedIn()) {
        const warning = document.getElementById('login-warning');
        if (warning) warning.style.display = 'block';
        return;
    }

    const user = getDiscordUser();
    if (!user) return;

    try {
        const response = await fetch(`${API_BASE}/api/create-checkout`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('discord_access_token')}`
            },
            body: JSON.stringify({
                pack_name: packName,
                amount: amount,
                price_usd: priceUSD
            })
        });

        const data = await response.json();
        if (data.url) {
            window.location.href = data.url;
        } else {
            alert('❌ Error: ' + (data.error || 'An error occurred'));
        }
    } catch (e) {
        console.error('[Stripe] Checkout error:', e);
        alert('❌ Connection error to API.');
    }
}

// ============================================
// Commands Modal
// ============================================
function showCommands() {
    document.getElementById('commands-modal').classList.add('active');
}

function closeCommands() {
    document.getElementById('commands-modal').classList.remove('active');
}

// ============================================
// Unified Load Handler
// ============================================
window.addEventListener('load', function() {
    // Language
    const lang = localStorage.getItem('klaraai_lang') || 'fr';
    currentLang = lang;

    // Age verification
    const verified = localStorage.getItem('klaraai_age_verified');
    if (verified === 'true') {
        const ageVerify = document.getElementById('age-verify');
        if (ageVerify) ageVerify.classList.add('hidden');
    }

    applyTranslations(lang);
    document.documentElement.lang = lang;

    // Theme
    const savedTheme = localStorage.getItem('klaraai_theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);
    updateThemeButton(savedTheme);

    // Discord Auth callback
    handleAuthCallback();

    // Check Discord login state
    if (isDiscordLoggedIn()) {
        const user = getDiscordUser();
        if (user) {
            updateDiscordUI(user);
            updateCreditsDisplay(user);
            loadUserDashboard(user);
        } else {
            const token = localStorage.getItem('discord_access_token');
            if (token) fetchDiscordUser(token);
        }
    } else {
        const warning = document.getElementById('login-warning');
        if (warning) warning.style.display = 'block';
    }

    // Animations
    if ('IntersectionObserver' in window) {
        animateOnScroll();
    }
});

// Smooth scroll for anchor links
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({ behavior: 'smooth' });
        }
    });
});

// Navbar scroll effect
window.addEventListener('scroll', function() {
    const nav = document.querySelector('nav');
    if (nav) {
        nav.classList.toggle('scrolled', window.scrollY > 30);
    }
});

// Add animation on scroll
function animateOnScroll() {
    const elements = document.querySelectorAll('.feature-card, .pricing-card, .shop-card, .step');
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
            }
        });
    }, { threshold: 0.1 });

    elements.forEach(el => {
        el.style.opacity = '0';
        el.style.transform = 'translateY(30px)';
        el.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
        observer.observe(el);
    });
}

// Pricing card hover effect
document.querySelectorAll('.pricing-card, .shop-card').forEach(card => {
    card.addEventListener('mouseenter', function() {
        this.style.boxShadow = '0 10px 30px rgba(155, 89, 182, 0.3)';
    });
    card.addEventListener('mouseleave', function() {
        this.style.boxShadow = 'none';
    });
});

// Close modal on outside click
document.addEventListener('click', function(e) {
    const modal = document.getElementById('commands-modal');
    if (modal && e.target === modal) {
        closeCommands();
    }
});

// Close modal on ESC key
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        closeCommands();
    }
});

// ============================================
// Cookie / local-storage consent (GDPR)
// ============================================
// We use localStorage for: age verification, language, theme, Discord OAuth
// token, and cookie consent itself. None of it is tracking, but EU rules
// still require explicit consent for non-strictly-necessary storage.
const CONSENT_KEY = 'klaraai_cookie_consent';
const CONSENT_VALUES = { ACCEPTED: 'accepted', REJECTED: 'rejected' };

function getCookieConsent() {
    try { return localStorage.getItem(CONSENT_KEY); } catch (e) { return null; }
}

function hasCookieConsent() {
    return getCookieConsent() === CONSENT_VALUES.ACCEPTED;
}

function injectCookieBanner() {
    if (document.getElementById('cookie-banner')) return;
    const lang = (localStorage.getItem('klaraai_lang') || 'fr').toLowerCase();
    const t = {
        fr: {
            title: '🍪 Préférences de stockage',
            body: "On utilise le stockage local de ton navigateur uniquement pour mémoriser ton thème, ta langue, ta vérification d'âge et ta connexion Discord. Aucun cookie publicitaire, aucun tracker tiers. Voir notre <a href=\"/privacy\">politique de confidentialité</a>.",
            accept: 'Accepter',
            reject: 'Refuser',
        },
        en: {
            title: '🍪 Storage preferences',
            body: 'We only use your browser local storage to remember your theme, language, age verification and Discord login. No advertising cookies, no third-party trackers. See our <a href="/privacy">privacy policy</a>.',
            accept: 'Accept',
            reject: 'Reject',
        },
        es: {
            title: '🍪 Preferencias de almacenamiento',
            body: 'Solo usamos el almacenamiento local del navegador para recordar tu tema, idioma, verificación de edad y sesión Discord. Sin cookies publicitarias ni rastreadores. Ver nuestra <a href="/privacy">política de privacidad</a>.',
            accept: 'Aceptar',
            reject: 'Rechazar',
        },
        it: {
            title: '🍪 Preferenze di archiviazione',
            body: 'Usiamo il local storage solo per ricordare tema, lingua, verifica età e login Discord. Nessun cookie pubblicitario, nessun tracker. Vedi la <a href="/privacy">privacy policy</a>.',
            accept: 'Accetta',
            reject: 'Rifiuta',
        },
    };
    const i = t[lang] || t.en;
    const div = document.createElement('div');
    div.className = 'cookie-banner';
    div.id = 'cookie-banner';
    div.innerHTML = `
        <div class="ck-title">${i.title}</div>
        <p>${i.body}</p>
        <div class="ck-actions">
            <button class="ck-btn ck-reject" id="ck-reject">${i.reject}</button>
            <button class="ck-btn ck-accept" id="ck-accept">${i.accept}</button>
        </div>
    `;
    document.body.appendChild(div);
    document.getElementById('ck-accept').addEventListener('click', () => acceptCookies());
    document.getElementById('ck-reject').addEventListener('click', () => rejectCookies());
    requestAnimationFrame(() => div.classList.add('visible'));
}

function showCookieBanner() {
    injectCookieBanner();
    const el = document.getElementById('cookie-banner');
    if (el) el.classList.add('visible');
}

function hideCookieBanner() {
    const el = document.getElementById('cookie-banner');
    if (el) el.classList.remove('visible');
    setTimeout(() => { if (el && el.parentNode) el.parentNode.removeChild(el); }, 400);
}

function acceptCookies() {
    try { localStorage.setItem(CONSENT_KEY, CONSENT_VALUES.ACCEPTED); } catch (e) {}
    hideCookieBanner();
}

function rejectCookies() {
    // Wipe non-essential storage AND mark the choice. Keep ONLY the consent
    // flag itself (so we don't re-prompt every reload — that would be hostile).
    try {
        const keysToWipe = [
            'klaraai_age_verified',
            'klaraai_lang',
            'klaraai_theme',
            'discord_access_token',
            'discord_token_type',
            'discord_token_expires',
            'discord_user',
        ];
        keysToWipe.forEach(k => localStorage.removeItem(k));
        localStorage.setItem(CONSENT_KEY, CONSENT_VALUES.REJECTED);
    } catch (e) {}
    // Logging out also resets the displayed UI
    try { logoutDiscord(); } catch (e) {}
    hideCookieBanner();
}

// Re-open the banner from the footer "Cookie preferences" link.
function openCookiePreferences() {
    showCookieBanner();
}

// Show the banner on first visit only.
window.addEventListener('load', function () {
    if (!getCookieConsent()) {
        // Wait a beat so it doesn't fight the age-verify modal.
        setTimeout(showCookieBanner, 600);
    }
});

// ============================================
// Live Activity Counter (simulated random walk)
// ============================================
// Goal: a believable "X active sessions" number that drifts realistically.
// - Range clamps: 95 .. 380
// - Updates every 2-5s with small deltas (-3..+5 most of the time)
// - Larger jumps (-12..+15) are rare (~5%)
// - Drift toward a time-of-day target (more activity late evening/night)
function startLiveCounter() {
    const elCount = document.getElementById('live-count');
    const elDelta = document.getElementById('live-delta');
    if (!elCount) return;

    const hour = new Date().getHours();
    // Late-night / evening sees more sessions; mid-day fewer
    const targetByHour = (h) => {
        if (h >= 21 || h < 3) return 280;
        if (h >= 18) return 220;
        if (h >= 12) return 170;
        if (h >= 7) return 140;
        return 200; // 3am-7am: night-owl crowd
    };
    let target = targetByHour(hour);
    let value = target + Math.floor(Math.random() * 40) - 20;

    const render = (delta) => {
        elCount.textContent = value;
        if (delta !== 0 && elDelta) {
            elDelta.textContent = (delta > 0 ? '+' : '') + delta;
            elDelta.classList.toggle('up', delta > 0);
            elDelta.classList.toggle('down', delta < 0);
            elDelta.classList.add('show');
            elCount.classList.toggle('bump-up', delta > 0);
            elCount.classList.toggle('bump-down', delta < 0);
            setTimeout(() => {
                elDelta.classList.remove('show');
                elCount.classList.remove('bump-up', 'bump-down');
            }, 1400);
        }
    };

    render(0);

    const tick = () => {
        const r = Math.random();
        let delta;
        if (r < 0.7) {
            // Small natural breathing: -3 .. +5
            delta = Math.floor(Math.random() * 9) - 3;
        } else if (r < 0.95) {
            // Moderate change: -6 .. +8
            delta = Math.floor(Math.random() * 15) - 6;
        } else {
            // Rare burst (group joining / leaving): -12 .. +15
            delta = Math.floor(Math.random() * 28) - 12;
        }

        // Gentle drift toward the time-of-day target so the value doesn't
        // wander off forever
        if (value < target - 60) delta += 1;
        else if (value > target + 80) delta -= 1;

        const newValue = Math.max(95, Math.min(380, value + delta));
        const realDelta = newValue - value;
        value = newValue;
        render(realDelta);

        // Refresh the time-of-day target every minute roughly
        if (Math.random() < 0.02) target = targetByHour(new Date().getHours());

        // Next tick in 2.0s - 5.0s
        const nextDelay = 2000 + Math.random() * 3000;
        setTimeout(tick, nextDelay);
    };

    setTimeout(tick, 1500);
}

window.addEventListener('load', startLiveCounter);

console.log('%cKlaraAI Website', 'color: #9b59b6; font-size: 20px; font-weight: bold;');
console.log('%cSite réservé aux 18+ ans', 'color: #e74c3c; font-size: 14px;');
