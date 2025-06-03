"""Crafter Agent - Specialized agent for crafting operations."""

from google.adk.agents import LlmAgent

from ...tools.mineflayer_tools import get_mineflayer_tools
from .prompt import CRAFTER_PROMPT


def create_crafter_agent() -> LlmAgent:
    """Create the crafter agent with structured output.

    Returns:
        Configured crafter agent that returns results via output_key
    """
    crafter = LlmAgent(
        name="CrafterAgent",
        instruction=CRAFTER_PROMPT,
        output_key="crafting_result",  # Structured output to state
        tools=get_mineflayer_tools(),
    )

    return crafter
