"""Test suite for enhanced agent communication callbacks."""
from unittest.mock import Mock, patch

from src.agents.callbacks import (
    get_configured_callbacks,
    log_agent_thoughts_callback,
    log_tool_invocation_end_callback,
    log_tool_invocation_start_callback,
)


class TestAgentThoughtsCallback:
    """Test the agent thoughts logging callback."""

    def test_should_log_agent_thoughts_when_agent_responds(self):
        """Agent thoughts should be captured from LLM responses."""
        # Arrange
        mock_logger = Mock()

        # Create callback context mock
        callback_context = Mock()
        callback_context.agent_name = "CoordinatorAgent"

        # Create llm_response mock
        llm_response = Mock()
        llm_response.text = "I need to gather oak logs first, then craft planks."
        llm_response.candidates = []

        # Act
        with patch("src.agents.callbacks.logger", mock_logger):
            result = log_agent_thoughts_callback(callback_context, llm_response)

        # Assert
        assert result is None  # Should return None to proceed
        mock_logger.bind.assert_called_once_with(agent="CoordinatorAgent")
        bound_logger = mock_logger.bind.return_value
        bound_logger.debug.assert_called_once()
        call_args = bound_logger.debug.call_args
        assert call_args[0][0] == "agent_thought"
        assert call_args[1]["thought"] == "I need to gather oak logs first, then craft planks."
        assert "timestamp" in call_args[1]

    def test_should_log_tool_calls_when_agent_uses_tools(self):
        """Tool calls should be logged from LLM response."""
        # Arrange
        mock_logger = Mock()

        # Create function call mock
        function_call = Mock()
        function_call.name = "find_nearest_blocks"
        function_call.args = {"block_type": "oak_log", "count": 5}

        # Create part with function call
        part = Mock()
        part.function_call = function_call

        # Create callback context
        callback_context = Mock()
        callback_context.agent_name = "GathererAgent"

        # Create llm_response mock
        llm_response = Mock()
        llm_response.text = None
        llm_response.candidates = [Mock(content=Mock(parts=[part]))]

        # Act
        with patch("src.agents.callbacks.logger", mock_logger):
            result = log_agent_thoughts_callback(callback_context, llm_response)

        # Assert
        assert result is None
        bound_logger = mock_logger.bind.return_value
        bound_logger.info.assert_called_once()
        call_args = bound_logger.info.call_args
        assert call_args[0][0] == "agent_tool_call"
        assert call_args[1]["tool"] == "find_nearest_blocks"
        assert call_args[1]["args"] == {"block_type": "oak_log", "count": 5}

    def test_should_log_agent_delegation(self):
        """Agent delegations should be logged."""
        # Arrange
        mock_logger = Mock()

        # Create function call for agent delegation
        function_call = Mock()
        function_call.name = "GathererAgent"
        function_call.args = {"task": "gather 5 oak logs"}

        part = Mock()
        part.function_call = function_call

        callback_context = Mock()
        callback_context.agent_name = "CoordinatorAgent"

        # Create llm_response mock
        llm_response = Mock()
        llm_response.text = None
        llm_response.candidates = [Mock(content=Mock(parts=[part]))]

        # Act
        with patch("src.agents.callbacks.logger", mock_logger):
            result = log_agent_thoughts_callback(callback_context, llm_response)

        # Assert
        assert result is None
        bound_logger = mock_logger.bind.return_value
        assert bound_logger.info.call_count == 2  # Both tool call and delegation

        # Check delegation log
        delegation_call = None
        for call in bound_logger.info.call_args_list:
            if call[0][0] == "agent_delegation":
                delegation_call = call
                break

        assert delegation_call is not None
        assert delegation_call[1]["from_agent"] == "CoordinatorAgent"
        assert delegation_call[1]["to_agent"] == "GathererAgent"
        assert delegation_call[1]["task"] == {"task": "gather 5 oak logs"}


