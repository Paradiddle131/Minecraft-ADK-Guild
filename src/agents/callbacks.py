"""
Callback functions for ADK agents
These callbacks provide logging and monitoring capabilities for agent thoughts
"""

from typing import Any, Optional

from ..logging_config import get_logger

logger = get_logger(__name__)


def log_agent_thoughts_callback(**kwargs) -> Optional[Any]:
    """Callback to log agent's raw LLM response including reasoning

    This callback is called after the LLM generates a response but before
    it's processed further. It logs the agent's full response including
    internal reasoning/thoughts.

    Args:
        **kwargs: Keyword arguments passed by ADK framework
            - callback_context: CallbackContext containing agent info and state
            - llm_response: The LlmResponse object from the model

    Returns:
        None - allows normal processing to continue
        LlmResponse - to replace the original response
    """
    try:
        callback_context = kwargs.get("callback_context")
        llm_response = kwargs.get("llm_response")

        agent_name = getattr(callback_context, "agent_name", "Unknown Agent") if callback_context else "Unknown Agent"

        if llm_response and hasattr(llm_response, "content"):
            logger.info(f"{'='*40}")
            logger.info(f"🤖 {agent_name} THOUGHTS AND RESPONSE:")
            logger.info(f"{'='*40}")

            if hasattr(llm_response.content, "parts"):
                for part in llm_response.content.parts:
                    if hasattr(part, "text") and part.text:
                        logger.info(f"{part.text}")
                    elif hasattr(part, "function_call"):
                        logger.info(f"Tool Call: {part.function_call.name}")
                        if hasattr(part.function_call, "args"):
                            logger.info(f"Arguments: {part.function_call.args}")

            logger.info(f"{'='*40}")

    except Exception as e:
        logger.error(f"Error in thought logging callback: {e}")

    return None


def log_tool_execution_callback(**kwargs) -> Optional[dict]:
    """Callback to log tool execution results

    This callback is called after a tool executes, logging its results
    for debugging and monitoring.

    Args:
        **kwargs: Keyword arguments passed by ADK framework
            - tool_context: ToolContext containing agent/tool info and state
            - tool: The Tool object that was executed
            - tool_response: The tool's response dictionary

    Returns:
        None - uses original tool response
        dict - to replace the tool response
    """
    try:
        tool_context = kwargs.get("tool_context")
        tool = kwargs.get("tool")
        tool_response = kwargs.get("tool_response")

        tool_name = getattr(tool, "name", "Unknown Tool") if tool else "Unknown Tool"
        agent_name = getattr(tool_context, "agent_name", "Unknown Agent") if tool_context else "Unknown Agent"

        logger.info("--- Tool Execution Complete ---")
        logger.info(f"Agent: {agent_name}")
        logger.info(f"Tool: {tool_name}")
        logger.info(f"Result: {tool_response}")
        logger.info("-------------------------------")

    except Exception as e:
        logger.error(f"Error in tool logging callback: {e}")

    return None


def log_tool_call_callback(**kwargs) -> Optional[dict]:
    """Callback to log tool calls before execution

    This callback is called before a tool executes, logging the call
    for debugging and monitoring.

    Args:
        **kwargs: Keyword arguments passed by ADK framework
            - tool_context: ToolContext containing agent/tool info and state
            - tool: The Tool object about to be executed
            - args: The arguments being passed to the tool

    Returns:
        None - executes tool with original args
        dict - to skip tool execution and use this as result
    """
    try:
        tool_context = kwargs.get("tool_context")
        tool = kwargs.get("tool")
        args = kwargs.get("args")

        tool_name = getattr(tool, "name", "Unknown Tool") if tool else "Unknown Tool"
        agent_name = getattr(tool_context, "agent_name", "Unknown Agent") if tool_context else "Unknown Agent"

        logger.info("--- Tool Call ---")
        logger.info(f"Agent: {agent_name}")
        logger.info(f"Tool: {tool_name}")
        logger.info(f"Arguments: {args}")
        logger.info("-----------------")

    except Exception as e:
        logger.error(f"Error in tool call logging callback: {e}")

    return None


def log_before_agent_callback(**kwargs) -> Optional[Any]:
    """Callback to log when an agent starts execution

    This helps track which agent is currently active in the multi-agent flow.

    Args:
        **kwargs: Keyword arguments passed by ADK framework
            - callback_context: CallbackContext containing agent info and state

    Returns:
        None - allows normal agent execution
    """
    try:
        callback_context = kwargs.get("callback_context")
        agent_name = getattr(callback_context, "agent_name", "Unknown Agent") if callback_context else "Unknown Agent"

        logger.info(f"{'*'*40}")
        logger.info(f"▶️  AGENT STARTING: {agent_name}")
        logger.info(f"{'*'*40}")

        # Log any relevant state that might indicate why this agent was called
        if callback_context and hasattr(callback_context, "state"):
            user_request = callback_context.state.get("user_request")
            if user_request:
                logger.info(f"Processing request: {user_request}")

        logger.info("")

    except Exception as e:
        logger.error(f"Error in before agent callback: {e}")

    return None


def log_after_agent_callback(**kwargs) -> Optional[Any]:
    """Callback to log when an agent completes execution

    This helps track agent completion and results in the multi-agent flow.

    Args:
        **kwargs: Keyword arguments passed by ADK framework
            - callback_context: CallbackContext containing agent info and state

    Returns:
        None - uses original agent response
    """
    try:
        callback_context = kwargs.get("callback_context")
        agent_name = getattr(callback_context, "agent_name", "Unknown Agent") if callback_context else "Unknown Agent"

        logger.info(f"{'*'*40}")
        logger.info(f"✅ AGENT COMPLETE: {agent_name}")
        logger.info(f"{'*'*40}")

    except Exception as e:
        logger.error(f"Error in after agent callback: {e}")

    return None
