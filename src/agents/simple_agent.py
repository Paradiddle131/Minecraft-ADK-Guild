"""
Simple Minecraft Agent - POC for single agent with Mineflayer tools
"""
import asyncio
from typing import Optional

import structlog
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from ..config import AgentConfig, get_config, setup_google_ai_credentials

from ..bridge.bridge_manager import BridgeConfig, BridgeManager
from ..bridge.event_stream import EventProcessor, EventStream
from ..tools.mineflayer_tools import create_mineflayer_tools

logger = structlog.get_logger(__name__)


class SimpleMinecraftAgent:
    """A simple Minecraft agent that can perform basic tasks"""

    def __init__(self, name: str = "MinecraftAgent", model: str = None, config: AgentConfig = None):
        self.config = config or get_config()
        self.name = name
        self.model = model or self.config.default_model
        self.bridge = None
        self.event_stream = None
        self.event_processor = None
        self.agent = None
        self.runner = None
        self.session = None
        self.session_manager = InMemorySessionService()
        
        # Setup Google AI credentials
        try:
            self.ai_credentials = setup_google_ai_credentials(self.config)
            logger.info("Google AI credentials configured successfully")
        except ValueError as e:
            logger.warning(f"Google AI credentials not configured: {e}")
            self.ai_credentials = None

    async def initialize(self):
        """Initialize the agent and all components"""
        logger.info(f"Initializing {self.name}")

        # Initialize bridge with config
        bridge_config = BridgeConfig(
            command_timeout=self.config.command_timeout_ms,
            batch_size=5,
            event_queue_size=self.config.event_queue_size
        )
        self.bridge = BridgeManager(bridge_config)
        await self.bridge.initialize()

        # Use the event stream from bridge (already started)
        self.event_stream = self.bridge.event_stream

        # Set up event processing
        self.event_processor = EventProcessor()
        self.event_stream.register_handler("position", self.event_processor.process_position_event)
        self.event_stream.register_handler(
            "playerJoined", self.event_processor.process_player_event
        )
        self.event_stream.register_handler("playerLeft", self.event_processor.process_player_event)
        self.event_stream.register_handler("blockUpdate", self.event_processor.process_block_update)

        # Create ADK agent with tools
        tools = create_mineflayer_tools(self.bridge)

        # Prepare agent configuration
        agent_kwargs = {
            "name": self.name,
            "model": self.model,
            "instruction": self._get_agent_instruction(),
            "description": "A Minecraft bot that can move, dig, build, and interact with the world",
            "tools": tools,
            "output_key": "agent_response",
            "generate_content_config": types.GenerateContentConfig(
                temperature=self.config.agent_temperature,
                max_output_tokens=self.config.max_output_tokens
            )
        }
        
        # Add credentials if available
        if self.ai_credentials:
            agent_kwargs.update(self.ai_credentials)
        
        self.agent = LlmAgent(**agent_kwargs)

        # Create runner for agent execution
        self.runner = Runner(
            agent=self.agent,
            app_name="minecraft_agent",
            session_service=self.session_manager
        )

        # Create session
        self.session = await self.session_manager.create_session(
            app_name="minecraft_agent", 
            user_id="minecraft_player"
        )
        logger.info(f"Agent {self.name} initialized with session {self.session.id}")

    def _get_agent_instruction(self) -> str:
        """Get the instruction prompt for the agent with state injection"""
        return """You are a helpful Minecraft bot at position {current_position?}.

Your current inventory contains: {current_inventory?}
The requesting player is: {requesting_player?}
Nearby players: {nearby_players?}

Available tools:
- execute(x, y, z): Move to coordinates using pathfinding
- dig_block(x, y, z): Mine blocks at specified coordinates
- place_block(x, y, z, block_type, face): Build with specified block type
- find_blocks(block_name, max_distance, count): Locate blocks within range
- get_nearby_players(): Get information about nearby players
- get_inventory(): Check current inventory contents
- craft_item(recipe, count): Craft items using available materials
- send_chat(message): Communicate with players

Guidelines:
1. Always acknowledge player requests in chat before starting a task
2. Break down complex tasks into logical steps
3. Check your inventory before attempting to place blocks
4. Use find_blocks to locate resources before trying to mine them
5. Report completion or any issues back to the player
6. Be efficient in your tool usage and pathfinding

Be helpful, efficient, and safe in your actions. Always respond with your planned actions and then execute them."""

    async def process_command(self, command: str, player: Optional[str] = None) -> str:
        """Process a command from a player or system using real ADK

        Args:
            command: The command or request
            player: Name of requesting player (optional)

        Returns:
            Agent's response
        """
        try:
            logger.info(f"Processing command: {command} from player: {player}")
            
            # Update session state with context
            if player:
                self.session.state["requesting_player"] = player
            
            # Add world state from event processor
            world_state = self.event_processor.get_world_state()
            self.session.state.update(world_state)
            
            # Add current bot position and inventory to state
            try:
                current_pos = await self.bridge.get_position()
                if not isinstance(current_pos, dict) or 'error' not in current_pos:
                    self.session.state["current_position"] = current_pos
            except Exception:
                self.session.state["current_position"] = "unknown (server not connected)"
            
            try:
                current_inventory = await self.bridge.get_inventory()
                if not isinstance(current_inventory, dict) or 'error' not in current_inventory:
                    # Create inventory summary
                    inventory_summary = {}
                    for item in current_inventory:
                        name = item["name"]
                        inventory_summary[name] = inventory_summary.get(name, 0) + item["count"]
                    self.session.state["current_inventory"] = inventory_summary
            except Exception:
                self.session.state["current_inventory"] = "unknown (server not connected)"
            
            # Create user message content
            user_content = types.Content(
                role='user',
                parts=[types.Part(text=command)]
            )
            
            # Execute agent with real ADK
            logger.info("Executing command with Google ADK")
            final_response = ""
            
            async for event in self.runner.run_async(
                user_id="minecraft_player",
                session_id=self.session.id,
                new_message=user_content
            ):
                if event.is_final_response() and event.content:
                    final_response = ''.join(
                        part.text or '' for part in event.content.parts
                    )
                    logger.info(f"Agent response: {final_response}")
            
            return final_response or "I couldn't process that command."
            
        except Exception as e:
            logger.error(f"Error processing command: {e}")
            # Fallback for testing without proper ADK setup
            if "inventory" in command.lower():
                try:
                    inventory_result = await self.bridge.get_inventory()
                    if isinstance(inventory_result, dict) and 'error' in inventory_result:
                        return "I cannot access my inventory because I'm not connected to a Minecraft server. Please start a Minecraft server on localhost:25565 to enable inventory commands."
                    return f"My current inventory contains: {inventory_result}"
                except Exception:
                    return "I cannot access my inventory because I'm not connected to a Minecraft server. Please start a Minecraft server on localhost:25565 to enable inventory commands."
            elif "position" in command.lower():
                try:
                    pos = await self.bridge.get_position()
                    if isinstance(pos, dict) and 'error' in pos:
                        return "I cannot get my position because I'm not connected to a Minecraft server. Please start a Minecraft server on localhost:25565 to enable position commands."
                    return f"I am currently at position: x={pos['x']}, y={pos['y']}, z={pos['z']}"
                except Exception:
                    return "I cannot get my position because I'm not connected to a Minecraft server. Please start a Minecraft server on localhost:25565 to enable position commands."
            else:
                return f"Sorry, I encountered an error processing '{command}': {str(e)}. ADK integration may need configuration."

    async def demonstrate_capabilities(self):
        """Run a demonstration of agent capabilities"""
        logger.info("Starting capability demonstration")

        demos = [
            "Check my current inventory",
            "Find the nearest oak logs within 32 blocks",
            "Move to coordinates 100, 65, 100",
            "Say hello to everyone in chat",
        ]

        for demo in demos:
            logger.info(f"Demo: {demo}")
            response = await self.process_command(demo)
            logger.info(f"Response: {response}")
            await asyncio.sleep(2)  # Pause between demos

    async def run_interactive(self):
        """Run in interactive mode, processing commands from console"""
        logger.info("Starting interactive mode")

        print("\nMinecraft Agent Interactive Mode")
        print("Type commands for the agent, or 'quit' to exit\n")

        while True:
            try:
                command = input("> ")
                if command.lower() in ["quit", "exit"]:
                    break

                response = await self.process_command(command)
                print(f"\nAgent: {response}\n")

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error: {e}")

        logger.info("Exiting interactive mode")

    async def cleanup(self):
        """Clean up resources"""
        logger.info("Cleaning up agent resources")

        if self.bridge:
            await self.bridge.close()

        logger.info("Cleanup complete")


async def main():
    """Main entry point for testing the agent"""
    # Configure logging
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Create and initialize agent
    agent = SimpleMinecraftAgent()

    try:
        await agent.initialize()

        # Run demonstration
        await agent.demonstrate_capabilities()

        # Run interactive mode
        await agent.run_interactive()

    finally:
        await agent.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
