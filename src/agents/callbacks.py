"""Enhanced callbacks for comprehensive agent communication logging."""
import os
import time
from datetime import datetime
from typing import Any, Callable, Dict, Optional

import structlog

logger = structlog.get_logger(__name__)


def log_agent_thoughts_callback(callback_context: Any, llm_response: Any) -> None:
    """
    Callback triggered after model generates a response.
    Logs agent thoughts and tool calls.

    Args:
        callback_context: ADK callback context
        llm_response: The LLM response object

    Returns:
        None to proceed with original response
    """
    try:
        # Get agent name from callback context
        agent_name = callback_context.agent_name or "UnknownAgent"
        # Use module logger for now (agents don't have direct access in callback)
        agent_logger = logger.bind(agent=agent_name)
        timestamp = datetime.utcnow().isoformat()

        # Log text responses (thoughts)
        if hasattr(llm_response, "text") and llm_response.text:
            agent_logger.debug("agent_thought", thought=llm_response.text, timestamp=timestamp)

        # Log tool calls from the response
        if hasattr(llm_response, "candidates") and llm_response.candidates:
            for candidate in llm_response.candidates:
                if hasattr(candidate, "content") and hasattr(candidate.content, "parts"):
                    for part in candidate.content.parts:
                        # Check for function calls in the parts
                        if hasattr(part, "function_call"):
                            agent_logger.info(
                                "agent_tool_call",
                                tool=part.function_call.name,
                                args=dict(part.function_call.args) if hasattr(part.function_call, "args") else {},
                                timestamp=timestamp,
                            )
                        # Check if it's a tool delegation (AgentTool)
                        if hasattr(part, "function_call") and part.function_call.name in [
                            "GathererAgent",
                            "CrafterAgent",
                        ]:
                            agent_logger.info(
                                "agent_delegation",
                                from_agent=agent_name,
                                to_agent=part.function_call.name,
                                task=dict(part.function_call.args) if hasattr(part.function_call, "args") else {},
                                timestamp=timestamp,
                            )
    except Exception as e:
        logger.error("Error in agent thoughts callback", error=str(e))

    # Return None to proceed with original response
    return None


def log_tool_invocation_start_callback(tool_context: Any, **kwargs) -> None:
    """
    Callback triggered before tool execution.
    Logs tool invocation with context.

    Args:
        tool_context: ADK tool context with tool info
        **kwargs: Additional keyword arguments from ADK

    Returns:
        None to proceed with tool execution
    """
    try:
        # Get agent name and tool info
        agent_name = tool_context.agent_name or "UnknownAgent"
        agent_logger = logger.bind(agent=agent_name)

        # Extract tool information from kwargs
        tool = kwargs.get("tool")
        tool_name = getattr(tool, "name", "unknown_tool") if tool else "unknown_tool"
        tool_args = kwargs.get("args", {})

        # Get current state snapshot
        state_snapshot = dict(tool_context.state) if hasattr(tool_context, "state") else {}

        agent_logger.debug(
            "tool_invocation_start",
            tool=tool_name,
            args=tool_args,
            state_snapshot=state_snapshot,
            timestamp=datetime.utcnow().isoformat(),
        )

        # Store start time in context for duration calculation
        tool_context._start_time = time.perf_counter()

    except Exception as e:
        logger.error("Error in tool invocation start callback", error=str(e))

    return None


def log_tool_invocation_end_callback(tool_context: Any, tool_response: Any, **kwargs) -> None:
    """
    Callback triggered after tool execution.
    Logs tool result and duration.

    Args:
        tool_context: ADK tool context
        tool_response: The response from the tool
        **kwargs: Additional keyword arguments from ADK

    Returns:
        None to use original tool result
    """
    try:
        # Get agent name
        agent_name = tool_context.agent_name or "UnknownAgent"
        agent_logger = logger.bind(agent=agent_name)

        # Extract tool name from kwargs
        tool = kwargs.get("tool")
        tool_name = getattr(tool, "name", "unknown_tool") if tool else "unknown_tool"

        # Calculate duration if start time was stored
        duration_ms = None
        if hasattr(tool_context, "_start_time"):
            duration_ms = (time.perf_counter() - tool_context._start_time) * 1000

        # Log tool completion
        agent_logger.debug(
            "tool_invocation_complete",
            tool=tool_name,
            duration_ms=duration_ms,
            result=tool_response if tool_response else {},
            timestamp=datetime.utcnow().isoformat(),
        )

        # Log state changes if any
        if hasattr(tool_context, "state"):
            current_state = dict(tool_context.state)
            agent_logger.debug(
                "state_after_tool",
                tool=tool_name,
                current_state=current_state,
                timestamp=datetime.utcnow().isoformat(),
            )

    except Exception as e:
        logger.error("Error in tool invocation end callback", error=str(e))

    return None


def get_configured_callbacks() -> Dict[str, Optional[Callable]]:
    """
    Get dict of callbacks based on environment configuration.

    Returns:
        Dict mapping callback types to callback functions
    """
    callbacks = {}

    # Check environment variables for which callbacks to enable
    if os.getenv("MINECRAFT_AGENT_LOG_AGENT_THOUGHTS", "true").lower() == "true":
        callbacks["after_model_callback"] = log_agent_thoughts_callback

    if os.getenv("MINECRAFT_AGENT_LOG_TOOL_CALLS", "true").lower() == "true":
        callbacks["before_tool_callback"] = log_tool_invocation_start_callback
        callbacks["after_tool_callback"] = log_tool_invocation_end_callback

    return callbacks


# Legacy callbacks for backward compatibility
def log_agent_communication_callback(response: Any, agent: Any) -> None:
    """Legacy callback - no longer used."""
    pass


def log_state_changes_callback(tool_response: Any, agent: Any, previous_state: Dict[str, Any]) -> None:
    """Legacy callback - state changes now logged in after_tool_callback."""
    pass


def log_tool_invocation_callback(tool_call: Any, agent: Any) -> Callable:
    """Legacy callback - replaced by before/after_tool_callback."""
    pass


def log_agent_delegation_callback(tool_call: Any, agent: Any) -> None:
    """Legacy callback - delegation now logged in after_model_callback."""
    pass


def log_function_calls_callback(response: Any, agent: Any) -> None:
    """Legacy callback - no longer used."""
    pass
