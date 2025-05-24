"""
Simple Minecraft Agent - POC for single agent with Mineflayer tools
"""
import asyncio
from typing import Optional

import structlog
from google.adk.agents import LlmAgent
from google.adk.sessions import InMemorySessionManager

from ..bridge.bridge_manager import BridgeConfig, BridgeManager
from ..bridge.event_stream import EventProcessor, EventStream
from ..tools.mineflayer_tools import create_mineflayer_tools

logger = structlog.get_logger(__name__)


class SimpleMinecraftAgent:
    """A simple Minecraft agent that can perform basic tasks"""

    def __init__(self, name: str = "MinecraftAgent", model: str = "gemini-2.0-flash"):
        self.name = name
        self.model = model
        self.bridge = None
        self.event_stream = None
        self.event_processor = None
        self.agent = None
        self.session = None
        self.session_manager = InMemorySessionManager()

    async def initialize(self):
        """Initialize the agent and all components"""
        logger.info(f"Initializing {self.name}")

        # Initialize bridge
        config = BridgeConfig(
            command_timeout=10000, batch_size=5  # 10 seconds for Minecraft operations
        )
        self.bridge = BridgeManager(config)
        await self.bridge.initialize()

        # Initialize event stream
        self.event_stream = EventStream()
        await self.event_stream.start()

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

        self.agent = LlmAgent(
            name=self.name,
            model=self.model,
            instruction=self._get_agent_instruction(),
            description="A Minecraft bot that can move, dig, build, and interact with the world",
            tools=tools,
            output_key="agent_response",
        )

        # Create session
        self.session = await self.session_manager.create_session()
        logger.info(f"Agent {self.name} initialized with session {self.session.id}")

    def _get_agent_instruction(self) -> str:
        """Get the instruction prompt for the agent"""
        return """You are a helpful Minecraft bot that can perform various tasks in the game world.

Your capabilities include:
- Movement: Use move_to(x, y, z) to navigate to specific coordinates
- Block interaction: Use dig_block(x, y, z) to mine blocks and place_block(x, y, z, block_type) to build
- World queries: Use find_blocks(block_name) to locate resources
- Inventory: Use get_inventory() to check what items you have
- Communication: Use send_chat(message) to talk to players

Guidelines:
1. Always acknowledge player requests in chat before starting a task
2. Break down complex tasks into steps
3. Check your inventory before attempting to place blocks
4. Use find_blocks to locate resources before trying to mine them
5. Report completion or any issues back to the player

Be helpful, efficient, and safe in your actions."""

    async def process_command(self, command: str, player: Optional[str] = None) -> str:
        """Process a command from a player or system

        Args:
            command: The command or request
            player: Name of requesting player (optional)

        Returns:
            Agent's response
        """
        try:
            # Add context to session state
            if player:
                self.session.state["requesting_player"] = player

            # Add world state from event processor
            self.session.state.update(self.event_processor.get_world_state())

            # Run agent
            response = await self.agent.run(session=self.session, prompt=command)

            # Extract response
            if response and response.messages:
                return response.messages[-1].content
            else:
                return "I processed your request but have no specific response."

        except Exception as e:
            logger.error(f"Error processing command: {e}")
            return f"Sorry, I encountered an error: {str(e)}"

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

        if self.event_stream:
            await self.event_stream.stop()

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
