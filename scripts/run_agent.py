#!/usr/bin/env python3
"""
Run script for Minecraft agents with proper environment setup
"""
import argparse
import asyncio
import logging
import sys
from pathlib import Path

import structlog
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.simple_agent import SimpleMinecraftAgent
from src.bridge.bridge_manager import BridgeConfig, BridgeManager
from src.utils.state_manager import StateManager


def setup_logging(log_level: str = "INFO", log_format: str = "pretty"):
    """Configure structured logging"""

    # Configure structlog
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if log_format == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper()),
    )


async def run_simple_agent(args):
    """Run the simple agent demo"""
    logger = structlog.get_logger()

    # Initialize state manager if persistence is enabled
    state_manager = None
    if args.enable_persistence:
        state_manager = StateManager()
        await state_manager.initialize()
        logger.info("State persistence enabled")

    # Create and run agent
    agent = SimpleMinecraftAgent(name=args.agent_name, model=args.model)

    try:
        await agent.initialize()

        if args.demo:
            await agent.demonstrate_capabilities()

        if args.interactive:
            await agent.run_interactive()

        if args.cmd:
            response = await agent.process_command(args.cmd)
            print(f"\nAgent response: {response}\n")

    finally:
        await agent.cleanup()
        if state_manager:
            await state_manager.close()


async def test_connection(args):
    """Test connection to Minecraft server"""

    logger = structlog.get_logger()
    logger.info("Testing connection to Minecraft server...")

    config = BridgeConfig()
    bridge = BridgeManager(config)

    try:
        await bridge.initialize()
        logger.info("Successfully connected to Minecraft server!")

        # Get bot position
        pos = await bridge.get_position()
        logger.info(f"Bot spawned at position: {pos}")

        # Send a test message
        await bridge.chat("Hello from the multi-agent system!")

        await asyncio.sleep(2)

    except Exception as e:
        logger.error(f"Connection test failed: {e}")
    finally:
        await bridge.close()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Minecraft Multi-Agent System")

    # Common arguments
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level",
    )
    parser.add_argument(
        "--log-format", default="pretty", choices=["pretty", "json"], help="Log output format"
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Agent command
    agent_parser = subparsers.add_parser("agent", help="Run a Minecraft agent")
    agent_parser.add_argument("--agent-name", default="MinecraftBot", help="Name of the agent")
    agent_parser.add_argument("--model", default="gemini-2.0-flash", help="LLM model to use")
    agent_parser.add_argument("--demo", action="store_true", help="Run capability demonstration")
    agent_parser.add_argument("--interactive", action="store_true", help="Run in interactive mode")
    agent_parser.add_argument("--cmd", type=str, help="Single command to execute")
    agent_parser.add_argument(
        "--enable-persistence", action="store_true", help="Enable state persistence"
    )

    # Test command
    subparsers.add_parser("test", help="Test connection to server")

    args = parser.parse_args()

    # Load environment variables
    load_dotenv()

    # Setup logging
    setup_logging(args.log_level, args.log_format)

    # Run appropriate command
    if args.command == "agent":
        asyncio.run(run_simple_agent(args))
    elif args.command == "test":
        asyncio.run(test_connection(args))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
