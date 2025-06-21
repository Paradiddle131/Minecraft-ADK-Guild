"""
JSPyBridge Manager - Handles Python to JavaScript communication with Mineflayer
"""
import asyncio
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional

if TYPE_CHECKING:
    from ..config import AgentConfig

from ..logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class BridgeConfig:
    """Configuration for JSPyBridge"""

    command_timeout: int = 5000  # milliseconds
    batch_size: int = 10
    max_retries: int = 3
    event_queue_size: int = 1000


@dataclass(order=True)
class Command:
    """Represents a command to be sent to JavaScript"""

    # Required fields without defaults (must come first)
    id: str = field(compare=False)
    method: str = field(compare=False)
    args: Dict[str, Any] = field(compare=False)

    # Optional fields with defaults (used for ordering in PriorityQueue)
    priority: int = field(default=0, compare=True)  # Higher priority executed first
    timestamp: datetime = field(default_factory=datetime.now, compare=True)
    callback: Optional[Callable] = field(default=None, compare=False)


class BridgeManager:
    """Manages communication between Python ADK agents and JavaScript Mineflayer bot"""

    def __init__(
        self, config: BridgeConfig = None, agent_config: Optional["AgentConfig"] = None, auto_start: bool = True
    ):
        self.config = config or BridgeConfig()
        self.agent_config = agent_config
        self.auto_start = auto_start
        self.bot = None
        self.event_handlers = {}
        self.command_queue = asyncio.PriorityQueue(maxsize=self.config.event_queue_size)
        self.pending_commands = {}
        self.is_connected = False
        self.is_spawned = False
        self._event_loop = None
        self._command_processor_task = None

    async def initialize(self, bot_script_path: str = None):
        """Initialize the bridge and start the Mineflayer bot"""
        if not self.auto_start:
            logger.info("Auto-start disabled - bridge initialized without bot connection")
            self.is_connected = False
            self.is_spawned = False
            return

        try:
            import os

            from javascript import require

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

            # Get minecraft configuration from environment or defaults
            # Use agent_config if provided, otherwise fall back to environment variables
            if self.agent_config:
                minecraft_host = self.agent_config.minecraft_host
                minecraft_port = self.agent_config.minecraft_port
                bot_username = self.agent_config.bot_username
                minecraft_version = self.agent_config.minecraft_version
            else:
                minecraft_host = os.getenv("MINECRAFT_AGENT_MINECRAFT_HOST", "localhost")
                minecraft_port = int(os.getenv("MINECRAFT_AGENT_MINECRAFT_PORT", "25565"))
                bot_username = os.getenv("MINECRAFT_AGENT_BOT_USERNAME", "MinecraftAgent")
                minecraft_version = os.getenv("MINECRAFT_AGENT_MINECRAFT_VERSION", "1.21.1")

            logger.info(
                f"Starting bot with configuration: host={minecraft_host}, port={minecraft_port}, username={bot_username}, version={minecraft_version}"
            )

            bot_result = self.bot_module.startBot(
                {
                    "host": minecraft_host,
                    "port": minecraft_port,
                    "username": bot_username,
                    "auth": "offline",
                    "version": minecraft_version,
                    "timeout": 60000,
                },
                timeout=90000,
            )

            wait_count = 0
            while wait_count < 300:
                if hasattr(bot_result, "bot") and bot_result.bot is not None:
                    break
                await asyncio.sleep(0.1)
                wait_count += 1

            if not hasattr(bot_result, "bot") or bot_result.bot is None:
                logger.error("Bot initialization failed - no bot object returned")
                raise TimeoutError(
                    f"Bot failed to initialize - check if Minecraft server is running on {minecraft_host}:{minecraft_port}"
                )

            # bot_result.bot is a MinecraftBot instance with executeCommand method
            self.bot = bot_result.bot

            logger.info("Waiting for bot to spawn in world...")
            self.is_spawned = await self._wait_for_spawn_with_timeout()

            if self.is_spawned:
                logger.info("Bot spawned successfully and ready to use")
            else:
                logger.warning("Bot created but not spawned - server might not be running")

            logger.info(f"Bot ready: bot={self.bot is not None}, spawned={self.is_spawned}")

            await self._setup_event_listeners()

            self._event_loop = asyncio.get_event_loop()
            self._command_processor_task = asyncio.create_task(self._process_command_queue())

            self.is_connected = True
            logger.info("JSPyBridge initialized successfully")
            logger.info("Bot initialized and spawned")

        except Exception as e:
            logger.error("Failed to initialize bridge", error=str(e))
            raise

    async def _wait_for_spawn_with_timeout(self, timeout: float = None) -> bool:
        """Wait for bot to spawn in the world with timeout

        Returns:
            bool: True if spawned, False if timeout
        """
        # Use environment variable or default
        if timeout is None:
            timeout = float(os.getenv("MINECRAFT_AGENT_SPAWN_TIMEOUT_SECONDS", "30.0"))

        # Check if bot is already spawned
        start_time = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start_time < timeout:
            try:
                # Check if bot has entity (means it's spawned)
                if hasattr(self.bot, "bot") and hasattr(self.bot.bot, "entity") and self.bot.bot.entity is not None:
                    logger.info("Bot spawned successfully - entity exists")
                    return True

                # Also check health as an indicator of spawn
                if hasattr(self.bot, "bot") and hasattr(self.bot.bot, "health") and self.bot.bot.health is not None:
                    logger.info(f"Bot spawned successfully - health: {self.bot.bot.health}")
                    return True

            except Exception as e:
                logger.debug(f"Error checking spawn status: {e}")

            await asyncio.sleep(0.5)

        logger.warning(f"Bot spawn timeout after {timeout}s - server may not be running")
        return False

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
            if hasattr(self.bot, "bot"):
                self.bot.bot.on(event, lambda *args, evt=event: self._handle_event(evt, args))

    def _handle_event(self, event_type: str, args):
        """Handle events from the Minecraft bot"""
        # Only log event type, not the full args to avoid massive objects
        logger.debug(f"Received event: {event_type}")

        event_data = {
            "type": event_type,
            "timestamp": datetime.now().isoformat(),
            "data": self._serialize_args(args),
        }

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

        if not self.is_spawned:
            raise RuntimeError("Bot is not connected to Minecraft server")

        command_id = f"cmd_{datetime.now().timestamp()}"
        future = asyncio.Future()

        command = Command(
            id=command_id,
            method=method,
            args=kwargs,
            callback=lambda result: future.set_result(result),
        )

        await self.command_queue.put((-command.priority, command))

        try:
            # Store command for potential cleanup
            self.pending_commands[command_id] = command

            result = await asyncio.wait_for(future, timeout=self.config.command_timeout / 1000)
            return result
        except asyncio.TimeoutError:
            logger.error("Command timeout", method=method, args=kwargs)
            raise TimeoutError(f"Command {method} timed out")
        finally:
            # Clean up pending command
            self.pending_commands.pop(command_id, None)

    async def _process_command_queue(self):
        """Process commands from the queue"""
        batch = []

        while True:
            try:
                while len(batch) < self.config.batch_size:
                    try:
                        _, command = await asyncio.wait_for(self.command_queue.get(), timeout=0.1)
                        batch.append(command)
                    except asyncio.TimeoutError:
                        break

                if batch:
                    await self._execute_batch(batch)
                    batch = []

                await asyncio.sleep(0.01)

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

    async def _execute_single_command(self, command: Command) -> Any:
        """Execute a single command - retry handled at higher level for specific commands"""
        logger.debug("Executing command", method=command.method, args=command.args)

        # Route to the MinecraftBot's command handlers via direct property access
        # Note: Can't use await on JSPyBridge Proxy objects directly

        # For entity.position and other info commands, access the mineflayer bot directly
        if command.method == "entity.position":
            if hasattr(self.bot, "bot") and hasattr(self.bot.bot, "entity") and self.bot.bot.entity:
                return self.bot.bot.entity.position
            else:
                raise RuntimeError("Bot entity not available - bot may not be spawned")

        elif command.method == "entity.health":
            if hasattr(self.bot, "bot"):
                return {
                    "health": getattr(self.bot.bot, "health", None),
                    "food": getattr(self.bot.bot, "food", None),
                    "saturation": getattr(self.bot.bot, "foodSaturation", None),
                }
            else:
                raise RuntimeError("Bot not available")

        elif command.method == "inventory.items":
            if hasattr(self.bot, "bot") and hasattr(self.bot.bot, "inventory"):
                items = self.bot.bot.inventory.items()
                return [{"name": item.name, "count": item.count, "slot": item.slot} for item in items]
            else:
                raise RuntimeError("Bot inventory not available")

        else:
            # For all other commands, use the bot's executeCommand method
            # which routes to the JavaScript handlers
            if hasattr(self.bot, "executeCommand"):
                # Special handling for long-running commands like pathfinder.goto
                if command.method == "pathfinder.goto":
                    # Don't retry pathfinder commands - they handle their own timeout
                    logger.info(f"Executing pathfinder.goto to {command.args}")

                # Calculate appropriate timeout for JSPyBridge call
                # For pathfinder.goto, use the pathfinder timeout + 5 seconds buffer
                if self.agent_config:
                    default_js_timeout = self.agent_config.js_command_timeout_ms
                else:
                    default_js_timeout = int(os.getenv("MINECRAFT_AGENT_JS_COMMAND_TIMEOUT_MS", "15000"))
                js_timeout = default_js_timeout  # Default for most commands
                if command.method == "pathfinder.goto" and "timeout" in command.args:
                    # Add 5 second buffer to pathfinder timeout
                    js_timeout = command.args["timeout"] + 5000
                elif command.method == "pathfinder.goto":
                    # Default pathfinder timeout from config or env var, add 5s buffer
                    if self.agent_config:
                        default_pathfinder_timeout = self.agent_config.pathfinder_timeout_ms
                    else:
                        default_pathfinder_timeout = int(os.getenv("MINECRAFT_AGENT_PATHFINDER_TIMEOUT_MS", "30000"))
                    js_timeout = default_pathfinder_timeout + 5000

                js_result = self.bot.executeCommand(
                    {
                        "method": command.method,
                        "args": command.args,
                        "id": command.id if hasattr(command, "id") else "cmd",
                    },
                    timeout=js_timeout,
                )

                # Handle JavaScript proxy object
                if js_result is None:
                    raise RuntimeError(f"No result returned from command: {command.method}")

                # Log the raw result for debugging
                logger.debug(
                    f"JS result type: {type(js_result)}, hasattr success: {hasattr(js_result, 'success') if js_result else 'N/A'}"
                )

                if hasattr(js_result, "success"):
                    # Access proxy properties directly
                    success = js_result.success
                    if success:
                        # Return the actual result data
                        result = js_result.result
                        logger.debug(f"Command {command.method} succeeded with result type: {type(result)}")
                        return result
                    else:
                        error_msg = js_result.error if hasattr(js_result, "error") else "Command failed"
                        raise RuntimeError(error_msg)
                else:
                    # Fallback for unexpected result format
                    logger.warning(f"Unexpected result format from {command.method}: {type(js_result)}")
                    return js_result
            else:
                raise RuntimeError(f"Unknown command: {command.method}")

    async def close(self):
        """Close the bridge and cleanup resources"""
        logger.info("Closing bridge")

        if self._command_processor_task:
            self._command_processor_task.cancel()

        if self.bot:
            if hasattr(self.bot, "quit"):
                self.bot.quit()
            elif hasattr(self.bot, "bot") and hasattr(self.bot.bot, "quit"):
                self.bot.bot.quit()

        self.is_connected = False
        logger.info("Bridge closed")

    # Convenience methods for common operations
    async def move_to(self, x: int, y: int, z: int, timeout: int = None) -> Dict[str, Any]:
        """Move bot to specific coordinates with timeout protection"""
        # Use config or environment variable for default
        if timeout is None:
            if self.agent_config:
                timeout = self.agent_config.pathfinder_timeout_ms
            else:
                timeout = int(os.getenv("MINECRAFT_AGENT_PATHFINDER_TIMEOUT_MS", "30000"))

        # Increase command timeout to match pathfinder timeout + buffer
        original_timeout = self.config.command_timeout
        self.config.command_timeout = timeout + 5000  # Add 5s buffer

        try:
            result = await self.execute_command("pathfinder.goto", x=x, y=y, z=z, timeout=timeout)
            return result
        finally:
            # Restore original timeout
            self.config.command_timeout = original_timeout

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
