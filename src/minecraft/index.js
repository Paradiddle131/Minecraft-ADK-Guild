/**
 * Main entry point for the Minecraft bot system
 */
const { createBot } = require('./bot.js');
const { EventClient, integrateEventClient } = require('./event_client.js');
const dotenv = require('dotenv');

// Load environment variables
dotenv.config();

// Main function to start bot with event streaming
async function startBot(options = {}) {
    const defaultOptions = {
        host: process.env.MC_SERVER_HOST || 'localhost',
        port: parseInt(process.env.MC_SERVER_PORT) || 25565,
        username: process.env.MC_BOT_USERNAME || 'MinecraftAgent',
        auth: process.env.MC_BOT_AUTH || 'offline'
    };

    const botOptions = { ...defaultOptions, ...options };

    console.log('Starting Minecraft bot with options:', botOptions);

    try {
        // Create bot
        const bot = await createBot(botOptions);
        console.log('Bot created successfully');

        // Create event client
        const eventClient = new EventClient(
            parseInt(process.env.BRIDGE_PORT) || 8765
        );

        // Connect event client
        await eventClient.connect();
        console.log('Event client connected');

        // Integrate bot with event client
        integrateEventClient(bot, eventClient);

        // Return both for external control
        return { bot, eventClient };

    } catch (error) {
        console.error('Failed to start bot:', error);
        throw error;
    }
}

// For direct Node.js execution
if (require.main === module) {
    startBot().catch(console.error);
}

module.exports = { startBot, createBot };
