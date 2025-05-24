"""
JSPyBridge Manager - Handles Python to JavaScript communication with Mineflayer
"""
import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, Optional

import structlog
from javascript import require
from tenacity import retry, stop_after_attempt, wait_exponential

logger = structlog.get_logger(__name__)


@dataclass
class BridgeConfig:
    """Configuration for JSPyBridge"""

    command_timeout: int = 5000  # milliseconds
    batch_size: int = 10
    max_retries: int = 3
    event_queue_size: int = 1000


@dataclass
class Command:
    """Represents a command to be sent to JavaScript"""

    id: str
    method: str
    args: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    callback: Optional[Callable] = None
    priority: int = 0  # Higher priority executed first


class BridgeManager:
    """Manages communication between Python ADK agents and JavaScript Mineflayer bot"""

    def __init__(self, config: BridgeConfig = None):
        self.config = config or BridgeConfig()
        self.bot = None
        self.event_handlers = {}
        self.command_queue = asyncio.PriorityQueue(maxsize=self.config.event_queue_size)
        self.pending_commands = {}
        self.is_connected = False
        self._event_loop = None
        self._command_processor_task = None

    async def initialize(self, bot_script_path: str = None):
        """Initialize the bridge and start the Mineflayer bot"""
        try:
            import os
            from javascript import require, On, Once, AsyncTask, once, off
            
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            original_cwd = os.getcwd()
            os.chdir(project_root)
            
            try:
                logger.info("Initializing JSPyBridge", cwd=os.getcwd(), project_root=project_root)
                
                index_js_path = os.path.join(project_root, "src", "minecraft", "index.js")
                if not os.path.exists(index_js_path):
                    raise FileNotFoundError(f"Bot script not found at {index_js_path}")
                
                logger.info("Bot script exists", path=index_js_path)
                
                self.bot_module = require(index_js_path)
            finally:
                os.chdir(original_cwd)

            await self._start_event_server()
            await asyncio.sleep(0.5)

            logger.info("Starting bot and waiting for readiness...")
            
            bot_result = self.bot_module.startBot(timeout=60000)
            
            logger.info("Waiting for bot initialization...")
            await asyncio.wait_for(self._wait_for_bot_ready(bot_result), timeout=30)
            
            self.bot = bot_result.bot
            self.event_client = bot_result.eventClient
            
            if self.bot and hasattr(self.bot, '_client') and self.bot._client:
                logger.info("Waiting for bot to spawn in world...")
                await asyncio.wait_for(self._wait_for_bot_spawn(), timeout=30)
            else:
                logger.info("Bot ready but no server connection (server may not be running)")
            
            logger.info(f"Bot ready: bot={self.bot is not None}, eventClient={self.event_client is not None}")

            await self._setup_event_listeners()

            self._event_loop = asyncio.get_event_loop()
            self._command_processor_task = asyncio.create_task(self._process_command_queue())

            self.is_connected = True
            logger.info("JSPyBridge initialized successfully")
            logger.info("Bot initialized and spawned")

        except Exception as e:
            logger.error("Failed to initialize bridge", error=str(e))
            raise

    async def _start_event_server(self):
        """Start the WebSocket event server for JavaScript clients"""
        from ..bridge.event_stream import EventStream
        
        self.event_stream = EventStream(port=8765)
        await self.event_stream.start()
        logger.info("Event stream server started on port 8765")

    async def _wait_for_bot_ready(self, bot_result):
        """Wait for bot initialization to complete"""
        while True:
            try:
                if hasattr(bot_result, 'bot') and bot_result.bot is not None:
                    break
            except:
                pass
            await asyncio.sleep(0.1)

    async def _wait_for_bot_spawn(self):
        """Wait for bot to spawn in the world"""
        spawn_event = asyncio.Event()

        def on_spawn():
            spawn_event.set()

        from javascript import On
        spawn_listener = On(self.bot, "spawn")(on_spawn)

        try:
            await spawn_event.wait()
            logger.info("Bot spawned successfully")
        finally:
            if hasattr(spawn_listener, 'destroy'):
                spawn_listener.destroy()

    async def _setup_event_listeners(self):
        """Set up event listeners for bot events"""
        events = [
            "chat",
            "playerJoined",
            "playerLeft",
            "health",
            "death",
            "kicked",
            "error",
            "blockUpdate",
            "entitySpawn",
            "entityGone",
        ]

        for event in events:
            self.bot.on(event, lambda *args, evt=event: self._handle_event(evt, args))

    def _handle_event(self, event_type: str, args):
        """Handle events from the Minecraft bot"""
        logger.debug(f"Received event: {event_type}", args=args)

        # Convert args to serializable format
        event_data = {
            "type": event_type,
            "timestamp": datetime.now().isoformat(),
            "data": self._serialize_args(args),
        }

        # Call registered handlers
        if event_type in self.event_handlers:
            for handler in self.event_handlers[event_type]:
                try:
                    handler(event_data)
                except Exception as e:
                    logger.error("Error in event handler", event=event_type, error=str(e))

    def _serialize_args(self, args):
        """Convert JavaScript objects to Python-serializable format"""
        serialized = []
        for arg in args:
            try:
                # Try to convert to dict if it's an object
                if hasattr(arg, "__dict__"):
                    serialized.append(arg.__dict__)
                else:
                    serialized.append(str(arg))
            except Exception:
                serialized.append(str(arg))
        return serialized

    def register_event_handler(self, event_type: str, handler: Callable):
        """Register a handler for specific bot events"""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)
        logger.debug(f"Registered handler for event: {event_type}")

    async def execute_command(self, method: str, **kwargs) -> Any:
        """Execute a command on the bot"""
        if not self.is_connected:
            raise RuntimeError("Bridge is not connected")

        command_id = f"cmd_{datetime.now().timestamp()}"
        future = asyncio.Future()

        command = Command(
            id=command_id,
            method=method,
            args=kwargs,
            callback=lambda result: future.set_result(result),
        )

        await self.command_queue.put((command.priority, command))

        try:
            result = await asyncio.wait_for(future, timeout=self.config.command_timeout / 1000)
            return result
        except asyncio.TimeoutError:
            logger.error("Command timeout", method=method, args=kwargs)
            raise TimeoutError(f"Command {method} timed out")

    async def _process_command_queue(self):
        """Process commands from the queue"""
        batch = []

        while True:
            try:
                # Collect commands for batching
                while len(batch) < self.config.batch_size:
                    try:
                        _, command = await asyncio.wait_for(self.command_queue.get(), timeout=0.1)
                        batch.append(command)
                    except asyncio.TimeoutError:
                        break

                # Execute batch if we have commands
                if batch:
                    await self._execute_batch(batch)
                    batch = []

                await asyncio.sleep(0.01)  # Small delay to prevent CPU spinning

            except Exception as e:
                logger.error("Error in command processor", error=str(e))
                await asyncio.sleep(1)

    async def _execute_batch(self, commands: list[Command]):
        """Execute a batch of commands"""
        for command in commands:
            try:
                result = await self._execute_single_command(command)
                if command.callback:
                    command.callback(result)
            except Exception as e:
                logger.error("Command execution failed", command=command.method, error=str(e))
                if command.callback:
                    command.callback({"error": str(e)})

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=5))
    async def _execute_single_command(self, command: Command) -> Any:
        """Execute a single command with retry logic"""
        logger.debug("Executing command", method=command.method, args=command.args)

        # Get the method from bot
        method_parts = command.method.split(".")
        obj = self.bot

        for part in method_parts:
            obj = getattr(obj, part)

        # Call the method
        if asyncio.iscoroutinefunction(obj):
            result = await obj(**command.args)
        else:
            result = obj(**command.args)

        return result

    async def close(self):
        """Close the bridge and cleanup resources"""
        logger.info("Closing bridge")

        if self._command_processor_task:
            self._command_processor_task.cancel()

        if self.bot:
            self.bot.quit()

        if hasattr(self, 'event_stream') and self.event_stream:
            await self.event_stream.stop()

        self.is_connected = False
        logger.info("Bridge closed")

    # Convenience methods for common operations
    async def move_to(self, x: int, y: int, z: int) -> Dict[str, Any]:
        """Move bot to specific coordinates"""
        return await self.execute_command("pathfinder.goto", x=x, y=y, z=z)

    async def dig_block(self, x: int, y: int, z: int) -> Dict[str, Any]:
        """Dig a block at specific coordinates"""
        return await self.execute_command("dig", x=x, y=y, z=z)

    async def place_block(self, x: int, y: int, z: int, face: str = "top") -> Dict[str, Any]:
        """Place a block at specific coordinates"""
        return await self.execute_command("placeBlock", x=x, y=y, z=z, face=face)

    async def chat(self, message: str) -> None:
        """Send a chat message"""
        return await self.execute_command("chat", message=message)

    async def get_inventory(self) -> Dict[str, Any]:
        """Get current inventory"""
        return await self.execute_command("inventory.items")

    async def get_position(self) -> Dict[str, float]:
        """Get current bot position"""
        pos = await self.execute_command("entity.position")
        return {"x": pos.x, "y": pos.y, "z": pos.z}
