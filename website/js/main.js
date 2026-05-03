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
    : 'https://klaraai.vercel.app';
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

async function buyCredits(amount, packName) {
    if (!isDiscordLoggedIn()) {
        const warning = document.getElementById('login-warning');
        if (warning) warning.style.display = 'block';
        return;
    }

    const user = getDiscordUser();
    if (!user) return;

    const result = await apiRequest('/api/credits/add', {
        method: 'POST',
        body: JSON.stringify({
            discord_id: user.id,
            amount: amount,
            pack_name: packName
        })
    });

    if (result && result.success) {
        const message = translate('shop_purchase_success')
            .replace('{pack}', packName)
            .replace('{amount}', amount)
            .replace('{balance}', result.new_balance);
        alert(`✅ ${message}`);
        await updateCreditsDisplay(user);
    } else {
        alert('❌ Erreur lors de l\'achat. Vérifiez que l\'API est démarrée (cd api && npm start).');
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
        nav.style.boxShadow = window.scrollY > 50
            ? '0 2px 20px rgba(0,0,0,0.3)'
            : 'none';
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

console.log('%cKlaraAI Website', 'color: #9b59b6; font-size: 20px; font-weight: bold;');
console.log('%cSite réservé aux 18+ ans', 'color: #e74c3c; font-size: 14px;');
