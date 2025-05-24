/**
 * Main entry point for the Minecraft bot system
 */
const { createBot } = require('./bot.js');
const { EventClient, integrateEventClient } = require('./event_client.js');
const dotenv = require('dotenv');

// Load environment variables
dotenv.config();

// Main function to start bot with optional event streaming
async function startBot(options = {}) {
    const defaultOptions = {
        host: process.env.MC_SERVER_HOST || 'localhost',
        port: parseInt(process.env.MC_SERVER_PORT) || 25565,
        username: process.env.MC_BOT_USERNAME || 'MinecraftAgent',
        auth: process.env.MC_BOT_AUTH || 'offline',
        enableEventClient: true  // Can be disabled for standalone mode
    };

    const botOptions = { ...defaultOptions, ...options };

    console.log('Starting Minecraft bot with options:', botOptions);

    try {
        // Create bot
        const bot = await createBot(botOptions);
        console.log('Bot created successfully');

        let eventClient = null;

        // Optionally create event client
        if (botOptions.enableEventClient) {
            try {
                eventClient = new EventClient(
                    parseInt(process.env.BRIDGE_PORT) || 8765
                );

                // Connect event client with timeout
                await Promise.race([
                    eventClient.connect(),
                    new Promise((_, reject) => 
                        setTimeout(() => reject(new Error('Event client connection timeout')), 5000)
                    )
                ]);
                
                console.log('Event client connected');

                // Integrate bot with event client
                integrateEventClient(bot, eventClient);
            } catch (error) {
                console.warn('Failed to connect to event client, running without event streaming:', error.message);
                eventClient = null;
            }
        }

        // Return both for external control
        return { bot, eventClient };

    } catch (error) {
        console.error('Failed to start bot:', error);
        throw error;
    }
}

// For direct Node.js execution
if (require.main === module) {
    // Run in standalone mode without event client
    startBot({ enableEventClient: false }).catch(console.error);
}

module.exports = { startBot, createBot };
