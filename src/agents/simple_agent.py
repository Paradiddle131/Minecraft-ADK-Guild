"""
Simple Minecraft Agent - POC for single agent with Mineflayer tools
"""
import asyncio
import os
from typing import Optional

import structlog
from google.adk import Runner
from google.adk.agents import LlmAgent
from google.adk.sessions import InMemorySessionService
from google.adk.runners import RunConfig
from google.genai import types

from ..bridge.bridge_manager import BridgeConfig, BridgeManager
from ..bridge.event_stream import EventProcessor, EventStream
from ..tools.mineflayer_tools import create_mineflayer_tools
from ..config import config

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
        self.session_manager = InMemorySessionService()
        self.runner = None

    async def initialize(self):
        """Initialize the agent and all components"""
        logger.info(f"Initializing {self.name}")
        
        # Check for API key
        if not config.validate_api_key():
            # Set API key from environment if available
            api_key = config.api_key
            if api_key:
                os.environ["GOOGLE_API_KEY"] = api_key
            else:
                logger.warning("No Google API key found. Please set GOOGLE_API_KEY or ADK_API_KEY environment variable.")

        # Initialize bridge
        bridge_config = BridgeConfig(
            command_timeout=config.jspy_command_timeout, 
            batch_size=config.jspy_batch_size
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

        self.agent = LlmAgent(
            name=self.name,
            model=self.model,
            instruction=self._get_agent_instruction(),
            description="A Minecraft bot that can move, dig, build, and interact with the world",
            tools=tools,
            output_key="agent_response",
        )

        # Create session
        self.session = await self.session_manager.create_session(
            app_name="minecraft_agent", 
            user_id="minecraft_player"
        )
        
        # Create runner for agent execution
        self.runner = Runner(
            app_name="minecraft_agent",
            agent=self.agent,
            session_service=self.session_manager
        )
        self.run_config = RunConfig(max_llm_calls=50)
        
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

            # Create user message content
            content = types.Content(
                parts=[types.Part(text=command)],
                role="user"
            )
            
            logger.info(f"Processing command with ADK: {command}")
            
            # Run the agent
            events = []
            response_text = ""
            
            async for event in self.runner.run_async(
                session_id=self.session.id,
                user_id="minecraft_player",
                new_message=content,
                run_config=self.run_config
            ):
                events.append(event)
                
                # Extract text responses from the agent
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.text:
                            response_text += part.text
                            
                # Log tool calls for debugging
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.function_call:
                            logger.info(f"Tool called: {part.function_call.name}", 
                                      args=part.function_call.args)
            
            # Return the collected response
            if response_text:
                return response_text.strip()
            else:
                return "I processed your command but didn't generate a text response. Please check the logs for tool execution details."

        except Exception as e:
            logger.error(f"Error processing command: {e}", exc_info=True)
            # Check if it's a connection issue
            if "not connected" in str(e).lower() or "connection" in str(e).lower():
                return "I cannot perform this action because I'm not connected to a Minecraft server. Please start a Minecraft server on localhost:25565 to enable Minecraft commands."
            return f"Sorry, I encountered an error while processing your command: {str(e)}"

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
