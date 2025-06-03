"""
Main entry point for the Minecraft Multi-Agent System
Orchestrates CoordinatorAgent with GathererAgent and CrafterAgent using AgentTool pattern
"""

import argparse
import asyncio
import sys

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from src.agents.coordinator_agent.agent import create_coordinator_agent
from src.bridge.bridge_manager import BridgeManager
from src.config import get_config, setup_google_ai_credentials
from src.logging_config import get_logger, setup_logging

logger = get_logger(__name__)

# Global command queue for interactive mode
command_queue = asyncio.Queue()


async def setup_system(bridge_manager: BridgeManager, config=None):
    """Setup the multi-agent system with coordinator agent

    Args:
        bridge_manager: Initialized BridgeManager for Minecraft interaction
        config: Optional configuration object

    Returns:
        Tuple of (runner, session_service)
    """
    config = config or get_config()

    # Setup Google AI credentials
    try:
        setup_google_ai_credentials(config)
        logger.info("Google AI credentials configured successfully")
    except ValueError as e:
        logger.error(f"Failed to setup Google AI credentials: {e}")
        sys.exit(1)

    # Create session service
    session_service = InMemorySessionService()

    # Create runner
    runner = Runner(app_name="minecraft_multiagent", session_service=session_service)

    # Create coordinator agent with AgentTool pattern
    coordinator = create_coordinator_agent(runner)

    # Set the agent on the runner
    runner.agent = coordinator

    logger.info("Multi-agent system setup complete")
    return runner, session_service


async def initialize_session(session_service: InMemorySessionService):
    """Initialize the persistent session

    Args:
        session_service: Session service for state management

    Returns:
        Session object
    """
    session = await session_service.create_session(
        app_name="minecraft_multiagent", user_id="player", session_id="interactive_session"
    )
    logger.info("Created new session for interactive mode")

    # Initialize the session state
    await session.set({"minecraft": {"connected": True}})

    return session


async def process_command(command: str, runner: Runner, session):
    """Process a single command ensuring coordinator handles it

    Args:
        command: User command to process
        runner: ADK Runner instance
        session: Current session object

    Returns:
        Agent response string
    """
    logger.info(f"Processing command: {command}")

    # Always ensure coordinator is the active agent
    # This is automatic with AgentTool pattern

    # Create user message
    user_content = types.Content(role="user", parts=[types.Part(text=command)])

    # Execute through runner
    final_response = ""

    try:
        async for event in runner.run_async(user_id="player", session_id=session.id, new_message=user_content):
            if event.is_final_response() and event.content:
                final_response = "".join(part.text or "" for part in event.content.parts)

        logger.info(f"Command processed successfully: {command}")
        return final_response
    except Exception as e:
        logger.error(f"Error processing command '{command}': {e}", exc_info=True)
        return f"Error processing command: {str(e)}"


async def command_processor(runner: Runner, session):
    """Background task to process commands from the queue"""
    logger.info("Starting command processor task")

    while True:
        try:
            # Wait for command from queue
            command = await command_queue.get()
            logger.debug(f"Got command from queue: {command}")

            # Process the command
            response = await process_command(command, runner, session)

            # Print response
            if response:
                print(f"\n{response}\n")

            # Mark task as done
            command_queue.task_done()

            # Log queue status
            queue_size = command_queue.qsize()
            if queue_size > 0:
                logger.info(f"Commands remaining in queue: {queue_size}")

        except asyncio.CancelledError:
            logger.info("Command processor cancelled")
            break
        except Exception as e:
            logger.error(f"Error in command processor: {e}", exc_info=True)


def parse_args():
    """Parse command line arguments

    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(description="Minecraft Multi-Agent System - Coordinate agents for complex tasks")
    parser.add_argument(
        "command", nargs="?", help="Command to execute (e.g., 'gather 3 oak logs', 'craft wooden pickaxe')"
    )
    parser.add_argument("--interactive", "-i", action="store_true", help="Run in interactive mode")
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
        google_log_level=config.google_log_level,
    )

    logger.info("Starting Minecraft Multi-Agent System")

    # Initialize bridge manager
    bridge = BridgeManager(agent_config=config)

    try:
        logger.info("Initializing connection to Minecraft...")
        await bridge.initialize()

        # Setup system with new architecture
        runner, session_service = await setup_system(bridge, config)

        # Initialize session
        session = await initialize_session(session_service)

        if args.interactive:
            # Interactive mode with command queue
            logger.info("Starting interactive mode. Type 'exit' to quit.")

            # Start command processor task
            logger.info("Creating command processor task...")
            processor_task = asyncio.create_task(command_processor(runner, session))
            logger.info(f"Command processor task created: {processor_task}")

            try:
                # Create a queue for user input
                import threading

                input_queue = asyncio.Queue()

                # Get the running event loop
                loop = asyncio.get_running_loop()

                def read_input():
                    """Read input in a separate thread"""
                    while True:
                        try:
                            line = input("\nMinecraft Agent> ").strip()
                            asyncio.run_coroutine_threadsafe(input_queue.put(line), loop)
                        except EOFError:
                            break

                # Start input thread
                input_thread = threading.Thread(target=read_input, daemon=True)
                input_thread.start()

                while True:
                    try:
                        # Get user input with timeout to allow other tasks to run
                        try:
                            command = await asyncio.wait_for(input_queue.get(), timeout=0.1)
                        except asyncio.TimeoutError:
                            continue

                        if command.lower() in ["exit", "quit", "q"]:
                            break

                        if not command:
                            continue

                        if command.lower() == "status":
                            # Show queue status
                            queue_size = command_queue.qsize()
                            print("\nQueue Status:")
                            print(f"  Commands in queue: {queue_size}")
                            continue

                        # Add command to queue
                        await command_queue.put(command)
                        logger.info(f"Added command to queue: {command}")
                        print("Command queued for processing.")

                    except KeyboardInterrupt:
                        logger.info("Exiting interactive mode...")
                        break
                    except Exception as e:
                        logger.error(f"Error handling input: {e}")

            finally:
                # Cancel processor task
                processor_task.cancel()
                try:
                    await processor_task
                except asyncio.CancelledError:
                    pass

        elif args.command:
            # Single command mode
            response = await process_command(args.command, runner, session)
            if response:
                print(response)
        else:
            # No command provided
            logger.info("Please provide a command or use --interactive mode")
            print("Examples:")
            print("  python main.py 'check inventory'")
            print("  python main.py 'gather 3 oak logs'")
            print("  python main.py 'craft wooden pickaxe'")
            print("  python main.py --interactive")

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
