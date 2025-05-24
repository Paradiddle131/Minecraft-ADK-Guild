/**
 * WebSocket Event Client - Sends Minecraft events to Python
 */
import WebSocket from 'ws';
import winston from 'winston';

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

export class EventClient {
    constructor(port = 8765) {
        this.port = port;
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
        this.reconnectDelay = 1000;
        this.isConnected = false;
        this.eventQueue = [];
        this.maxQueueSize = 1000;
    }

    async connect() {
        try {
            logger.info(`Connecting to event stream server on port ${this.port}`);

            this.ws = new WebSocket(`ws://localhost:${this.port}`);

            return new Promise((resolve, reject) => {
                this.ws.on('open', () => {
                    logger.info('Connected to event stream server');
                    this.isConnected = true;
                    this.reconnectAttempts = 0;

                    // Send queued events
                    this.flushEventQueue();

                    // Start heartbeat
                    this.startHeartbeat();

                    resolve();
                });

                this.ws.on('error', (error) => {
                    logger.error('WebSocket error:', error);
                    reject(error);
                });

                this.ws.on('close', () => {
                    logger.warn('Disconnected from event stream server');
                    this.isConnected = false;
                    this.handleReconnect();
                });

                this.ws.on('message', (data) => {
                    this.handleMessage(data);
                });
            });
        } catch (error) {
            logger.error('Failed to connect:', error);
            throw error;
        }
    }

    handleMessage(data) {
        try {
            const message = JSON.parse(data);

            switch (message.type) {
                case 'command':
                    this.handleCommand(message.data);
                    break;
                case 'heartbeat_ack':
                    // Heartbeat acknowledged
                    break;
                default:
                    logger.warn(`Unknown message type: ${message.type}`);
            }
        } catch (error) {
            logger.error('Error handling message:', error);
        }
    }

    handleCommand(command) {
        // Commands from Python will be handled here
        // This will be integrated with the bot's command execution
        logger.debug('Received command from Python:', command);
    }

    sendEvent(eventType, data, metadata = {}) {
        const event = {
            type: 'event',
            eventType,
            timestamp: new Date().toISOString(),
            data,
            metadata
        };

        if (this.isConnected) {
            try {
                this.ws.send(JSON.stringify(event));
            } catch (error) {
                logger.error('Failed to send event:', error);
                this.queueEvent(event);
            }
        } else {
            this.queueEvent(event);
        }
    }

    queueEvent(event) {
        if (this.eventQueue.length < this.maxQueueSize) {
            this.eventQueue.push(event);
        } else {
            logger.warn('Event queue full, dropping oldest event');
            this.eventQueue.shift();
            this.eventQueue.push(event);
        }
    }

    flushEventQueue() {
        logger.info(`Flushing ${this.eventQueue.length} queued events`);

        while (this.eventQueue.length > 0 && this.isConnected) {
            const event = this.eventQueue.shift();
            try {
                this.ws.send(JSON.stringify(event));
            } catch (error) {
                logger.error('Failed to send queued event:', error);
                this.eventQueue.unshift(event);
                break;
            }
        }
    }

    sendCommandResult(id, success, result = null, error = null) {
        const message = {
            type: 'command_result',
            id,
            success,
            result,
            error
        };

        if (this.isConnected) {
            this.ws.send(JSON.stringify(message));
        }
    }

    startHeartbeat() {
        setInterval(() => {
            if (this.isConnected) {
                try {
                    this.ws.send(JSON.stringify({ type: 'heartbeat' }));
                } catch (error) {
                    logger.error('Heartbeat failed:', error);
                }
            }
        }, 30000); // 30 second heartbeat
    }

    async handleReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            logger.error('Max reconnection attempts reached');
            return;
        }

        this.reconnectAttempts++;
        const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);

        logger.info(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);

        setTimeout(async () => {
            try {
                await this.connect();
            } catch (error) {
                logger.error('Reconnection failed:', error);
            }
        }, delay);
    }

    close() {
        if (this.ws) {
            this.ws.close();
        }
    }
}

// Integration with MinecraftBot
export function integrateEventClient(bot, eventClient) {
    // Forward all bot events to Python
    bot.on('minecraft_event', (event) => {
        eventClient.sendEvent(event.type, event.data);
    });

    // Handle commands from Python
    eventClient.handleCommand = async (command) => {
        try {
            const result = await bot.executeCommand(command);
            eventClient.sendCommandResult(command.id, true, result);
        } catch (error) {
            eventClient.sendCommandResult(command.id, false, null, error.message);
        }
    };
}
