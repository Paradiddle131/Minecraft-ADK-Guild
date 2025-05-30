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
from src.minecraft_data_service import MinecraftDataService
from src.minecraft_bot_controller import BotController

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
    
    # Create shared services
    minecraft_version = getattr(config, 'minecraft_version', '1.21.1')
    mc_data_service = MinecraftDataService(minecraft_version)
    bot_controller = BotController(bridge_manager)
    
    # Create sub-agents
    gatherer = GathererAgent(
        name="GathererAgent",
        model=config.default_model,
        tools=[],  # Tools will be set after agent creation
        session_service=session_service,
        bridge_manager=bridge_manager,
        ai_credentials=ai_credentials,
        config=config,
        mc_data_service=mc_data_service,
        bot_controller=bot_controller
    )
    
    crafter = CrafterAgent(
        name="CrafterAgent", 
        model=config.default_model,
        tools=[],  # Tools will be set after agent creation
        session_service=session_service,
        bridge_manager=bridge_manager,
        ai_credentials=ai_credentials,
        config=config,
        mc_data_service=mc_data_service,
        bot_controller=bot_controller
    )
    
    # Now create enhanced tools with bot controller and minecraft data service
    gatherer_tools = create_gatherer_tools(gatherer.bot_controller, gatherer.mc_data)
    crafter_tools = create_crafter_tools(crafter.bot_controller, crafter.mc_data)
    
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
        config=config,
        mc_data_service=mc_data_service,
        bot_controller=bot_controller
    )
    
    # Create runner for the coordinator
    runner = Runner(
        agent=coordinator.create_agent(),
        app_name="minecraft_multiagent",
        session_service=session_service
    )
    
    logger.info("Multi-agent system setup complete")
    return coordinator, runner, session_service


async def initialize_session(session_service: InMemorySessionService):
    """Initialize or get the persistent session
    
    Args:
        session_service: Session service for state management
        
    Returns:
        Session object
    """
    # Try to get existing session first
    try:
        session = await session_service.get_session(
            app_name="minecraft_multiagent",
            user_id="player", 
            session_id="interactive_session"
        )
        logger.info("Retrieved existing session")
    except:
        # Create new session if it doesn't exist
        session = await session_service.create_session(
            app_name="minecraft_multiagent",
            user_id="player",
            session_id="interactive_session"
        )
        # Initialize command queue
        session.state["task.command_queue"] = []
        session.state["task.processing"] = False
        logger.info("Created new session with command queue")
        
    return session


async def add_command_to_queue(command: str, session_service: InMemorySessionService, session):
    """Add a command to the processing queue
    
    Args:
        command: User command to add to queue
        session_service: Session service for state management
        session: Current session object
    """
    # Get current queue
    command_queue = session.state.get("task.command_queue", [])
    command_queue.append(command)
    
    # Update state with new queue
    from google.adk.events import Event, EventActions
    
    state_changes = {
        "task.command_queue": command_queue
    }
    
    event = Event(
        author="system",
        actions=EventActions(state_delta=state_changes)
    )
    
    await session_service.append_event(session, event)
    logger.info(f"Added command to queue: {command}. Queue size: {len(command_queue)}")


async def process_next_command(runner: Runner, session_service: InMemorySessionService, session):
    """Process the next command from the queue
    
    Args:
        runner: ADK Runner instance
        session_service: Session service for state management
        session: Current session object
        
    Returns:
        Agent response string or None if queue is empty
    """
    # Check if already processing
    if session.state.get("task.processing", False):
        logger.info("Already processing a command")
        return None
        
    # Get command queue
    command_queue = session.state.get("task.command_queue", [])
    if not command_queue:
        return None
        
    # Get next command
    command = command_queue.pop(0)
    
    # Update state to mark as processing
    from google.adk.events import Event, EventActions
    
    state_changes = {
        "task.command_queue": command_queue,
        "task.processing": True,
        "task.current_command": command,
        "user_request": command  # For backward compatibility
    }
    
    event = Event(
        author="system",
        actions=EventActions(state_delta=state_changes)
    )
    
    await session_service.append_event(session, event)
    logger.info(f"Processing command: {command}")
    
    # Create user message
    user_content = types.Content(
        role='user',
        parts=[types.Part(text=command)]
    )
    
    # Execute through runner
    final_response = ""
    
    async for event in runner.run_async(
        user_id="player",
        session_id=session.id,
        new_message=user_content
    ):
        if event.is_final_response() and event.content:
            final_response = ''.join(
                part.text or '' for part in event.content.parts
            )
    
    # Mark processing as complete
    state_changes = {
        "task.processing": False,
        "task.current_command": None
    }
    
    complete_event = Event(
        author="system",
        actions=EventActions(state_delta=state_changes)
    )
    
    await session_service.append_event(session, complete_event)
    
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
        _, runner, session_service = await setup_agents(bridge, config)
        
        # Initialize persistent session
        session = await initialize_session(session_service)
        
        if args.interactive:
            # Interactive mode with persistent session
            logger.info("Starting interactive mode with persistent session. Type 'exit' to quit.")
            logger.info("Commands are queued and processed sequentially.")
            
            # Start background task to process command queue
            import asyncio
            
            async def process_queue_loop():
                """Background task to process commands from queue"""
                while True:
                    try:
                        # Get fresh session state
                        session_fresh = await session_service.get_session(
                            app_name="minecraft_multiagent",
                            user_id="player",
                            session_id="interactive_session"
                        )
                        
                        # Process next command if any
                        response = await process_next_command(runner, session_service, session_fresh)
                        if response:
                            logger.info(f"Agent response: {response}")
                            print(f"\n{response}\n")
                            
                        # Check remaining queue size
                        queue_size = len(session_fresh.state.get("task.command_queue", []))
                        if queue_size > 0:
                            logger.info(f"Remaining commands in queue: {queue_size}")
                            
                    except Exception as e:
                        logger.error(f"Error in queue processor: {e}")
                        
                    # Small delay between queue checks
                    await asyncio.sleep(0.5)
            
            # Start queue processor
            queue_task = asyncio.create_task(process_queue_loop())
            
            try:
                while True:
                    try:
                        # Get user input
                        command = input("\nMinecraft Agent> ").strip()
                        
                        if command.lower() in ['exit', 'quit', 'q']:
                            break
                            
                        if not command:
                            continue
                            
                        if command.lower() == 'status':
                            # Show queue status
                            session_fresh = await session_service.get_session(
                                app_name="minecraft_multiagent",
                                user_id="player",
                                session_id="interactive_session"
                            )
                            queue = session_fresh.state.get("task.command_queue", [])
                            processing = session_fresh.state.get("task.processing", False)
                            current = session_fresh.state.get("task.current_command")
                            
                            print(f"\nQueue Status:")
                            print(f"  Processing: {processing}")
                            print(f"  Current command: {current}")
                            print(f"  Queued commands: {len(queue)}")
                            for i, cmd in enumerate(queue):
                                print(f"    {i+1}. {cmd}")
                            continue
                            
                        # Add command to queue
                        await add_command_to_queue(command, session_service, session)
                        print(f"Command added to queue: {command}")
                        
                    except KeyboardInterrupt:
                        logger.info("Exiting interactive mode...")
                        break
                    except Exception as e:
                        logger.error(f"Error handling input: {e}")
            finally:
                # Cancel queue processor
                queue_task.cancel()
                try:
                    await queue_task
                except asyncio.CancelledError:
                    pass
                    
        elif args.command:
            # Single command mode with persistent session
            await add_command_to_queue(args.command, session_service, session)
            response = await process_next_command(runner, session_service, session)
            if response:
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