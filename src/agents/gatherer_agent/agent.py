"""Gatherer Agent - Specialized agent for resource gathering."""

from google.adk.agents import LlmAgent

from ...tools.mineflayer_tools import get_mineflayer_tools
from .prompt import GATHERER_PROMPT


def create_gatherer_agent() -> LlmAgent:
    """Create the gatherer agent with structured output.

    Returns:
        Configured gatherer agent that returns results via output_key
    """
    gatherer = LlmAgent(
        name="GathererAgent",
        instruction=GATHERER_PROMPT,
        output_key="gathering_result",  # Structured output to state
        tools=get_mineflayer_tools(),
    )

    return gatherer
