"""Enhanced callbacks for comprehensive agent communication logging."""
import os
import time
from datetime import datetime
from typing import Any, Callable, Dict, Optional

import structlog

logger = structlog.get_logger(__name__)


def log_agent_thoughts_callback(callback_context: Any, **kwargs) -> None:
    """
    Callback triggered after model generates a response.
    Logs agent thoughts and tool calls.

    Args:
        callback_context: ADK callback context
        **kwargs: Additional arguments including llm_response

    Returns:
        None to proceed with original response
    """
    try:
        # Extract llm_response from kwargs
        llm_response = kwargs.get("llm_response")
        if not llm_response:
            return None

        # Get agent name from callback context
        agent_name = getattr(callback_context, "agent_name", "UnknownAgent")

        # Try to get agent logger from invocation context
        invocation_context = getattr(callback_context, "_invocation_context", None)
        agent = None
        if invocation_context:
            agent = getattr(invocation_context, "agent", None)

        if agent and hasattr(agent, "_logger"):
            agent_logger = agent._logger
        else:
            # Fallback to module logger with agent binding
            agent_logger = logger.bind(agent=agent_name)

        timestamp = datetime.utcnow().isoformat()

        # Check if this is a text response (agent thinking)
        # ADK wraps the actual response, we need to check the content
        if hasattr(llm_response, "content") and llm_response.content:
            # For text responses
            agent_logger.debug("agent_thought", thought=str(llm_response.content)[:500], timestamp=timestamp)
            print(f"\n💭 [{agent_name}] Thinking: {str(llm_response.content)[:200]}...")

        # Check if there are function calls in the response
        if hasattr(llm_response, "function_calls") and llm_response.function_calls:
            for func_call in llm_response.function_calls:
                func_name = getattr(func_call, "name", "unknown")
                func_args = getattr(func_call, "args", {})

                agent_logger.info(
                    "agent_tool_call",
                    tool=func_name,
                    args=dict(func_args) if func_args else {},
                    timestamp=timestamp,
                )
                print(f"🔧 [{agent_name}] Calling tool: {func_name}")

                # Check if it's a tool delegation (AgentTool)
                if func_name in ["GathererAgent", "CrafterAgent"]:
                    agent_logger.info(
                        "agent_delegation",
                        from_agent=agent_name,
                        to_agent=func_name,
                        task=dict(func_args) if func_args else {},
                        timestamp=timestamp,
                    )
                    print(f"→ [{agent_name}] Delegating to {func_name}")

    except Exception as e:
        logger.error("Error in agent thoughts callback", error=str(e), exc_info=True)

    # Return None to proceed with original response
    return None


def log_tool_invocation_start_callback(tool_context: Any, **kwargs) -> None:
    """
    Callback triggered before tool execution.
    Logs tool invocation with context.

    Args:
        tool_context: ADK tool context with tool info
        **kwargs: Additional arguments including tool details

    Returns:
        None to proceed with tool execution
    """
    try:
        # Get agent and tool info from context
        agent_name = getattr(tool_context, "agent_name", "UnknownAgent")

        # Try to get agent logger from invocation context
        invocation_context = getattr(tool_context, "_invocation_context", None)
        agent = None
        if invocation_context:
            agent = getattr(invocation_context, "agent", None)

        if agent and hasattr(agent, "_logger"):
            agent_logger = agent._logger
        else:
            agent_logger = logger.bind(agent=agent_name)

        # Extract tool info from kwargs
        tool = kwargs.get("tool", {})
        tool_name = getattr(tool, "name", kwargs.get("tool_name", "unknown"))
        tool_args = kwargs.get("args", {})

        # Log tool invocation start
        # The state object is an ADK State object, not a dict
        state_obj = getattr(tool_context, "state", None)
        state_snapshot = {}
        if state_obj:
            try:
                # Try to get a snapshot of state keys we care about
                for key in ["minecraft.inventory", "minecraft.position", "task.current"]:
                    if hasattr(state_obj, "get"):
                        val = state_obj.get(key)
                        if val is not None:
                            state_snapshot[key] = val
            except Exception:
                # If state access fails, just use empty snapshot
                pass

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
        logger.error("Error in tool invocation start callback", error=str(e), exc_info=True)

    return None


def log_tool_invocation_end_callback(tool_context: Any, **kwargs) -> None:
    """
    Callback triggered after tool execution.
    Logs tool result and duration.

    Args:
        tool_context: ADK tool context with tool result
        **kwargs: Additional arguments including tool result

    Returns:
        None to use original tool result
    """
    try:
        # Get agent info from context
        agent_name = getattr(tool_context, "agent_name", "UnknownAgent")

        # Try to get agent logger from invocation context
        invocation_context = getattr(tool_context, "_invocation_context", None)
        agent = None
        if invocation_context:
            agent = getattr(invocation_context, "agent", None)

        if agent and hasattr(agent, "_logger"):
            agent_logger = agent._logger
        else:
            agent_logger = logger.bind(agent=agent_name)

        # Extract tool info from kwargs
        tool = kwargs.get("tool", {})
        tool_name = getattr(tool, "name", kwargs.get("tool_name", "unknown"))
        tool_result = kwargs.get("result", {})

        # Calculate duration if start time was stored
        duration_ms = None
        if hasattr(tool_context, "_start_time"):
            duration_ms = (time.perf_counter() - tool_context._start_time) * 1000

        # Log tool completion
        agent_logger.debug(
            "tool_invocation_complete",
            tool=tool_name,
            duration_ms=duration_ms,
            result=tool_result,
            timestamp=datetime.utcnow().isoformat(),
        )

        if duration_ms:
            print(f"✓ [{agent_name}] Tool {tool_name} completed in {duration_ms:.0f}ms")

        # Log state changes if any
        # The state object is an ADK State object, not a dict
        state_obj = getattr(tool_context, "state", None)
        current_state = {}
        if state_obj:
            try:
                # Try to get a snapshot of state keys we care about
                for key in ["minecraft.inventory", "minecraft.position", "task.current"]:
                    if hasattr(state_obj, "get"):
                        val = state_obj.get(key)
                        if val is not None:
                            current_state[key] = val
            except Exception:
                # If state access fails, just use empty snapshot
                pass
        # In the before callback, we'd need to store the previous state
        # For now, just log that state may have changed
        agent_logger.debug(
            "state_after_tool",
            tool=tool_name,
            current_state=current_state,
            timestamp=datetime.utcnow().isoformat(),
        )

    except Exception as e:
        logger.error("Error in tool invocation end callback", error=str(e), exc_info=True)

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
