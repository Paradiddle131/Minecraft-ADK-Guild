"""Test terminal logging enhancements."""
from unittest.mock import Mock, patch

from src.agents.terminal_logging import (
    format_agent_output,
    get_agent_color,
    log_agent_communication,
    setup_terminal_logging,
)


class TestTerminalFormatting:
    """Test terminal output formatting functions."""

    def test_should_format_agent_output_with_color(self):
        """Agent output should be formatted with color codes."""
        # Act
        output = format_agent_output("CoordinatorAgent", "Planning next action...")

        # Assert
        assert "[CoordinatorAgent]" in output
        assert "Planning next action..." in output
        # Should contain ANSI color codes
        assert "\033[" in output

    def test_should_use_different_colors_for_different_agents(self):
        """Different agents should have different colors."""
        # Act
        coordinator_color = get_agent_color("CoordinatorAgent")
        gatherer_color = get_agent_color("GathererAgent")
        crafter_color = get_agent_color("CrafterAgent")

        # Assert
        assert coordinator_color != gatherer_color
        assert gatherer_color != crafter_color
        assert coordinator_color != crafter_color

    def test_should_format_thought_with_indentation(self):
        """Agent thoughts should be indented for clarity."""
        # Act
        output = format_agent_output("GathererAgent", "I need to find oak logs nearby", event_type="thought")

        # Assert
        assert "  " in output  # Contains indentation
        assert "💭" in output or "Thought:" in output

    def test_should_format_tool_call_distinctly(self):
        """Tool calls should have distinct formatting."""
        # Act
        output = format_agent_output(
            "CrafterAgent", "craft_item(item_name='oak_planks', quantity=4)", event_type="tool_call"
        )

        # Assert
        assert "🔧" in output or "Tool:" in output
        assert "craft_item" in output

    def test_should_format_delegation_with_arrow(self):
        """Agent delegation should show flow."""
        # Act
        output = format_agent_output(
            "CoordinatorAgent", "Delegating to GathererAgent: gather 5 oak logs", event_type="delegation"
        )

        # Assert
        assert "→" in output or "Delegating" in output
        assert "GathererAgent" in output


class TestTerminalLoggingSetup:
    """Test terminal logging configuration."""

    @patch("structlog.configure")
    def test_should_setup_structlog_with_pretty_rendering(self, mock_configure):
        """Terminal logging should use pretty console rendering."""
        # Act
        setup_terminal_logging()

        # Assert
        mock_configure.assert_called_once()
        config_call = mock_configure.call_args[1]

        # Check processors include console renderer
        processors = config_call.get("processors", [])
        processor_names = [p.__class__.__name__ for p in processors if hasattr(p, "__class__")]
        assert any("ConsoleRenderer" in name for name in processor_names)

    def test_should_respect_verbosity_environment_variable(self):
        """Logging verbosity should be configurable."""
        with patch.dict("os.environ", {"MINECRAFT_AGENT_LOG_VERBOSITY": "DEBUG"}):
            # Act
            level = setup_terminal_logging()

            # Assert
            assert level == "DEBUG"

        with patch.dict("os.environ", {"MINECRAFT_AGENT_LOG_VERBOSITY": "WARNING"}):
            # Act
            level = setup_terminal_logging()

            # Assert
            assert level == "WARNING"


class TestAgentCommunicationLogging:
    """Test high-level agent communication logging."""

    def test_should_log_agent_thought_to_terminal(self):
        """Agent thoughts should be logged with formatting."""
        # Arrange
        mock_logger = Mock()

        # Act
        log_agent_communication(
            logger=mock_logger,
            agent_name="CoordinatorAgent",
            event_type="thought",
            message="I need to delegate this gathering task",
            details={"confidence": 0.95},
        )

        # Assert
        mock_logger.debug.assert_called_once()
        call_args = mock_logger.debug.call_args
        assert "agent_thought" in call_args[0]
        assert call_args[1]["agent"] == "CoordinatorAgent"
        assert call_args[1]["message"] == "I need to delegate this gathering task"
        assert call_args[1]["details"] == {"confidence": 0.95}

    def test_should_log_tool_invocation_at_info_level(self):
        """Tool invocations should be logged at info level."""
        # Arrange
        mock_logger = Mock()

        # Act
        log_agent_communication(
            logger=mock_logger,
            agent_name="GathererAgent",
            event_type="tool_call",
            message="find_nearest_blocks",
            details={"block_type": "oak_log", "count": 5},
        )

        # Assert
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert "agent_tool_call" in call_args[0]
        assert call_args[1]["tool"] == "find_nearest_blocks"

    def test_should_log_delegation_prominently(self):
        """Agent delegations should be logged prominently."""
        # Arrange
        mock_logger = Mock()

        # Act
        log_agent_communication(
            logger=mock_logger,
            agent_name="CoordinatorAgent",
            event_type="delegation",
            message="Delegating to CrafterAgent",
            details={"task": "craft 4 sticks"},
        )

        # Assert
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert "agent_delegation" in call_args[0]
        assert "CrafterAgent" in str(call_args)
