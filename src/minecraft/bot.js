/**
 * Mineflayer Bot Module - JavaScript side of the bridge
 */
const mineflayer = require('mineflayer');
const { pathfinder, Movements, goals } = require('mineflayer-pathfinder');
const winston = require('winston');
const { EventEmitter } = require('events');
const dotenv = require('dotenv');

// Load environment variables
dotenv.config();

// Configure logger
const logger = winston.createLogger({
    level: process.env.LOG_LEVEL || 'info',
    format: winston.format.combine(
        winston.format.timestamp(),
        winston.format.json()
    ),
    transports: [
        new winston.transports.Console()
    ]
});

// Bot event emitter for Python bridge
class BotEventEmitter extends EventEmitter {
    constructor() {
        super();
        this.setMaxListeners(50); // Increase for multiple event types
    }
}

// Main bot class
class MinecraftBot {
    constructor(options) {
        this.options = options;
        this.bot = null;
        this.events = new BotEventEmitter();
        this.movements = null;
        this.commandQueue = [];
        this.isProcessingCommands = false;
    }

    async createBot() {
        logger.info('Creating Mineflayer bot', this.options);

        this.bot = mineflayer.createBot({
            host: this.options.host,
            port: this.options.port,
            username: this.options.username,
            auth: this.options.auth,
            version: false // Auto-detect version
        });

        // Load pathfinder plugin
        this.bot.loadPlugin(pathfinder);

        // Set up event handlers
        this.setupEventHandlers();

        // Wait for spawn
        await new Promise((resolve, reject) => {
            this.bot.once('spawn', () => {
                logger.info('Bot spawned');
                this.setupPathfinder();
                resolve();
            });

            this.bot.once('error', reject);

            // Timeout after 30 seconds
            setTimeout(() => reject(new Error('Spawn timeout')), 30000);
        });

        return this;
    }

    setupPathfinder() {
        // Configure pathfinder movements
        this.movements = new Movements(this.bot);
        this.movements.canDig = true;
        this.movements.scaffoldingBlocks.add(this.bot.registry.itemsByName.cobblestone.id);
        this.movements.scaffoldingBlocks.add(this.bot.registry.itemsByName.dirt.id);

        this.bot.pathfinder.setMovements(this.movements);
        logger.info('Pathfinder configured');
    }

    setupEventHandlers() {
        // Forward all relevant events to Python
        const eventsToForward = [
            'chat', 'whisper', 'actionBar', 'title',
            'health', 'breath', 'spawn', 'death', 'respawn',
            'playerJoined', 'playerLeft', 'playerUpdated',
            'blockUpdate', 'chunkColumnLoad',
            'entitySpawn', 'entityGone', 'entityMoved',
            'kicked', 'error', 'end'
        ];

        eventsToForward.forEach(eventName => {
            this.bot.on(eventName, (...args) => {
                this.handleEvent(eventName, args);
            });
        });

        // Special handling for position updates
        this.bot.on('move', () => {
            this.handleEvent('position', [{
                x: this.bot.entity.position.x,
                y: this.bot.entity.position.y,
                z: this.bot.entity.position.z,
                yaw: this.bot.entity.yaw,
                pitch: this.bot.entity.pitch
            }]);
        });
    }

    handleEvent(eventName, args) {
        try {
            // Convert Minecraft objects to serializable format
            const serializedArgs = this.serializeArgs(args);

            // Emit to Python bridge
            this.events.emit('minecraft_event', {
                type: eventName,
                timestamp: new Date().toISOString(),
                data: serializedArgs
            });

            logger.debug(`Event: ${eventName}`, { args: serializedArgs });
        } catch (error) {
            logger.error(`Error handling event ${eventName}:`, error);
        }
    }

    serializeArgs(args) {
        return args.map(arg => {
            if (arg === null || arg === undefined) return arg;

            // Handle special Minecraft types
            if (arg.username !== undefined) {
                // Player object
                return {
                    username: arg.username,
                    uuid: arg.uuid,
                    entityId: arg.entity?.id,
                    position: arg.entity?.position
                };
            }

            if (arg.position !== undefined && arg.type !== undefined) {
                // Entity object
                return {
                    id: arg.id,
                    type: arg.type,
                    position: arg.position,
                    velocity: arg.velocity,
                    yaw: arg.yaw,
                    pitch: arg.pitch
                };
            }

            if (arg.x !== undefined && arg.y !== undefined && arg.z !== undefined) {
                // Vec3 object
                return { x: arg.x, y: arg.y, z: arg.z };
            }

            // Default: try to convert to plain object
            try {
                return JSON.parse(JSON.stringify(arg));
            } catch {
                return String(arg);
            }
        });
    }

