"""Minecraft Coordinator Agent - ADK deployment module.

This module creates and exports the root_agent for ADK deployment commands.
When used with 'adk web', the bot will not automatically connect to Minecraft.
"""
import logging
import os
import sys

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import TYPE_CHECKING

import structlog
from google.adk.agents import LlmAgent
from google.adk.tools.agent_tool import AgentTool

from minecraft_crafter.agent import create_crafter_agent
from minecraft_gatherer.agent import create_gatherer_agent
from src.bridge.bridge_manager import BridgeManager
from src.config import get_config, setup_google_ai_credentials
from src.logging_config import setup_logging
from src.minecraft_bot_controller import BotController
from src.minecraft_data_service import MinecraftDataService
from src.tools.mineflayer_tools import create_mineflayer_tools

from .callbacks import get_configured_callbacks
from .prompt import COORDINATOR_PROMPT

if TYPE_CHECKING:
    from google.adk.common import Runner

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)


def create_coordinator_agent(
    runner: "Runner" = None, bot_controller=None, mc_data_service=None, config=None
) -> LlmAgent:
    """Create the coordinator agent with AgentTool pattern.

    Args:
        runner: The ADK runner instance for agent creation
        bot_controller: BotController instance
        mc_data_service: MinecraftDataService instance
        config: Agent configuration instance

    Returns:
        Configured coordinator agent that orchestrates all operations
    """
    # Get config if not provided
    if config is None:
        config = get_config()
    # Create sub-agents (they don't need runner since they use output_key)
    gatherer_agent = create_gatherer_agent(bot_controller, mc_data_service, config)
    crafter_agent = create_crafter_agent(bot_controller, mc_data_service, config)

    # Get base tools
    tools = create_mineflayer_tools(bot_controller, mc_data_service)

    # Add sub-agents as AgentTools
    tools.extend(
        [
            AgentTool(agent=gatherer_agent),
            AgentTool(agent=crafter_agent),
        ]
    )

    # Get configured callbacks
    callbacks = get_configured_callbacks()

    # Create coordinator with tools only (no sub_agents)
    # Register callbacks individually as per ADK API
    coordinator = LlmAgent(
        name="CoordinatorAgent",
        model=config.default_model,
        instruction=COORDINATOR_PROMPT,
        tools=tools,
        **callbacks,  # Unpack callback dict to pass as individual parameters
    )

    # Add logger for callbacks to use
    coordinator._logger = structlog.get_logger(f"agents.{coordinator.name}")

    return coordinator


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
    root_agent = create_coordinator_agent(
        runner=None, bot_controller=bot_controller, mc_data_service=mc_data_service, config=config
    )

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
        model=config.default_model if "config" in locals() else "gemini-2.0-flash",
        instruction=f"The Minecraft Coordinator Agent failed to initialize due to: {error_msg}. Please inform the user about this error and suggest checking the .env configuration.",
        tools=[explain_error],
    )
