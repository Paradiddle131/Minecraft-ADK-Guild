"""
Event Stream Handler - Manages JavaScript to Python event flow
"""
import asyncio
import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import structlog
import websockets

logger = structlog.get_logger(__name__)


@dataclass
class MinecraftEvent:
    """Represents an event from Minecraft"""

    type: str
    timestamp: str
    data: List[Any]
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class EventStream:
    """Handles streaming of events from JavaScript to Python"""

    def __init__(self, port: int = 8765):
        self.port = port
        self.handlers: Dict[str, List[Callable]] = defaultdict(list)
        self.event_history: List[MinecraftEvent] = []
        self.max_history_size = 1000
        self.websocket_server = None
        self.connected_clients = set()
        self._running = False

    async def start(self):
        """Start the WebSocket server for event streaming"""
        logger.info(f"Starting event stream server on port {self.port}")

        self._running = True
        self.websocket_server = await websockets.serve(self._handle_client, "localhost", self.port)

        logger.info("Event stream server started")

    async def _handle_client(self, websocket, path):
        """Handle a WebSocket client connection"""
        client_id = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        logger.info(f"Client connected: {client_id}")

        self.connected_clients.add(websocket)

        try:
            async for message in websocket:
                await self._process_message(message, websocket)
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Client disconnected: {client_id}")
        finally:
            self.connected_clients.remove(websocket)

    async def _process_message(self, message: str, websocket):
        """Process incoming message from JavaScript"""
        try:
            data = json.loads(message)

            # Handle different message types
            if data.get("type") == "event":
                await self._handle_event(data)
            elif data.get("type") == "command_result":
                await self._handle_command_result(data)
            elif data.get("type") == "heartbeat":
                await websocket.send(json.dumps({"type": "heartbeat_ack"}))
            else:
                logger.warning(f"Unknown message type: {data.get('type')}")

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON received: {e}")
        except Exception as e:
            logger.error(f"Error processing message: {e}")

    async def _handle_event(self, data: Dict[str, Any]):
        """Handle a Minecraft event"""
        event = MinecraftEvent(
            type=data["eventType"],
            timestamp=data["timestamp"],
            data=data["data"],
            metadata=data.get("metadata", {}),
        )

        # Add to history
        self.event_history.append(event)
        if len(self.event_history) > self.max_history_size:
            self.event_history.pop(0)

        # Call registered handlers
        await self._dispatch_event(event)

        # Log event
        logger.debug(f"Received event: {event.type}", data=event.data)

    async def _dispatch_event(self, event: MinecraftEvent):
        """Dispatch event to registered handlers"""
        # Global handlers (handle all events)
        for handler in self.handlers.get("*", []):
            await self._call_handler(handler, event)

        # Specific event handlers
        for handler in self.handlers.get(event.type, []):
            await self._call_handler(handler, event)

    async def _call_handler(self, handler: Callable, event: MinecraftEvent):
        """Call an event handler safely"""
        try:
            if asyncio.iscoroutinefunction(handler):
                await handler(event)
            else:
                handler(event)
        except Exception as e:
            logger.error(f"Error in event handler for {event.type}: {e}")

    async def _handle_command_result(self, data: Dict[str, Any]):
        """Handle command execution result from JavaScript"""
        # This will be used to complete pending command futures
        # Implementation depends on integration with BridgeManager
        logger.debug(f"Command result received: {data}")

    def register_handler(self, event_type: str, handler: Callable):
        """Register an event handler

        Args:
            event_type: Type of event to handle (use "*" for all events)
            handler: Function to call when event occurs
        """
        self.handlers[event_type].append(handler)
        logger.info(f"Registered handler for event type: {event_type}")

    def unregister_handler(self, event_type: str, handler: Callable):
        """Unregister an event handler"""
        if event_type in self.handlers and handler in self.handlers[event_type]:
            self.handlers[event_type].remove(handler)
            logger.info(f"Unregistered handler for event type: {event_type}")

    async def broadcast_command(self, command: Dict[str, Any]):
        """Broadcast a command to all connected JavaScript clients"""
        message = json.dumps({"type": "command", "data": command})

        if self.connected_clients:
            await asyncio.gather(
                *[client.send(message) for client in self.connected_clients], return_exceptions=True
            )

    def get_recent_events(
        self, event_type: Optional[str] = None, limit: int = 10
    ) -> List[MinecraftEvent]:
        """Get recent events from history"""
        if event_type:
            filtered = [e for e in self.event_history if e.type == event_type]
            return filtered[-limit:]
        return self.event_history[-limit:]

    async def stop(self):
        """Stop the event stream server"""
        logger.info("Stopping event stream server")
        self._running = False

        if self.websocket_server:
            self.websocket_server.close()
            await self.websocket_server.wait_closed()

        logger.info("Event stream server stopped")


class EventProcessor:
    """Processes Minecraft events and updates world state"""

    def __init__(self):
        self.world_state = {}
        self.player_positions = {}
        self.inventory_cache = {}

    async def process_position_event(self, event: MinecraftEvent):
        """Process position update event"""
        if event.data and len(event.data) > 0:
            pos_data = event.data[0]
            self.world_state["bot_position"] = {
                "x": pos_data.get("x"),
                "y": pos_data.get("y"),
                "z": pos_data.get("z"),
                "yaw": pos_data.get("yaw"),
                "pitch": pos_data.get("pitch"),
                "timestamp": event.timestamp,
            }

    async def process_player_event(self, event: MinecraftEvent):
        """Process player join/leave events"""
        if event.type == "playerJoined" and event.data:
            player = event.data[0]
            self.player_positions[player.get("username")] = player
            logger.info(f"Player joined: {player.get('username')}")

        elif event.type == "playerLeft" and event.data:
            player = event.data[0]
            username = player.get("username")
            if username in self.player_positions:
                del self.player_positions[username]
            logger.info(f"Player left: {username}")

    async def process_block_update(self, event: MinecraftEvent):
        """Process block update events"""
        if event.data and len(event.data) >= 2:
            old_block = event.data[0]
            new_block = event.data[1]

            # Update world model
            pos_key = f"{new_block.get('x')}_{new_block.get('y')}_{new_block.get('z')}"
            self.world_state[f"block_{pos_key}"] = {
                "type": new_block.get("name"),
                "old_type": old_block.get("name"),
                "timestamp": event.timestamp,
            }

    def get_world_state(self) -> Dict[str, Any]:
        """Get current world state"""
        return {
            "bot_position": self.world_state.get("bot_position"),
            "players": list(self.player_positions.values()),
            "last_update": datetime.now().isoformat(),
        }
