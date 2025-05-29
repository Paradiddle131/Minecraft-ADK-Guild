"""
Main entry point for the Minecraft Multi-Agent System
Orchestrates CoordinatorAgent with GathererAgent and CrafterAgent sub-agents
"""

import asyncio
import argparse
import sys
from typing import Optional

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from src.config import get_config, setup_google_ai_credentials
from src.bridge.bridge_manager import BridgeManager
from src.tools.agent_tools import create_gatherer_tools, create_crafter_tools
from src.agents import CoordinatorAgent, GathererAgent, CrafterAgent
from src.logging_config import setup_logging, get_logger

# Module-level logger (will be properly configured in main())
logger = get_logger(__name__)


async def setup_agents(bridge_manager: BridgeManager, config=None):
    """Setup the multi-agent system with coordinator and sub-agents
    
    Args:
        bridge_manager: Initialized BridgeManager for Minecraft interaction
        config: Optional configuration object
        
    Returns:
        Tuple of (coordinator, runner, session_service)
    """
    config = config or get_config()
    
    # Setup Google AI credentials
    try:
        ai_credentials = setup_google_ai_credentials(config)
        logger.info("Google AI credentials configured successfully")
    except ValueError as e:
        logger.error(f"Failed to setup Google AI credentials: {e}")
        sys.exit(1)
    
    # Create session service
    session_service = InMemorySessionService()
    
    # Create sub-agents with bridge integration first (they will create mc_data_service)
    gatherer = GathererAgent(
        name="GathererAgent",
        model=config.default_model,
        tools=[],  # Tools will be set after agent creation
        session_service=session_service,
        bridge_manager=bridge_manager,
        ai_credentials=ai_credentials,
        config=config
    )
    
    crafter = CrafterAgent(
        name="CrafterAgent", 
        model=config.default_model,
        tools=[],  # Tools will be set after agent creation
        session_service=session_service,
        bridge_manager=bridge_manager,
        ai_credentials=ai_credentials,
        config=config
    )
    
    # Now create enhanced tools with minecraft data service
    gatherer_tools = create_gatherer_tools(bridge_manager, gatherer.mc_data)
    crafter_tools = create_crafter_tools(bridge_manager, crafter.mc_data)
    
    # Update agents with tools
    gatherer.tools = gatherer_tools
    crafter.tools = crafter_tools
    
    # Create coordinator with sub-agents
    coordinator = CoordinatorAgent(
        name="CoordinatorAgent",
        model=config.default_model,
        sub_agents=[gatherer.create_agent(), crafter.create_agent()],
        session_service=session_service,
        bridge_manager=bridge_manager,
        ai_credentials=ai_credentials,
        config=config
    )
    
    # Create runner for the coordinator
    runner = Runner(
        agent=coordinator.create_agent(),
        app_name="minecraft_multiagent",
        session_service=session_service
    )
    
    logger.info("Multi-agent system setup complete")
    return coordinator, runner, session_service


async def run_agent_system(command: str, runner: Runner, session_service: InMemorySessionService):
    """Execute a command through the agent system
    
    Args:
        command: User command to process
        runner: ADK Runner instance
        session_service: Session service for state management
        
    Returns:
        Agent response string
    """
    # Create or get session
    session = await session_service.create_session(
        app_name="minecraft_multiagent",
        user_id="player"
    )
    
    # Store user request in state for agents to access
    session.state["user_request"] = command
    
    # Create user message
    user_content = types.Content(
        role='user',
        parts=[types.Part(text=command)]
    )
    
    # Execute through runner
    final_response = ""
    logger.info(f"Processing command: {command}")
    
    async for event in runner.run_async(
        user_id="player",
        session_id=session.id,
        new_message=user_content
    ):
        if event.is_final_response() and event.content:
            final_response = ''.join(
                part.text or '' for part in event.content.parts
            )
    
    # Log task results from state
    gather_result = session.state.get("task.gather.result")
    craft_result = session.state.get("task.craft.result")
    
    if gather_result:
        logger.info(f"Gather result: {gather_result}")
    if craft_result:
        logger.info(f"Craft result: {craft_result}")
        
    return final_response


def parse_args():
    """Parse command line arguments
    
    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="Minecraft Multi-Agent System - Coordinate agents for complex tasks"
    )
    parser.add_argument(
        "command",
        nargs="?",
        help="Command to execute (e.g., 'gather 3 oak logs', 'craft wooden pickaxe')"
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Run in interactive mode"
    )
    return parser.parse_args()


async def main():
    """Main entry point for the multi-agent system"""
    args = parse_args()
    
    # Load configuration
    config = get_config()
    
    # Setup logging with config
    setup_logging(
        log_level=config.log_level,
        log_file=config.log_file,
        console_output=True,
        json_format=config.log_json_format,
        google_log_level=config.google_log_level
    )
    
    logger.info("Starting Minecraft Multi-Agent System")
    
    # Initialize bridge manager
    bridge = BridgeManager(agent_config=config)
    
    try:
        logger.info("Initializing connection to Minecraft...")
        await bridge.initialize()
        
        # Setup agents
        coordinator, runner, session_service = await setup_agents(bridge, config)
        
        if args.interactive:
            # Interactive mode
            logger.info("Starting interactive mode. Type 'exit' to quit.")
            
            while True:
                try:
                    command = input("\nMinecraft Agent> ").strip()
                    
                    if command.lower() in ['exit', 'quit', 'q']:
                        break
                        
                    if not command:
                        continue
                        
                    response = await run_agent_system(command, runner, session_service)
                    logger.info(f"Agent response: {response}")
                    
                except KeyboardInterrupt:
                    logger.info("Exiting interactive mode...")
                    break
                except Exception as e:
                    logger.error(f"Error processing command: {e}")
                    
        elif args.command:
            # Single command mode
            response = await run_agent_system(args.command, runner, session_service)
            logger.info(f"Agent response: {response}")
        else:
            # No command provided
            logger.info("Please provide a command or use --interactive mode")
            logger.info("Examples:")
            logger.info("  python main.py 'check inventory'")
            logger.info("  python main.py 'gather 3 oak logs'")
            logger.info("  python main.py 'craft wooden pickaxe'")
            logger.info("  python main.py --interactive")
            
    except Exception as e:
        logger.error(f"Failed to initialize: {e}")
        logger.error("Make sure:")
        logger.error("1. Minecraft server is running")
        logger.error("2. Environment variables are set (see .env.example)")
        logger.error("3. Google AI API key is configured")
        sys.exit(1)
    finally:
        # Cleanup
        if bridge.is_connected:
            logger.info("Shutting down bridge connection...")
            # Bridge cleanup handled by garbage collection


if __name__ == "__main__":
    asyncio.run(main())