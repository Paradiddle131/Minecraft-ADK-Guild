"""Coordinator Agent - Main orchestrator for all Minecraft operations."""

from typing import TYPE_CHECKING

import structlog
from google.adk.agents import LlmAgent
from google.adk.tools.agent_tool import AgentTool

from ...tools.mineflayer_tools import create_mineflayer_tools
from ..callbacks import get_configured_callbacks
from ..crafter_agent.agent import create_crafter_agent
from ..gatherer_agent.agent import create_gatherer_agent
from .prompt import COORDINATOR_PROMPT

if TYPE_CHECKING:
    from google.adk.common import Runner


def create_coordinator_agent(runner: "Runner" = None, bot_controller=None, mc_data_service=None) -> LlmAgent:
    """Create the coordinator agent with AgentTool pattern.

    Args:
        runner: The ADK runner instance for agent creation
        bot_controller: BotController instance
        mc_data_service: MinecraftDataService instance

    Returns:
        Configured coordinator agent that orchestrates all operations
    """
    # Create sub-agents (they don't need runner since they use output_key)
    gatherer_agent = create_gatherer_agent(bot_controller, mc_data_service)
    crafter_agent = create_crafter_agent(bot_controller, mc_data_service)

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
        model="gemini-2.0-flash",
        instruction=COORDINATOR_PROMPT,
        tools=tools,
        **callbacks,  # Unpack callback dict to pass as individual parameters
    )

    # Add logger for callbacks to use
    coordinator._logger = structlog.get_logger(f"agents.{coordinator.name}")

    return coordinator
