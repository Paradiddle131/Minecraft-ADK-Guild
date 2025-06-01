/**
 * Mineflayer Bot Module - JavaScript side of the bridge
 */
const mineflayer = require('mineflayer');
const { pathfinder, Movements, goals } = require('mineflayer-pathfinder');
const { Vec3 } = require('vec3');
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
        winston.format.timestamp({ format: 'YYYY-MM-DD HH:mm:ss' }),
        winston.format.colorize(),
        winston.format.printf(({ timestamp, level, message }) => {
            return `${timestamp} [${level}     ] [JS]: ${message}`;
        })
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
            version: this.options.version || process.env.MINECRAFT_AGENT_MINECRAFT_VERSION || '1.21.1'
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

            // Timeout after 30 seconds for spawn
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

        // Crafting events
        // Note: supportFeature check removed as it may not be available during initialization
        // The 'craft' event will simply not fire if crafting is not available
        this.bot.on('craft', (recipe, result) => {
            this.eventEmitter.emitItemCraftEvent(recipe.name, result, recipe.ingredients);
        });

        // Consumption events
        this.bot.on('consume', () => {
            const heldItem = this.bot.heldItem;
            if (heldItem && heldItem.name) {
                // Food data now handled by Python MinecraftDataService
                this.eventEmitter.emitItemConsumeEvent(heldItem, 0, 0);
            }
        });

        // Error and connection events - forward to legacy handler
        const legacyEvents = ['error', 'end', 'kicked'];
        legacyEvents.forEach(eventName => {
            this.bot.on(eventName, (...args) => {
                // Stop pathfinding on disconnect events
                if (eventName === 'end' || eventName === 'kicked') {
                    if (this.bot.pathfinder) {
                        logger.info(`Bot ${eventName} event - stopping pathfinder`);
                        this.bot.pathfinder.stop();
                    }
                }
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
            'pathfinder.goto': async ({ x, y, z, timeout }) => {
                // Timeout must be provided by Python caller
                if (!timeout) {
                    throw new Error('Movement timeout not specified - must be provided by caller');
                }
                const goal = new goals.GoalBlock(x, y, z);
                const startPos = this.bot.entity.position.clone();

                try {
                    // Check if pathfinder is properly loaded
                    if (!this.bot.pathfinder) {
                        throw new Error('Pathfinder plugin not loaded');
                    }

                    const startTime = Date.now();
                    console.log(`Starting pathfinding to (${x}, ${y}, ${z}) from (${startPos.x.toFixed(1)}, ${startPos.y.toFixed(1)}, ${startPos.z.toFixed(1)})`);

                    // Track progress
                    let lastProgressUpdate = 0;
                    let lastChatUpdate = 0;
                    let pathStatus = 'computing';
                    let timeoutId = null;
                    let stuckCount = 0;
                    let lastDistance = null;
                    const chatUpdateInterval = 5000; // 5 seconds between chat updates
                    const stuckThreshold = 3;

                    // Initial distance calculation
                    const initialDistance = Math.sqrt(
                        Math.pow(startPos.x - x, 2) +
                        Math.pow(startPos.y - y, 2) +
                        Math.pow(startPos.z - z, 2)
                    );

                    // Send initial chat message
                    this.bot.chat(`I'm at (${Math.floor(startPos.x)}, ${Math.floor(startPos.y)}, ${Math.floor(startPos.z)}) and I'm on my way to (${x}, ${y}, ${z}). Distance: ${initialDistance.toFixed(1)} blocks`);

                    if (initialDistance > 5) {
                        await new Promise(resolve => setTimeout(resolve, 100));
                        this.bot.chat(`Starting navigation to (${x}, ${y}, ${z}) - will update every 5 seconds...`);
                    }

                    // Progress tracking using interval timer instead of events
                    let progressInterval = null;
                    let movementComplete = false;

                    const sendProgressUpdate = () => {
                        if (movementComplete) return;

                        const now = Date.now();
                        const currentPos = this.bot.entity.position;
                        const distanceToGoal = Math.sqrt(
                            Math.pow(currentPos.x - x, 2) +
                            Math.pow(currentPos.y - y, 2) +
                            Math.pow(currentPos.z - z, 2)
                        );

                        console.log(`Progress check: distance=${distanceToGoal.toFixed(1)}, moving=${this.bot.pathfinder.isMoving()}`);

                        // Emit progress event for Python
                        if (this.eventEmitter) {
                            this.eventEmitter.emitMovementProgressEvent({
                                target: { x, y, z },
                                current_position: {
                                    x: Math.floor(currentPos.x),
                                    y: Math.floor(currentPos.y),
                                    z: Math.floor(currentPos.z)
                                },
                                distance_remaining: distanceToGoal,
                                path_status: this.bot.pathfinder.isMoving() ? 'moving' : 'idle',
                                elapsed_time: now - startTime
                            });
                        }

                        // Send chat updates every 5 seconds for long movements
                        if (initialDistance > 5 && now - lastChatUpdate > chatUpdateInterval) {
                            console.log(`Sending chat update: distance=${distanceToGoal.toFixed(1)}, lastDistance=${lastDistance}`);

                            // Check if stuck
                            if (lastDistance !== null && Math.abs(lastDistance - distanceToGoal) < 0.5) {
                                stuckCount++;
                                console.log(`Bot might be stuck: stuckCount=${stuckCount}`);
                                if (stuckCount >= stuckThreshold) {
                                    this.bot.chat(`Navigation appears stuck at ${distanceToGoal.toFixed(1)} blocks - may need manual help`);
                                } else {
                                    this.bot.chat(`Navigation progress: ${distanceToGoal.toFixed(1)} blocks remaining (might be finding path around obstacles)`);
                                }
                            } else {
                                // Normal progress
                                stuckCount = 0;
                                const progressMade = initialDistance - distanceToGoal;
                                const progressPercent = (progressMade / initialDistance) * 100;
                                console.log(`Sending normal progress: ${progressPercent.toFixed(0)}% complete`);
                                this.bot.chat(`Moving... ${distanceToGoal.toFixed(1)} blocks remaining (${progressPercent.toFixed(0)}% complete)`);
                            }

                            lastDistance = distanceToGoal;
                            lastChatUpdate = now;

                            // Stop updates if stuck for too long
                            if (stuckCount >= stuckThreshold + 2) {
                                console.log('Bot appears stuck after multiple updates, stopping progress reporting');
                                clearInterval(progressInterval);
                                progressInterval = null;
                            }

                            // Stop if very close to target
                            if (distanceToGoal < 2) {
                                console.log('Very close to target, stopping progress updates');
                                clearInterval(progressInterval);
                                progressInterval = null;
                            }
                        }
                    };

                    // Start progress updates for long movements
                    if (initialDistance > 5) {
                        console.log(`Starting progress interval for distance ${initialDistance.toFixed(1)}`);
                        progressInterval = setInterval(sendProgressUpdate, 1000); // Check every second
                    }

                    // Create movement promise
                    const movementPromise = new Promise(async (resolve, reject) => {
                        try {
                            // Set timeout
                            timeoutId = setTimeout(() => {
                                console.log('Movement timeout - stopping pathfinder');
                                this.bot.pathfinder.stop();
                                reject(new Error(`Movement timeout after ${timeout}ms`));
                            }, timeout);

                            // Execute goto and wait for completion
                            await this.bot.pathfinder.goto(goal);

                            // Clear timeout on success
                            if (timeoutId) {
                                clearTimeout(timeoutId);
                                timeoutId = null;
                            }

                            resolve();
                        } catch (error) {
                            // Clear timeout on error
                            if (timeoutId) {
                                clearTimeout(timeoutId);
                                timeoutId = null;
                            }
                            reject(error);
                        }
                    });

                    // Wait for movement to complete
                    await movementPromise;

                    // Get actual position after movement
                    const pos = this.bot.entity.position;
                    const distance = Math.sqrt(
                        Math.pow(pos.x - x, 2) +
                        Math.pow(pos.y - y, 2) +
                        Math.pow(pos.z - z, 2)
                    );

                    const totalTime = Date.now() - startTime;
                    console.log(`Reached destination (${x}, ${y}, ${z}) in ${totalTime}ms, actual distance: ${distance.toFixed(2)}`);

                    // Stop progress updates
                    movementComplete = true;
                    if (progressInterval) {
                        clearInterval(progressInterval);
                        progressInterval = null;
                        console.log('Cleared progress interval - movement completed');
                    }

                    // Send completion message
                    this.bot.chat(`Arrived at (${Math.floor(pos.x)}, ${Math.floor(pos.y)}, ${Math.floor(pos.z)})`);

                    return {
                        target: { x, y, z },
                        actual_position: {
                            x: Math.floor(pos.x),
                            y: Math.floor(pos.y),
                            z: Math.floor(pos.z)
                        },
                        distance_to_target: distance,
                        status: 'completed',
                        message: 'Movement completed successfully',
                        duration_ms: totalTime
                    };

                } catch (error) {
                    console.error(`Pathfinding failed:`, error);

                    // Stop progress updates on error
                    movementComplete = true;
                    if (progressInterval) {
                        clearInterval(progressInterval);
                        progressInterval = null;
                        console.log('Cleared progress interval - movement failed');
                    }

                    // Get current position even on failure
                    const pos = this.bot.entity.position;
                    const partialDistance = Math.sqrt(
                        Math.pow(pos.x - startPos.x, 2) +
                        Math.pow(pos.y - startPos.y, 2) +
                        Math.pow(pos.z - startPos.z, 2)
                    );

                    const errorMsg = error.message || error.toString();

                    // Check for specific error types
                    if (errorMsg.includes('timeout')) {
                        this.bot.chat(`Movement timed out after ${timeout}ms. Try again or increase the timeout.`);
                        throw new Error(`Movement timeout: Failed to reach (${x}, ${y}, ${z}) within ${timeout}ms`);
                    } else if (errorMsg.includes('No path')) {
                        this.bot.chat('Movement failed - couldn\'t reach destination');
                        throw new Error(`No path found to (${x}, ${y}, ${z}). The location may be blocked or unreachable.`);
                    } else {
                        this.bot.chat('Movement failed - couldn\'t reach destination');
                        throw new Error(`Movement failed: ${errorMsg}`);
                    }
                }
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

            'pathfinder.isMoving': async () => {
                return {
                    isMoving: this.bot.pathfinder.isMoving(),
                    goal: this.bot.pathfinder.goal
                };
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
                if (!referenceBlock) throw new Error('No block at reference position');

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
                if (!this.bot) throw new Error('Bot not initialized');
                if (!this.bot.entity) throw new Error('Bot entity not available - bot may not be spawned');
                if (!this.bot.entity.position) throw new Error('Bot position not available');
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
            },

            // Additional simplified action handlers for Python BotController
            'js_lookAt': async ({ x, y, z }) => {
                this.bot.lookAt(new Vec3(x, y, z));
                return { looked_at: { x, y, z } };
            },

            'js_stopDigging': async () => {
                this.bot.stopDigging();
                return { stopped: true };
            },

            'js_activateItem': async () => {
                this.bot.activateItem();
                return { activated: true };
            },

            'js_deactivateItem': async () => {
                this.bot.deactivateItem();
                return { deactivated: true };
            },

            'js_useOnBlock': async ({ x, y, z }) => {
                const block = this.bot.blockAt(new Vec3(x, y, z));
                if (!block) throw new Error('No block at position');

                await this.bot.activateBlock(block);
                return { used_on: { x, y, z } };
            },

            'js_attackEntity': async ({ entity_id }) => {
                const entity = this.bot.entities[entity_id];
                if (!entity) throw new Error(`Entity ${entity_id} not found`);

                this.bot.attack(entity);
                return { attacked: entity_id };
            },

            'js_dropItem': async ({ item_name, count = null }) => {
                const item = this.bot.inventory.items().find(i => i.name === item_name);
                if (!item) throw new Error(`Item ${item_name} not found in inventory`);

                await this.bot.tossStack(item, count);
                return { dropped: item_name, count: count || item.count };
            },

            // Crafting
            'craft': async ({ recipe: itemName, count = 1 }) => {
                try {
                    logger.info(`Attempting to craft ${count} ${itemName}`);

                    // Handle common naming variations
                    let normalizedName = itemName;

                    // Handle plural/singular variations
                    if (itemName === 'sticks') normalizedName = 'stick';

                    // Handle generic planks request - try to craft from available logs
                    if (itemName === 'planks') {
                        // Find what type of log we have
                        const logTypes = ['oak_log', 'birch_log', 'spruce_log', 'dark_oak_log', 'acacia_log', 'jungle_log', 'mangrove_log', 'cherry_log'];
                        const inventory = this.bot.inventory.items();

                        for (const item of inventory) {
                            if (logTypes.includes(item.name)) {
                                // Determine the plank type based on log type
                                normalizedName = item.name.replace('_log', '_planks');
                                logger.info(`Converting generic 'planks' request to '${normalizedName}' based on available ${item.name}`);
                                break;
                            }
                        }

                        // If no logs found, check if we already have some planks
                        if (normalizedName === 'planks') {
                            const plankTypes = ['oak_planks', 'birch_planks', 'spruce_planks', 'dark_oak_planks', 'acacia_planks', 'jungle_planks', 'mangrove_planks', 'cherry_planks'];
                            for (const item of inventory) {
                                if (plankTypes.includes(item.name)) {
                                    normalizedName = item.name; // Use existing plank type
                                    logger.info(`Using existing '${normalizedName}' for generic 'planks' request`);
                                    break;
                                }
                            }
                        }

                        // If still no match, default to oak_planks
                        if (normalizedName === 'planks') {
                            normalizedName = 'oak_planks';
                            logger.info(`Defaulting generic 'planks' request to 'oak_planks'`);
                        }
                    }

                    // Handle other common variations
                    if (itemName === 'sticks' || itemName === 'stick') {
                        normalizedName = 'stick';
                    }

                    // Get the item from registry
                    const item = this.bot.registry.itemsByName[normalizedName];
                    if (!item) {
                        return {
                            success: false,
                            error: `Unknown item: ${itemName}`
                        };
                    }

                    // Check if we need a crafting table - assume any recipe not craftable in 2x2 needs table
                    // Python MinecraftDataService now determines this
                    let craftingTable = null;

                    // Try to find a crafting table nearby - let Python decide if needed
                    craftingTable = this.bot.findBlock({
                        matching: this.bot.registry.blocksByName.crafting_table.id,
                        maxDistance: 4
                    });

                    // Get recipes for this item
                    const recipes = this.bot.recipesFor(item.id, null, 1, craftingTable);

                    if (!recipes || recipes.length === 0) {
                        return {
                            success: false,
                            error: `No recipe found for ${itemName}`
                        };
                    }

                    // Use the first available recipe
                    const recipe = recipes[0];

                    // Check if we have the required materials
                    const missingMaterials = await this.checkMissingMaterials(recipe, count);

                    if (Object.keys(missingMaterials).length > 0) {
                        return {
                            success: false,
                            error: `Cannot craft ${itemName}: missing materials`,
                            missing_materials: missingMaterials
                        };
                    }

                    // Actually craft the item
                    try {
                        await this.bot.craft(recipe, count, craftingTable);
                        logger.info(`Successfully crafted ${count} ${itemName}`);

                        return {
                            success: true,
                            crafted: count,
                            recipe: itemName,
                            message: `Crafted ${count} ${itemName}`
                        };
                    } catch (craftError) {
                        logger.error(`Crafting failed for ${itemName}:`, craftError);

                        // Try to provide more specific error info
                        if (craftError.message.includes('materials')) {
                            // Re-check materials for better error reporting
                            const missing = await this.checkMissingMaterials(recipe, count);
                            return {
                                success: false,
                                error: `Crafting failed: ${craftError.message}`,
                                missing_materials: missing
                            };
                        }

                        throw craftError;
                    }

                } catch (error) {
                    logger.error('Crafting error:', error);
                    return {
                        success: false,
                        error: error.message || 'Crafting failed'
                    };
                }
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

    // Data lookup methods removed - now handled by Python MinecraftDataService

    async checkMissingMaterials(recipe, count = 1) {
        const missing = {};
        const inventory = this.bot.inventory.items();

        // Count required materials
        const required = {};

        // Handle both shaped and shapeless recipes
        const ingredients = recipe.inShape || recipe.ingredients || [];

        for (const row of ingredients) {
            if (Array.isArray(row)) {
                // Shaped recipe with rows
                for (const slot of row) {
                    if (slot && slot.id !== -1) {
                        const item = this.bot.registry.items[slot.id];
                        if (item) {
                            const totalNeeded = (slot.count || 1) * count;
                            required[item.name] = (required[item.name] || 0) + totalNeeded;
                        }
                    }
                }
            } else if (row && row.id !== -1) {
                // Shapeless recipe or single item
                const item = this.bot.registry.items[row.id];
                if (item) {
                    const totalNeeded = (row.count || 1) * count;
                    required[item.name] = (required[item.name] || 0) + totalNeeded;
                }
            }
        }

        // Check what we have
        const have = {};
        for (const item of inventory) {
            have[item.name] = (have[item.name] || 0) + item.count;
        }

        // Calculate missing
        for (const [itemName, needCount] of Object.entries(required)) {
            const haveCount = have[itemName] || 0;
            if (haveCount < needCount) {
                missing[itemName] = needCount - haveCount;
            }
        }

        return missing;
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

// Export functions for Python bridge
async function createBot(options) {
    const bot = new MinecraftBot(options);
    await bot.createBot();
    return bot;
}

module.exports = { createBot };
