/**
 * Minecraft Event Emitter - Centralized event emission for Minecraft-to-Python bridge
 */
const { EventEmitter } = require('events');
const winston = require('winston');

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

class MinecraftEventEmitter extends EventEmitter {
    constructor(bot) {
        super();
        this.bot = bot;
        this.botId = bot.username;
        this.setMaxListeners(100);
        
        this.eventStats = {
            totalEmitted: 0,
            byType: {},
            errors: 0
        };
        
        this.debugMode = process.env.EVENT_DEBUG_MODE === 'true';
        
        logger.info('MinecraftEventEmitter initialized', { 
            botId: this.botId,
            debugMode: this.debugMode 
        });
    }
    
    /**
     * Emit a standardized event to Python bridge
     * @param {string} eventName - The event name (without minecraft: prefix)
     * @param {object} data - Event-specific data
     * @param {object} options - Additional options (priority, batch, etc.)
     */
    emitToPython(eventName, data, options = {}) {
        try {
            const payload = this.createStandardPayload(eventName, data, options);
            
            // Generate unique event ID for tracking
            const eventId = `${this.botId}_${eventName}_${payload.timestamp}_${Math.random().toString(36).substr(2, 9)}`;
            payload.eventId = eventId;
            
            // Emit with minecraft: namespace
            const fullEventName = `minecraft:${eventName}`;
            this.bot.emit(fullEventName, payload);
            
            // Update statistics
            this.updateStats(fullEventName);
            
            // Log event emission lifecycle
            this.logEventEmission(fullEventName, payload, eventId);
            
            return payload;
            
        } catch (error) {
            this.eventStats.errors++;
            logger.error('Failed to emit event to Python', {
                eventName,
                data,
                error: error.message,
                botId: this.botId
            });
            throw error;
        }
    }
    
    /**
     * Create standardized event payload
     * @param {string} eventName - The event name
     * @param {object} data - Event data
     * @param {object} options - Additional options
     * @returns {object} Standardized payload
     */
    createStandardPayload(eventName, data, options = {}) {
        const timestamp = Date.now();
        
        const payload = {
            event: `minecraft:${eventName}`,
            data: this.sanitizeData(data),
            timestamp,
            botId: this.botId,
            metadata: {
                worldTime: this.bot.time?.age || 0,
                dimension: this.bot.game?.dimension || 'unknown',
                serverVersion: this.bot.version || 'unknown',
                ...options.metadata
            }
        };
        
        // Add optional fields if provided
        if (options.priority !== undefined) {
            payload.priority = options.priority;
        }
        
        if (options.batchId) {
            payload.batchId = options.batchId;
        }
        
        return payload;
    }
    
    /**
     * Sanitize data to ensure it's JSON serializable
     * @param {any} data - Data to sanitize
     * @returns {any} Sanitized data
     */
    sanitizeData(data) {
        if (data === null || data === undefined) {
            return data;
        }
        
        if (typeof data === 'string' || typeof data === 'number' || typeof data === 'boolean') {
            return data;
        }
        
        if (Array.isArray(data)) {
            return data.map(item => this.sanitizeData(item));
        }
        
        if (typeof data === 'object') {
            // Handle special Minecraft objects
            if (data.username !== undefined) {
                // Player object
                return {
                    username: data.username,
                    uuid: data.uuid,
                    entityId: data.entity?.id,
                    position: this.sanitizePosition(data.entity?.position),
                    ping: data.ping
                };
            }
            
            if (data.position !== undefined && data.type !== undefined) {
                // Entity object
                return {
                    id: data.id,
                    type: data.type,
                    position: this.sanitizePosition(data.position),
                    velocity: this.sanitizePosition(data.velocity),
                    yaw: data.yaw,
                    pitch: data.pitch,
                    health: data.health,
                    name: data.name
                };
            }
            
            if (data.x !== undefined && data.y !== undefined && data.z !== undefined) {
                // Vec3 object
                return this.sanitizePosition(data);
            }
            
            if (data.name !== undefined && data.type !== undefined) {
                // Block object
                return {
                    name: data.name,
                    type: data.type,
                    hardness: data.hardness,
                    position: this.sanitizePosition(data.position)
                };
            }
            
            // Generic object - recursively sanitize
            const sanitized = {};
            for (const [key, value] of Object.entries(data)) {
                try {
                    sanitized[key] = this.sanitizeData(value);
                } catch (error) {
                    // If we can't sanitize a field, convert to string
                    sanitized[key] = String(value);
                }
            }
            return sanitized;
        }
        
        // Fallback: convert to string
        return String(data);
    }
    
