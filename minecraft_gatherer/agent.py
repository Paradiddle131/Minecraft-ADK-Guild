"""Minecraft Gatherer Agent - ADK deployment module.

This module creates and exports the gatherer agent for standalone testing.
When used with 'adk web', the bot will not automatically connect to Minecraft.
"""
import logging
import os
import sys

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import structlog
from google.adk.agents import LlmAgent

from minecraft_coordinator.callbacks import get_configured_callbacks
from src.bridge.bridge_manager import BridgeManager
from src.config import get_config, setup_google_ai_credentials
from src.logging_config import setup_logging
from src.minecraft_bot_controller import BotController
from src.minecraft_data_service import MinecraftDataService
from src.tools.mineflayer_tools import create_mineflayer_tools

from .prompt import GATHERER_PROMPT

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)


def create_gatherer_agent(bot_controller=None, mc_data_service=None, config=None) -> LlmAgent:
    """Create the gatherer agent with structured output.

    Args:
        bot_controller: BotController instance
        mc_data_service: MinecraftDataService instance
        config: Agent configuration instance

    Returns:
        Configured gatherer agent that returns results via output_key
    """
    # Get config if not provided
    if config is None:
        config = get_config()
    # Get configured callbacks
    callbacks = get_configured_callbacks()

    # Register callbacks individually as per ADK API
    gatherer = LlmAgent(
        name="GathererAgent",
        model=config.default_model,
        instruction=GATHERER_PROMPT,
        output_key="gathering_result",  # Structured output to state
        tools=create_mineflayer_tools(bot_controller, mc_data_service),
        **callbacks,  # Unpack callback dict to pass as individual parameters
    )

    # Add logger for callbacks to use
    gatherer._logger = structlog.get_logger(f"agents.{gatherer.name}")

    return gatherer


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

    # Create gatherer agent for standalone testing
    # Note: In production, gatherer is used as an AgentTool by coordinator
    root_agent = create_gatherer_agent(bot_controller=bot_controller, mc_data_service=mc_data_service, config=config)

    logger.info("Gatherer agent created successfully for ADK deployment")

except Exception as e:
    error_msg = str(e)
    logger.error(f"Failed to create gatherer agent: {error_msg}")
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
        model=config.default_model if "config" in locals() else "gemini-2.0-flash",
        instruction=f"The Minecraft Gatherer Agent failed to initialize due to: {error_msg}. Please inform the user about this error and suggest checking the .env configuration.",
        tools=[explain_error],
    )
