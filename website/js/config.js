// ============================================
// KlaraAI Website - Configuration
// ============================================

const CONFIG = {
    // Discord OAuth2
    DISCORD: {
        CLIENT_ID: '1500196432211349634',
        REDIRECT_URI: (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
            ? 'http://localhost:8000'
            : window.location.origin,
        SCOPES: 'identify',
        RESPONSE_TYPE: 'token'
    },

    // API
    API: {
        BASE_URL: (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
            ? 'http://localhost:3000'
            : window.location.origin,
        ENDPOINTS: {
            CREDITS: '/api/credits',
            ADD_CREDITS: '/api/credits/add',
            UPDATE_USER: '/api/users/update',
            HEALTH: '/api/health',
            LEADERBOARD: '/api/leaderboard'
        }
    },

    // Feature flags
    FEATURES: {
        DARK_MODE: true,
        DISCORD_AUTH: true,
        CREDITS_SYSTEM: true,
        COMMANDS_MODAL: true
    }
};

// Helper to build Discord OAuth2 URL
function getDiscordAuthURL() {
    const { CLIENT_ID, REDIRECT_URI, SCOPES, RESPONSE_TYPE } = CONFIG.DISCORD;
    return `https://discord.com/api/oauth2/authorize?client_id=${CLIENT_ID}&redirect_uri=${encodeURIComponent(REDIRECT_URI)}&response_type=${RESPONSE_TYPE}&scope=${SCOPES}`;
}