    /**
     * Sanitize position objects (Vec3)
     * @param {object} pos - Position object
     * @returns {object|null} Sanitized position
     */
    sanitizePosition(pos) {
        if (!pos || typeof pos !== 'object') {
            return null;
        }
        
        return {
            x: typeof pos.x === 'number' ? pos.x : 0,
            y: typeof pos.y === 'number' ? pos.y : 0,
            z: typeof pos.z === 'number' ? pos.z : 0
        };
    }
    
    /**
     * Update event statistics
     * @param {string} eventName - The event name
     */
    updateStats(eventName) {
        this.eventStats.totalEmitted++;
        this.eventStats.byType[eventName] = (this.eventStats.byType[eventName] || 0) + 1;
    }
    
    /**
     * Log event emission for debugging
     * @param {string} eventName - The event name
     * @param {object} payload - The event payload
     * @param {string} eventId - The unique event ID
     */
    logEventEmission(eventName, payload, eventId) {
        const logData = {
            event: eventName,
            eventId: eventId,
            botId: this.botId,
            timestamp: payload.timestamp,
            payloadSize: JSON.stringify(payload).length,
            dataKeys: Object.keys(payload.data || {}),
            stage: 'emitted'
        };
        
        // Always log emission for lifecycle tracking
        logger.debug('Event lifecycle: emitted', logData);
        
        // Debug mode provides additional detail
        if (this.debugMode) {
            logger.debug('Event emission details', {
                ...logData,
                fullPayload: payload
            });
        }
    }
    
    /**
     * Get event statistics
     * @returns {object} Event statistics
     */
    getStats() {
        return {
            ...this.eventStats,
            uptime: Date.now() - this.startTime,
            eventsPerSecond: this.eventStats.totalEmitted / ((Date.now() - this.startTime) / 1000)
        };
    }
    
    /**
     * Reset event statistics
     */
    resetStats() {
        this.eventStats = {
            totalEmitted: 0,
            byType: {},
            errors: 0
        };
        this.startTime = Date.now();
    }
    
    /**
     * Emit spawn event with proper data
     */
    emitSpawnEvent() {
        this.emitToPython('spawn', {
            spawned: true,
            position: this.sanitizePosition(this.bot.entity?.position),
            time: Date.now(),
            health: this.bot.health,
            food: this.bot.food
        }, { priority: 100 });
    }
    
    /**
     * Emit chat event
     * @param {string} username - The username who sent the message
     * @param {string} message - The chat message
     */
    emitChatEvent(username, message) {
        this.emitToPython('chat', {
            username,
            message,
            time: Date.now()
        }, { priority: 50 });
    }
    
    /**
     * Emit position update event
     */
    emitPositionEvent() {
        const pos = this.bot.entity?.position;
        if (!pos) return;
        
        this.emitToPython('position', {
            x: pos.x,
            y: pos.y,
            z: pos.z,
            yaw: this.bot.entity.yaw,
            pitch: this.bot.entity.pitch,
            time: Date.now()
        }, { priority: 5 });
    }
    
    /**
     * Emit health update event
     */
    emitHealthEvent() {
        this.emitToPython('health', {
            health: this.bot.health,
            food: this.bot.food,
            saturation: this.bot.foodSaturation,
            time: Date.now()
        }, { priority: 75 });
    }
    
    /**
     * Emit player joined event
     * @param {object} player - The player object
     */
    emitPlayerJoinedEvent(player) {
        this.emitToPython('player_joined', {
            username: player.username,
            uuid: player.uuid,
            time: Date.now()
        }, { priority: 30 });
    }
    
    /**
     * Emit player left event
     * @param {object} player - The player object
     */
    emitPlayerLeftEvent(player) {
        this.emitToPython('player_left', {
            username: player.username,
            uuid: player.uuid,
            time: Date.now()
        }, { priority: 30 });
    }
    
    /**
     * Emit player updated event
     * @param {object} player - The player object
     */
    emitPlayerUpdatedEvent(player) {
        this.emitToPython('player_updated', {
            username: player.username,
            uuid: player.uuid,
            position: this.sanitizePosition(player.entity?.position),
            ping: player.ping,
            gamemode: player.gameMode,
            time: Date.now()
        }, { priority: 10 });
    }
    
    /**
     * Emit entity move event
     * @param {object} entity - The entity object
     * @param {object} oldPos - Previous position
     * @param {object} newPos - New position
     */
    emitEntityMoveEvent(entity, oldPos, newPos) {
        this.emitToPython('entity_move', {
            entity_id: entity.id,
            entity_type: entity.type,
            old_position: this.sanitizePosition(oldPos),
            new_position: this.sanitizePosition(newPos),
            velocity: this.sanitizePosition(entity.velocity),
            time: Date.now()
        }, { priority: 5 });
    }
    
