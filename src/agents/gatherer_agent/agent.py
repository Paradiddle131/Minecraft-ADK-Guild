"""Gatherer Agent - Specialized agent for resource gathering."""

import structlog
from google.adk.agents import LlmAgent

from ...tools.mineflayer_tools import create_mineflayer_tools
from ..callbacks import get_configured_callbacks
from .prompt import GATHERER_PROMPT


def create_gatherer_agent(bot_controller=None, mc_data_service=None) -> LlmAgent:
    """Create the gatherer agent with structured output.

    Args:
        bot_controller: BotController instance
        mc_data_service: MinecraftDataService instance

    Returns:
        Configured gatherer agent that returns results via output_key
    """
    # Get configured callbacks
    callbacks = get_configured_callbacks()

    # Register callbacks individually as per ADK API
    gatherer = LlmAgent(
        name="GathererAgent",
        model="gemini-2.0-flash",
        instruction=GATHERER_PROMPT,
        output_key="gathering_result",  # Structured output to state
        tools=create_mineflayer_tools(bot_controller, mc_data_service),
        **callbacks,  # Unpack callback dict to pass as individual parameters
    )

    # Add logger for callbacks to use
    gatherer._logger = structlog.get_logger(f"agents.{gatherer.name}")

    return gatherer