    // Command execution methods
    async executeCommand(command) {
        const { method, args, id } = command;

        try {
            logger.debug(`Executing command: ${method}`, args);

            // Route to appropriate handler
            const result = await this.routeCommand(method, args);

            return {
                id,
                success: true,
                result
            };
        } catch (error) {
            logger.error(`Command failed: ${method}`, error);
            return {
                id,
                success: false,
                error: error.message
            };
        }
    }

    async routeCommand(method, args) {
        const handlers = {
            // Movement commands
            'pathfinder.goto': async ({ x, y, z }) => {
                const goal = new goals.GoalBlock(x, y, z);
                await this.bot.pathfinder.goto(goal);
                return { position: { x, y, z } };
            },

            'pathfinder.follow': async ({ username, range = 3 }) => {
                const player = this.bot.players[username];
                if (!player) throw new Error(`Player ${username} not found`);

                const goal = new goals.GoalFollow(player.entity, range);
                this.bot.pathfinder.setGoal(goal, true);
                return { following: username };
            },

            'pathfinder.stop': async () => {
                this.bot.pathfinder.stop();
                return { stopped: true };
            },

            // Block interaction
            'dig': async ({ x, y, z }) => {
                const block = this.bot.blockAt(new Vec3(x, y, z));
                if (!block) throw new Error('No block at position');

                await this.bot.dig(block);
                return { dug: true, block: block.name };
            },

            'placeBlock': async ({ x, y, z, face = 'top' }) => {
                const referenceBlock = this.bot.blockAt(new Vec3(x, y, z));
                const faceVector = this.getFaceVector(face);

                await this.bot.placeBlock(referenceBlock, faceVector);
                return { placed: true };
            },

            // Inventory
            'inventory.items': async () => {
                return this.bot.inventory.items().map(item => ({
                    name: item.name,
                    count: item.count,
                    slot: item.slot
                }));
            },

            'inventory.equip': async ({ item, destination = 'hand' }) => {
                const itemObj = this.bot.inventory.items().find(i => i.name === item);
                if (!itemObj) throw new Error(`Item ${item} not found`);

                await this.bot.equip(itemObj, destination);
                return { equipped: item };
            },

            // Chat
            'chat': async ({ message }) => {
                this.bot.chat(message);
                return { sent: true };
            },

            // Information queries
            'entity.position': async () => {
                return this.bot.entity.position;
            },

            'entity.health': async () => {
                return {
                    health: this.bot.health,
                    food: this.bot.food,
                    saturation: this.bot.foodSaturation
                };
            },

            'world.getBlock': async ({ x, y, z }) => {
                const block = this.bot.blockAt(new Vec3(x, y, z));
                return {
                    name: block?.name,
                    type: block?.type,
                    hardness: block?.hardness
                };
            },

            'world.findBlocks': async ({ name, maxDistance = 64, count = 1 }) => {
                const blockType = this.bot.registry.blocksByName[name];
                if (!blockType) throw new Error(`Unknown block type: ${name}`);

                const blocks = this.bot.findBlocks({
                    matching: blockType.id,
                    maxDistance,
                    count
                });

                return blocks.map(pos => ({ x: pos.x, y: pos.y, z: pos.z }));
            }
        };

        const handler = handlers[method];
        if (!handler) {
            throw new Error(`Unknown command: ${method}`);
        }

        return await handler(args);
    }

    getFaceVector(face) {
        const faces = {
            top: new Vec3(0, 1, 0),
            bottom: new Vec3(0, -1, 0),
            north: new Vec3(0, 0, -1),
            south: new Vec3(0, 0, 1),
            east: new Vec3(1, 0, 0),
            west: new Vec3(-1, 0, 0)
        };
        return faces[face] || faces.top;
    }

    // Python bridge interface methods
    on(event, handler) {
        this.events.on(event, handler);
    }

    once(event, handler) {
        this.events.once(event, handler);
    }

    quit() {
        if (this.bot) {
            this.bot.quit();
        }
    }
}

// Vec3 import
const { Vec3 } = mineflayer;

// Export functions for Python bridge
async function createBot(options) {
    const bot = new MinecraftBot(options);
    await bot.createBot();
    return bot;
}

module.exports = { createBot };
