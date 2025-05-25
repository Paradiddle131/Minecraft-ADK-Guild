/**
 * Mineflayer Bot Module - JavaScript side of the bridge
 */
const mineflayer = require('mineflayer');
const { pathfinder, Movements, goals } = require('mineflayer-pathfinder');
const winston = require('winston');
const { EventEmitter } = require('events');
const dotenv = require('dotenv');
const { MinecraftEventEmitter } = require('./MinecraftEventEmitter');

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
        this.eventEmitter = null; // Will be initialized after bot creation
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

        // Initialize event emitter with bot
        this.eventEmitter = new MinecraftEventEmitter(this.bot);

        // Set up event handlers
        this.setupEventHandlers();

        // Wait for spawn
        await new Promise((resolve, reject) => {
            this.bot.once('spawn', () => {
                logger.info('Bot spawned');
                this.setupPathfinder();
                
                // Emit standardized spawn event using event emitter
                this.eventEmitter.emitSpawnEvent();
                logger.info('Emitted minecraft:spawn event via MinecraftEventEmitter');
                
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
        this.movements.scafoldingBlocks.push(this.bot.registry.itemsByName.cobblestone.id);
        this.movements.scafoldingBlocks.push(this.bot.registry.itemsByName.dirt.id);

        this.bot.pathfinder.setMovements(this.movements);
        logger.info('Pathfinder configured');
    }

    setupEventHandlers() {
        // Chat events
        this.bot.on('chat', (username, message) => {
            this.eventEmitter.emitChatEvent(username, message);
        });

        // Player events
        this.bot.on('playerJoined', (player) => {
            this.eventEmitter.emitPlayerJoinedEvent(player);
        });

        this.bot.on('playerLeft', (player) => {
            this.eventEmitter.emitPlayerLeftEvent(player);
        });

        this.bot.on('playerUpdated', (player) => {
            this.eventEmitter.emitPlayerUpdatedEvent(player);
        });

        // Health events
        this.bot.on('health', () => {
            this.eventEmitter.emitHealthEvent();
        });

        // Position updates (throttled)
        let lastPositionEmit = 0;
        const positionThrottle = 1000; // Emit position max once per second
        
        this.bot.on('move', () => {
            const now = Date.now();
            if (now - lastPositionEmit > positionThrottle) {
                this.eventEmitter.emitPositionEvent();
                lastPositionEmit = now;
            }
        });

        // Block events
        this.bot.on('blockUpdate', (oldBlock, newBlock) => {
            this.eventEmitter.emitBlockUpdateEvent(oldBlock, newBlock);
        });

        // Advanced world events
        this.bot.on('diggingCompleted', (block) => {
            this.eventEmitter.emitBlockBreakEvent(block, this.bot.username, this.bot.heldItem?.name);
        });

        this.bot.on('chunkColumnLoad', (point) => {
            this.eventEmitter.emitChunkLoadEvent(point.x, point.z);
        });

        this.bot.on('chunkColumnUnload', (point) => {
            this.eventEmitter.emitChunkUnloadEvent(point.x, point.z);
        });

        // Weather and time events with throttling
        let lastWeatherState = null;
        let lastTimeEmit = 0;
        const timeEmitThrottle = 30000; // 30 seconds

        this.bot.on('weatherUpdate', () => {
            const currentWeather = this.bot.thunderState ? 'thunder' : 
                                 this.bot.rainState > 0 ? 'rain' : 'clear';
            
            if (lastWeatherState && lastWeatherState !== currentWeather) {
                this.eventEmitter.emitWeatherChangeEvent(
                    lastWeatherState, 
                    currentWeather,
                    this.bot.thunderState > 0,
                    this.bot.rainState > 0
                );
            }
            lastWeatherState = currentWeather;
        });

        this.bot.on('time', () => {
            const now = Date.now();
            if (now - lastTimeEmit > timeEmitThrottle) {
                this.eventEmitter.emitTimeChangeEvent(
                    this.bot.time.timeOfDay,
                    this.bot.time.age
                );
                lastTimeEmit = now;
            }
        });

        // Entity events
        this.bot.on('entitySpawn', (entity) => {
            this.eventEmitter.emitEntitySpawnEvent(entity);
        });

        this.bot.on('entityGone', (entity) => {
            this.eventEmitter.emitEntityDeathEvent(entity);
        });

        // Entity movement tracking with throttling
        const entityMoveThrottle = new Map(); // entity_id -> last_emit_time
        const entityMoveDelay = 2000; // 2 seconds between entity move events
        
        this.bot.on('entityMoved', (entity) => {
            const now = Date.now();
            const lastEmit = entityMoveThrottle.get(entity.id) || 0;
            
            if (now - lastEmit > entityMoveDelay) {
                const oldPos = entity.position; // This might need adjustment based on mineflayer API
                this.eventEmitter.emitEntityMoveEvent(entity, oldPos, entity.position);
                entityMoveThrottle.set(entity.id, now);
            }
        });

        // Bot death and respawn events
        this.bot.on('death', () => {
            const deathMessage = this.bot.game?.deathScore?.deathMessage || 'Unknown cause';
            this.eventEmitter.emitBotDeathEvent(deathMessage, null);
        });

        this.bot.on('respawn', () => {
            this.eventEmitter.emitBotRespawnEvent();
        });

        // Inventory events
        this.bot.on('windowUpdate', (slot, _oldItem, newItem) => {
            if (slot < this.bot.inventory.inventoryStart || 
                slot >= this.bot.inventory.inventoryEnd) {
                return; // Only track main inventory
            }
            
            const inventorySlot = slot - this.bot.inventory.inventoryStart;
            this.eventEmitter.emitInventoryChangeEvent(inventorySlot, newItem);
        });

        // Container events
        this.bot.on('windowOpen', (window) => {
            this.eventEmitter.emitContainerOpenEvent(window);
        });

        this.bot.on('windowClose', (window) => {
            this.eventEmitter.emitContainerCloseEvent(window);
        });

        // Item drop/pickup events
        this.bot.on('playerCollect', (collector, collected) => {
            if (collector.username === this.bot.username) {
                this.eventEmitter.emitItemPickupEvent(collected);
            }
        });

        // Crafting events (if available)
        if (this.bot.supportFeature('craft')) {
            this.bot.on('craft', (recipe, result) => {
                this.eventEmitter.emitItemCraftEvent(recipe.name, result, recipe.ingredients);
            });
        }

        // Consumption events
        this.bot.on('consume', () => {
            const heldItem = this.bot.heldItem;
            if (heldItem && heldItem.name) {
                // Estimate food points and saturation (these might not be directly available)
                const foodPoints = this.getFoodPoints(heldItem.name);
                const saturation = this.getSaturation(heldItem.name);
                this.eventEmitter.emitItemConsumeEvent(heldItem, foodPoints, saturation);
            }
        });

        // Error and connection events - forward to legacy handler
        const legacyEvents = ['error', 'end', 'kicked'];
        legacyEvents.forEach(eventName => {
            this.bot.on(eventName, (...args) => {
                this.handleEvent(eventName, args);
            });
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

    getFoodPoints(itemName) {
        // Basic food points mapping - could be expanded with a proper food database
        const foodValues = {
            'apple': 4,
            'bread': 5,
            'cooked_beef': 8,
            'cooked_chicken': 6,
            'cooked_porkchop': 8,
            'golden_apple': 4,
            'cookie': 2,
            'cake': 14
        };
        return foodValues[itemName] || 0;
    }

    getSaturation(itemName) {
        // Basic saturation mapping
        const saturationValues = {
            'apple': 2.4,
            'bread': 6.0,
            'cooked_beef': 12.8,
            'cooked_chicken': 7.2,
            'cooked_porkchop': 12.8,
            'golden_apple': 9.6,
            'cookie': 0.4,
            'cake': 0.4
        };
        return saturationValues[itemName] || 0;
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
