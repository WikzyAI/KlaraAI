// ============================================
// KlaraAI Discord Bot - API Integration
// ============================================
// Copy the functions below into your Discord bot code.
// Make sure to set API_BASE to match your API URL.
//
// Required: npm install node-fetch@2
// ============================================

const fetch = require('node-fetch');
const API_BASE = process.env.API_BASE || 'http://localhost:3000';

// Get user credits from the website API
// Returns: { discord_id, username, credits }
async function getCredits(discordId) {
    try {
        const res = await fetch(`${API_BASE}/api/credits?discord_id=${discordId}`);
        if (res.ok) {
            return await res.json();
        } else {
            console.error('[API] Failed to get credits:', await res.text());
        }
    } catch (e) {
        console.error('[API] Error fetching credits:', e.message);
    }
    return { discord_id: discordId, username: 'Unknown', credits: 0 };
}

// Add credits to a user (admin command or gift)
// Requires API_SECRET in environment for admin auth
async function addCredits(discordId, amount, username) {
    try {
        const res = await fetch(`${API_BASE}/api/credits/add`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${process.env.API_SECRET}`
            },
            body: JSON.stringify({
                discord_id: discordId,
                amount: amount,
                pack_name: 'Bot Gift',
                username: username
            })
        });
        if (res.ok) {
            return await res.json();
        }
    } catch (e) {
        console.error('[API] Error adding credits:', e.message);
    }
    return null;
}

// ============================================
// Example: /profile command
// ============================================
/*
// If you use discord.js v14:
const { SlashCommandBuilder } = require('discord.js');

// Command definition
const profileCommand = new SlashCommandBuilder()
    .setName('profile')
    .setDescription('View your profile and credit balance');

// In your interaction handler:
if (interaction.commandName === 'profile') {
    const userId = interaction.user.id;

    await interaction.deferReply({ ephemeral: true });

    const data = await getCredits(userId);

    const { EmbedBuilder } = require('discord.js');
    const embed = new EmbedBuilder()
        .setColor(0x9b59b6)
        .setTitle('💎 Your Profile')
        .addFields(
            { name: 'User', value: `<@${userId}>`, inline: true },
            { name: 'Credits', value: `**${data.credits} credits**`, inline: true },
            { name: 'Value', value: `$${(data.credits / 100).toFixed(2)}`, inline: true }
        )
        .setFooter({ text: 'Credits purchased on klaraai.com' })
        .setTimestamp();

    await interaction.editReply({ embeds: [embed] });
}

// ============================================
// Example: /premium command (check subscription level)
// ============================================
const premiumCommand = new SlashCommandBuilder()
    .setName('premium')
    .setDescription('Check your subscription status');

if (interaction.commandName === 'premium') {
    const userId = interaction.user.id;

    await interaction.deferReply({ ephemeral: true });

    const data = await getCredits(userId);

    const { EmbedBuilder } = require('discord.js');
    const embed = new EmbedBuilder()
        .setColor(0x9b59b6)
        .setTitle('💎 Subscription Status')
        .setDescription(`Your current balance: **${data.credits} credits**`)
        .addFields(
            {
                name: 'Standard (1600 credits/month)',
                value: data.credits >= 1600 ? '✅ Active' : '❌ Inactive',
                inline: false
            },
            {
                name: 'Premium (3200 credits/month)',
                value: data.credits >= 3200 ? '✅ Active' : '❌ Inactive',
                inline: false
            }
        )
        .setFooter({ text: 'Buy credits on klaraai.com' })
        .setTimestamp();

    await interaction.editReply({ embeds: [embed] });
}

// ============================================
// Setup: Register slash commands (run once)
// ============================================
async function registerCommands(botToken, clientId) {
    const commands = [profileCommand.toJSON(), premiumCommand.toJSON()];
    try {
        const res = await fetch(`https://discord.com/api/v10/applications/${clientId}/commands`, {
            method: 'PUT',
            headers: {
                'Authorization': `Bot ${botToken}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(commands)
        });
        if (res.ok) {
            console.log('[Bot] Slash commands registered!');
        } else {
            console.error('[Bot] Failed to register commands:', await res.text());
        }
    } catch (e) {
        console.error('[Bot] Error registering commands:', e.message);
    }
}

// Call this after bot login:
// registerCommands(process.env.DISCORD_BOT_TOKEN, 'YOUR_CLIENT_ID');
*/

module.exports = { getCredits, addCredits };