class TestToolInvocationCallbacks:
    """Test tool invocation start/end callbacks."""

    def test_should_log_tool_start_with_context(self):
        """Tool invocation start should log context."""
        # Arrange
        mock_logger = Mock()

        tool_context = Mock()
        tool_context.agent_name = "CrafterAgent"
        tool_context.state = {"minecraft.inventory": {"oak_log": 1}}

        tool_mock = Mock()
        tool_mock.name = "craft_item"

        kwargs = {"tool": tool_mock, "args": {"item_name": "oak_planks", "quantity": 4}}

        # Act
        with patch("src.agents.callbacks.logger", mock_logger):
            with patch("time.perf_counter", return_value=1000.0):
                result = log_tool_invocation_start_callback(tool_context, **kwargs)

        # Assert
        assert result is None
        bound_logger = mock_logger.bind.return_value
        bound_logger.debug.assert_called_once()
        call_args = bound_logger.debug.call_args
        assert call_args[0][0] == "tool_invocation_start"
        assert call_args[1]["tool"] == "craft_item"
        assert call_args[1]["args"] == {"item_name": "oak_planks", "quantity": 4}
        assert call_args[1]["state_snapshot"] == {"minecraft.inventory": {"oak_log": 1}}
        assert tool_context._start_time == 1000.0

    def test_should_log_tool_end_with_duration(self):
        """Tool invocation end should log result and duration."""
        # Arrange
        mock_logger = Mock()

        tool_context = Mock()
        tool_context.agent_name = "CrafterAgent"
        tool_context._start_time = 1000.0
        tool_context.state = {"minecraft.inventory": {"oak_planks": 4}}

        tool_response = {"status": "success", "crafted": 4}

        tool_mock = Mock()
        tool_mock.name = "craft_item"

        kwargs = {"tool": tool_mock}

        # Act
        with patch("src.agents.callbacks.logger", mock_logger):
            with patch("time.perf_counter", return_value=1001.5):
                result = log_tool_invocation_end_callback(tool_context, tool_response, **kwargs)

        # Assert
        assert result is None
        bound_logger = mock_logger.bind.return_value
        assert bound_logger.debug.call_count == 2  # Complete + state after

        # Check completion log
        complete_call = bound_logger.debug.call_args_list[0]
        assert complete_call[0][0] == "tool_invocation_complete"
        assert complete_call[1]["duration_ms"] == 1500.0
        assert complete_call[1]["result"] == {"status": "success", "crafted": 4}

        # Check state log
        state_call = bound_logger.debug.call_args_list[1]
        assert state_call[0][0] == "state_after_tool"
        assert state_call[1]["current_state"] == {"minecraft.inventory": {"oak_planks": 4}}


class TestConfiguredCallbacks:
    """Test callback configuration based on environment."""

    @patch.dict("os.environ", {"MINECRAFT_AGENT_LOG_AGENT_THOUGHTS": "true"})
    def test_should_include_model_callback_when_thoughts_enabled(self):
        """Model callback should be included when thoughts logging enabled."""
        # Act
        callbacks = get_configured_callbacks()

        # Assert
        assert "after_model_callback" in callbacks
        assert callbacks["after_model_callback"] == log_agent_thoughts_callback

    @patch.dict("os.environ", {"MINECRAFT_AGENT_LOG_TOOL_CALLS": "true"})
    def test_should_include_tool_callbacks_when_tools_enabled(self):
        """Tool callbacks should be included when tool logging enabled."""
        # Act
        callbacks = get_configured_callbacks()

        # Assert
        assert "before_tool_callback" in callbacks
        assert "after_tool_callback" in callbacks
        assert callbacks["before_tool_callback"] == log_tool_invocation_start_callback
        assert callbacks["after_tool_callback"] == log_tool_invocation_end_callback

    @patch.dict(
        "os.environ", {"MINECRAFT_AGENT_LOG_AGENT_THOUGHTS": "false", "MINECRAFT_AGENT_LOG_TOOL_CALLS": "false"}
    )
    def test_should_exclude_callbacks_when_logging_disabled(self):
        """Callbacks should be excluded when logging is disabled."""
        # Act
        callbacks = get_configured_callbacks()

        # Assert
        assert len(callbacks) == 0