    /**
     * Emit entity damage event
     * @param {object} entity - The entity object
     * @param {number} damage - Damage amount
     * @param {string} cause - Damage cause
     * @param {number} attackerId - Attacker entity ID
     */
    emitEntityDamageEvent(entity, damage, cause, attackerId) {
        this.emitToPython('entity_damage', {
            entity_id: entity.id,
            entity_type: entity.type,
            damage: damage,
            cause: cause,
            attacker_id: attackerId,
            time: Date.now()
        }, { priority: 30 });
    }
    
    /**
     * Emit bot death event
     * @param {string} cause - Death cause
     * @param {string} killer - Killer name
     */
    emitBotDeathEvent(cause, killer) {
        this.emitToPython('bot_death', {
            cause: cause,
            position: this.sanitizePosition(this.bot.entity?.position),
            killer: killer,
            time: Date.now()
        }, { priority: 100 });
    }
    
    /**
     * Emit bot respawn event
     */
    emitBotRespawnEvent() {
        this.emitToPython('bot_respawn', {
            position: this.sanitizePosition(this.bot.entity?.position),
            dimension: this.bot.game?.dimension || 'overworld',
            time: Date.now()
        }, { priority: 90 });
    }
    
    /**
     * Emit block update event
     * @param {object} oldBlock - The old block
     * @param {object} newBlock - The new block
     */
    emitBlockUpdateEvent(oldBlock, newBlock) {
        this.emitToPython('block_update', {
            position: this.sanitizePosition(newBlock.position),
            old_block: oldBlock?.name,
            new_block: newBlock.name,
            time: Date.now()
        }, { priority: 10 });
    }
    
    /**
     * Emit block break event
     * @param {object} block - The broken block
     * @param {string} player - Player who broke it
     * @param {string} tool - Tool used
     */
    emitBlockBreakEvent(block, player, tool) {
        this.emitToPython('block_break', {
            position: this.sanitizePosition(block.position),
            block_type: block.type?.toString(),
            block_name: block.name,
            tool_used: tool,
            player: player,
            time: Date.now()
        }, { priority: 40 });
    }
    
    /**
     * Emit block place event
     * @param {object} block - The placed block
     * @param {string} player - Player who placed it
     */
    emitBlockPlaceEvent(block, player) {
        this.emitToPython('block_place', {
            position: this.sanitizePosition(block.position),
            block_type: block.type?.toString(),
            block_name: block.name,
            placed_by: player,
            time: Date.now()
        }, { priority: 40 });
    }
    
    /**
     * Emit explosion event
     * @param {object} position - Explosion center
     * @param {number} power - Explosion power
     * @param {array} affectedBlocks - List of affected blocks
     * @param {string} cause - Explosion cause
     */
    emitExplosionEvent(position, power, affectedBlocks, cause) {
        this.emitToPython('explosion', {
            position: this.sanitizePosition(position),
            power: power,
            affected_blocks: affectedBlocks.map(pos => this.sanitizePosition(pos)),
            cause: cause,
            time: Date.now()
        }, { priority: 80 });
    }
    
    /**
     * Emit weather change event
     * @param {string} oldWeather - Previous weather
     * @param {string} newWeather - New weather
     * @param {boolean} thundering - Is thundering
     * @param {boolean} raining - Is raining
     */
    emitWeatherChangeEvent(oldWeather, newWeather, thundering, raining) {
        this.emitToPython('weather_change', {
            old_weather: oldWeather,
            new_weather: newWeather,
            thundering: thundering,
            raining: raining,
            time: Date.now()
        }, { priority: 20 });
    }
    
    /**
     * Emit time change event
     * @param {number} timeOfDay - Time of day (0-24000)
     * @param {number} age - World age
     */
    emitTimeChangeEvent(timeOfDay, age) {
        const isDay = timeOfDay > 1000 && timeOfDay < 13000;
        const isNight = timeOfDay > 14000 || timeOfDay < 1000;
        
        this.emitToPython('time_change', {
            time_of_day: timeOfDay,
            age: age,
            is_day: isDay,
            is_night: isNight,
            time: Date.now()
        }, { priority: 5 });
    }
    
    /**
     * Emit chunk load event
     * @param {number} chunkX - Chunk X coordinate
     * @param {number} chunkZ - Chunk Z coordinate
     */
    emitChunkLoadEvent(chunkX, chunkZ) {
        this.emitToPython('chunk_load', {
            chunk_x: chunkX,
            chunk_z: chunkZ,
            dimension: this.bot.game?.dimension || 'overworld',
            time: Date.now()
        }, { priority: 15 });
    }
    
