"""Coordinator Agent - Main orchestrator for all Minecraft operations."""

from typing import TYPE_CHECKING

from google.adk.agents import LlmAgent
from google.adk.tools.agent_tool import AgentTool

from ...tools.mineflayer_tools import get_mineflayer_tools
from ..crafter_agent.agent import create_crafter_agent
from ..gatherer_agent.agent import create_gatherer_agent
from .prompt import COORDINATOR_PROMPT

if TYPE_CHECKING:
    from google.adk.common import Runner


def create_coordinator_agent(runner: "Runner") -> LlmAgent:
    """Create the coordinator agent with AgentTool pattern.

    Args:
        runner: The ADK runner instance for agent creation

    Returns:
        Configured coordinator agent that orchestrates all operations
    """
    # Create sub-agents (they don't need runner since they use output_key)
    gatherer_agent = create_gatherer_agent()
    crafter_agent = create_crafter_agent()

    # Get base tools
    tools = get_mineflayer_tools()

    # Add sub-agents as AgentTools
    tools.extend(
        [
            AgentTool(agent=gatherer_agent, name="gatherer_tool"),
            AgentTool(agent=crafter_agent, name="crafter_tool"),
        ]
    )

    # Create coordinator with tools only (no sub_agents)
    coordinator = LlmAgent(
        runner=runner,
        name="CoordinatorAgent",
        instruction=COORDINATOR_PROMPT,
        tools=tools,
    )

    return coordinator
