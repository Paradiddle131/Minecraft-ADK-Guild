"""Test integration of callbacks with agents."""
from unittest.mock import Mock, patch

from src.agents.coordinator_agent.agent import create_coordinator_agent
from src.agents.crafter_agent.agent import create_crafter_agent
from src.agents.gatherer_agent.agent import create_gatherer_agent


class TestCallbackIntegration:
    """Test that callbacks are properly integrated into agents."""

    @patch("src.agents.coordinator_agent.agent.get_configured_callbacks")
    @patch("src.agents.coordinator_agent.agent.LlmAgent")
    def test_should_register_callbacks_when_coordinator_created(self, mock_llm_agent, mock_get_callbacks):
        """Coordinator agent should register callbacks during creation."""
        # Arrange
        mock_callback = Mock()
        mock_get_callbacks.return_value = {"after_model_callback": mock_callback, "before_tool_callback": mock_callback}
        mock_agent_instance = Mock()
        mock_llm_agent.return_value = mock_agent_instance

        # Act
        create_coordinator_agent()

        # Assert
        mock_get_callbacks.assert_called_once()
        mock_llm_agent.assert_called()
        call_kwargs = mock_llm_agent.call_args[1]
        assert "after_model_callback" in call_kwargs
        assert call_kwargs["after_model_callback"] == mock_callback
        assert "before_tool_callback" in call_kwargs
        assert call_kwargs["before_tool_callback"] == mock_callback

    @patch("src.agents.gatherer_agent.agent.get_configured_callbacks")
    @patch("src.agents.gatherer_agent.agent.LlmAgent")
    def test_should_register_callbacks_when_gatherer_created(self, mock_llm_agent, mock_get_callbacks):
        """Gatherer agent should register callbacks during creation."""
        # Arrange
        mock_callback = Mock()
        mock_get_callbacks.return_value = {"after_model_callback": mock_callback}
        mock_agent_instance = Mock()
        mock_llm_agent.return_value = mock_agent_instance

        # Act
        create_gatherer_agent()

        # Assert
        mock_get_callbacks.assert_called_once()
        mock_llm_agent.assert_called()
        call_kwargs = mock_llm_agent.call_args[1]
        assert "after_model_callback" in call_kwargs
        assert call_kwargs["after_model_callback"] == mock_callback

    @patch("src.agents.crafter_agent.agent.get_configured_callbacks")
    @patch("src.agents.crafter_agent.agent.LlmAgent")
    def test_should_register_callbacks_when_crafter_created(self, mock_llm_agent, mock_get_callbacks):
        """Crafter agent should register callbacks during creation."""
        # Arrange
        mock_before_tool = Mock()
        mock_after_tool = Mock()
        mock_get_callbacks.return_value = {
            "before_tool_callback": mock_before_tool,
            "after_tool_callback": mock_after_tool,
        }
        mock_agent_instance = Mock()
        mock_llm_agent.return_value = mock_agent_instance

        # Act
        create_crafter_agent()

        # Assert
        mock_get_callbacks.assert_called_once()
        mock_llm_agent.assert_called()
        call_kwargs = mock_llm_agent.call_args[1]
        assert "before_tool_callback" in call_kwargs
        assert call_kwargs["before_tool_callback"] == mock_before_tool
        assert "after_tool_callback" in call_kwargs
        assert call_kwargs["after_tool_callback"] == mock_after_tool

    @patch.dict("os.environ", {"MINECRAFT_AGENT_LOG_AGENT_THOUGHTS": "true"})
    def test_should_have_logger_in_agent_context(self):
        """Agents should have logger available for callbacks."""
        # Act
        agent = create_gatherer_agent()

        # Assert
        # LlmAgent instances should have _logger attribute for callbacks
        assert hasattr(agent, "name")
        assert agent.name == "GathererAgent"
        assert hasattr(agent, "_logger")
        assert agent._logger is not None