    /**
     * Emit chunk unload event
     * @param {number} chunkX - Chunk X coordinate
     * @param {number} chunkZ - Chunk Z coordinate
     */
    emitChunkUnloadEvent(chunkX, chunkZ) {
        this.emitToPython('chunk_unload', {
            chunk_x: chunkX,
            chunk_z: chunkZ,
            dimension: this.bot.game?.dimension || 'overworld',
            time: Date.now()
        }, { priority: 15 });
    }
    
    /**
     * Emit entity spawn event
     * @param {object} entity - The entity object
     */
    emitEntitySpawnEvent(entity) {
        this.emitToPython('entity_spawn', {
            entity_id: entity.id,
            entity_type: entity.type,
            position: this.sanitizePosition(entity.position),
            time: Date.now()
        }, { priority: 20 });
    }
    
    /**
     * Emit entity death event
     * @param {object} entity - The entity object
     */
    emitEntityDeathEvent(entity) {
        this.emitToPython('entity_death', {
            entity_id: entity.id,
            entity_type: entity.type,
            position: this.sanitizePosition(entity.position),
            time: Date.now()
        }, { priority: 25 });
    }
    
    /**
     * Emit inventory change event
     * @param {number} slot - The inventory slot
     * @param {object} item - The item object (or null)
     */
    emitInventoryChangeEvent(slot, item) {
        this.emitToPython('inventory_change', {
            slot,
            item_name: item?.name || null,
            count: item?.count || 0,
            time: Date.now()
        }, { priority: 40 });
    }
    
    /**
     * Emit container open event
     * @param {object} window - The window/container object
     */
    emitContainerOpenEvent(window) {
        this.emitToPython('container_open', {
            container_type: window.type || 'unknown',
            container_position: window.position ? this.sanitizePosition(window.position) : null,
            container_size: window.slots ? window.slots.length : 0,
            time: Date.now()
        }, { priority: 50 });
    }
    
    /**
     * Emit container close event
     * @param {object} window - The window/container object
     */
    emitContainerCloseEvent(window) {
        this.emitToPython('container_close', {
            container_type: window.type || 'unknown',
            container_position: window.position ? this.sanitizePosition(window.position) : null,
            time: Date.now()
        }, { priority: 45 });
    }
    
    /**
     * Emit item drop event
     * @param {object} item - The dropped item entity
     */
    emitItemDropEvent(item) {
        this.emitToPython('item_drop', {
            item_name: item.name || item.itemType || 'unknown',
            count: item.itemCount || item.count || 1,
            position: this.sanitizePosition(item.position),
            entity_id: item.id,
            time: Date.now()
        }, { priority: 35 });
    }
    
    /**
     * Emit item pickup event
     * @param {object} item - The picked up item entity
     */
    emitItemPickupEvent(item) {
        this.emitToPython('item_pickup', {
            item_name: item.name || item.itemType || 'unknown',
            count: item.itemCount || item.count || 1,
            position: this.sanitizePosition(item.position),
            entity_id: item.id,
            time: Date.now()
        }, { priority: 35 });
    }
    
    /**
     * Emit item craft event
     * @param {string} recipe - Recipe name
     * @param {object} result - Crafted item
     * @param {array} ingredients - Used ingredients
     */
    emitItemCraftEvent(recipe, result, ingredients) {
        this.emitToPython('item_craft', {
            recipe_name: recipe,
            result_item: result.name,
            result_count: result.count || 1,
            ingredients: ingredients || [],
            time: Date.now()
        }, { priority: 60 });
    }
    
    /**
     * Emit item consume event
     * @param {object} item - Consumed item
     * @param {number} foodPoints - Food points gained
     * @param {number} saturation - Saturation gained
     */
    emitItemConsumeEvent(item, foodPoints, saturation) {
        this.emitToPython('item_consume', {
            item_name: item.name,
            food_points: foodPoints,
            saturation: saturation,
            time: Date.now()
        }, { priority: 55 });
    }
    
    /**
     * Emit movement progress event
     * @param {object} progressData - Movement progress data
     */
    emitMovementProgressEvent(progressData) {
        this.emitToPython('movement_progress', {
            target: progressData.target,
            current_position: progressData.current_position,
            distance_remaining: progressData.distance_remaining,
            path_status: progressData.path_status,
            remaining_moves: progressData.remaining_moves,
            elapsed_time: progressData.elapsed_time,
            time: Date.now()
        }, { priority: 20 });
    }
}

module.exports = { MinecraftEventEmitter };