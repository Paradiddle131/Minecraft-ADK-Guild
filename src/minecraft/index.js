/**
 * Main entry point for the Minecraft bot system
 */
const { createBot } = require('./bot.js');
const dotenv = require('dotenv');

// Load environment variables
dotenv.config();

// Main function to start bot
async function startBot(options = {}) {
    const defaultOptions = {
        host: process.env.MC_SERVER_HOST || 'localhost',
        port: parseInt(process.env.MC_SERVER_PORT) || 25565,
        username: process.env.MC_BOT_USERNAME || 'MinecraftAgent',
        auth: process.env.MC_BOT_AUTH || 'offline'
    };

    const botOptions = { ...defaultOptions, ...options };


    try {
        // Create bot
        const bot = await createBot(botOptions);

        // Return bot interface for bridge
        return {
            bot: bot,
            executeCommand: async (cmd) => {
                try {
                    const result = await bot.executeCommand(cmd);
                    return result;
                } catch (error) {
                    console.error(`Command ${cmd.method} error:`, error);
                    return {
                        id: cmd.id,
                        success: false,
                        error: error.message || error.toString()
                    };
                }
            },
            quit: () => bot.quit()
        };

    } catch (error) {
        console.error('Failed to start bot:', error);
        throw error;
    }
}

// For direct Node.js execution
if (require.main === module) {
    // Run in standalone mode
    startBot().catch(console.error);
}

module.exports = { startBot, createBot };
