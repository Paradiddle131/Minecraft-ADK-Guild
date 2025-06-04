"""Enhanced terminal logging for agent communications."""
import os
from typing import Any, Dict, Optional

import structlog
from structlog.dev import ConsoleRenderer
from structlog.processors import CallsiteParameter, CallsiteParameterAdder, add_log_level
from structlog.stdlib import LoggerFactory

# ANSI color codes for different agents
AGENT_COLORS = {
    "CoordinatorAgent": "\033[94m",  # Blue
    "GathererAgent": "\033[92m",  # Green
    "CrafterAgent": "\033[93m",  # Yellow
    "default": "\033[96m",  # Cyan
}

# ANSI reset code
RESET_COLOR = "\033[0m"

# Event type formatting
EVENT_ICONS = {"thought": "💭", "tool_call": "🔧", "delegation": "→", "result": "✓", "error": "❌"}

# Fallback for non-emoji terminals
EVENT_LABELS = {
    "thought": "[Thought]",
    "tool_call": "[Tool]",
    "delegation": "[Delegate]",
    "result": "[Result]",
    "error": "[Error]",
}


def get_agent_color(agent_name: str) -> str:
    """
    Get ANSI color code for an agent.

    Args:
        agent_name: Name of the agent

    Returns:
        ANSI color code string
    """
    return AGENT_COLORS.get(agent_name, AGENT_COLORS["default"])


def format_agent_output(agent_name: str, message: str, event_type: Optional[str] = None) -> str:
    """
    Format agent output with color and structure.

    Args:
        agent_name: Name of the agent
        message: Message to format
        event_type: Type of event (thought, tool_call, delegation, etc.)

    Returns:
        Formatted string with ANSI codes
    """
    color = get_agent_color(agent_name)

    # Base formatting
    output = f"{color}[{agent_name}]{RESET_COLOR}"

    # Add event type formatting
    if event_type:
        # Check if terminal supports emoji
        use_emoji = os.getenv("MINECRAFT_AGENT_USE_EMOJI", "true").lower() == "true"

        if use_emoji and event_type in EVENT_ICONS:
            icon = EVENT_ICONS[event_type]
            output += f" {icon}"
        elif event_type in EVENT_LABELS:
            output += f" {EVENT_LABELS[event_type]}"

        # Add indentation for thoughts
        if event_type == "thought":
            message = "  " + message.replace("\n", "\n  ")

        # Highlight tool calls
        elif event_type == "tool_call":
            # Extract tool name if present
            if "(" in message:
                tool_name = message.split("(")[0]
                output += f" {color}{tool_name}{RESET_COLOR}"
                message = "(" + message.split("(", 1)[1]

        # Format delegations
        elif event_type == "delegation":
            if "GathererAgent" in message:
                delegate_color = get_agent_color("GathererAgent")
            elif "CrafterAgent" in message:
                delegate_color = get_agent_color("CrafterAgent")
            else:
                delegate_color = AGENT_COLORS["default"]

            message = message.replace("GathererAgent", f"{delegate_color}GathererAgent{RESET_COLOR}")
            message = message.replace("CrafterAgent", f"{delegate_color}CrafterAgent{RESET_COLOR}")

    output += f" {message}"
    return output


def setup_terminal_logging() -> str:
    """
    Configure structlog for enhanced terminal output.

    Returns:
        Configured log level
    """
    # Get verbosity from environment
    log_level = os.getenv("MINECRAFT_AGENT_LOG_VERBOSITY", "INFO").upper()

    # Configure structlog with pretty console output
    structlog.configure(
        processors=[
            add_log_level,
            CallsiteParameterAdder(parameters=[CallsiteParameter.FILENAME, CallsiteParameter.LINENO]),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            ConsoleRenderer(colors=True),
        ],
        context_class=dict,
        logger_factory=LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    return log_level


def log_agent_communication(
    logger: Any, agent_name: str, event_type: str, message: str, details: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log agent communication with appropriate formatting.

    Args:
        logger: Logger instance
        agent_name: Name of the agent
        event_type: Type of event (thought, tool_call, delegation, etc.)
        message: Main message to log
        details: Additional details to include
    """
    # Map event types to log methods and keys
    event_mapping = {
        "thought": ("debug", "agent_thought"),
        "tool_call": ("info", "agent_tool_call"),
        "delegation": ("info", "agent_delegation"),
        "result": ("info", "agent_result"),
        "error": ("error", "agent_error"),
    }

    log_method_name, log_key = event_mapping.get(event_type, ("info", "agent_event"))
    log_method = getattr(logger, log_method_name)

    # Build log kwargs
    log_kwargs = {"agent": agent_name, "message": message}

    # Add details if provided
    if details:
        if event_type == "tool_call" and "block_type" in details:
            log_kwargs["tool"] = message  # Tool name
            log_kwargs["args"] = details
        else:
            log_kwargs["details"] = details

    # Format terminal output
    terminal_message = format_agent_output(agent_name, message, event_type)

    # Log with formatting
    log_method(log_key, terminal_output=terminal_message, **log_kwargs)
