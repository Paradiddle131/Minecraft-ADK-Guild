"""Minecraft Coordinator Agent - ADK deployment module.

This module creates and exports the root_agent for ADK deployment commands.
When used with 'adk web', the bot will not automatically connect to Minecraft.
"""
import logging
import os
import sys

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.coordinator_agent.agent import create_coordinator_agent
from src.bridge.bridge_manager import BridgeManager
from src.config import get_config, setup_google_ai_credentials
from src.logging_config import setup_logging
from src.minecraft_bot_controller import BotController
from src.minecraft_data_service import MinecraftDataService

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

try:
    # Initialize configuration
    config = get_config()
    setup_google_ai_credentials(config)
    logger.info("Google AI credentials configured for ADK deployment")

    # Initialize services without auto-starting bot connection
    # This allows testing in web UI without requiring a Minecraft server
    bridge = BridgeManager(agent_config=config, auto_start=False)
    bot_controller = BotController(bridge)

    # Initialize data service with version from config
    minecraft_version = getattr(config, "minecraft_version", "1.21.1")
    mc_data_service = MinecraftDataService(minecraft_version)

    # Create and export root_agent for ADK
    root_agent = create_coordinator_agent(runner=None, bot_controller=bot_controller, mc_data_service=mc_data_service)

    logger.info("Coordinator agent created successfully for ADK deployment")

except Exception as e:
    error_msg = str(e)
    logger.error(f"Failed to create coordinator agent: {error_msg}")
    # Create a minimal agent that explains the error
    from google.adk.agents import Agent

    def explain_error(user_input: str) -> dict:
        """Explain configuration error to user."""
        return {
            "status": "error",
            "message": f"Agent initialization failed: {error_msg}. Please check your .env configuration and ensure all required environment variables are set.",
        }

    root_agent = Agent(
        name="ErrorAgent",
        model="gemini-2.0-flash",
        instruction=f"The Minecraft Coordinator Agent failed to initialize due to: {error_msg}. Please inform the user about this error and suggest checking the .env configuration.",
        tools=[explain_error],
    )
