"""
Unit tests for ADK agent components
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.simple_agent import SimpleMinecraftAgent
from src.agents.simple_enhanced_agent import SimpleEnhancedAgent
from src.agents.workflow_agents import WorkflowAgentFactory
from src.bridge.bridge_manager import BridgeManager, BridgeConfig
from src.config import AgentConfig


@pytest.fixture
def mock_bridge():
    """Mock bridge manager for testing"""
    mock = AsyncMock(spec=BridgeManager)
    mock.get_position.return_value = {"x": 0, "y": 64, "z": 0}
    mock.get_inventory.return_value = [
        {"name": "stone", "count": 64},
        {"name": "oak_log", "count": 32}
    ]
    mock.chat = AsyncMock()
    mock.move_to = AsyncMock()
    mock.dig_block = AsyncMock()
    mock.place_block = AsyncMock()
    mock.execute_command = AsyncMock()
    
    # Mock event stream
    mock_event_stream = MagicMock()
    mock_event_stream.register_handler = MagicMock()
    mock.event_stream = mock_event_stream
    
    return mock


@pytest.fixture
def test_config():
    """Test configuration"""
    return AgentConfig(
        default_model="gemini-2.0-flash",
        agent_temperature=0.2,
        max_output_tokens=500,
        command_timeout_ms=5000
    )


class TestSimpleMinecraftAgent:
    """Test the main SimpleMinecraftAgent"""
    
    async def test_agent_initialization(self, mock_bridge, test_config):
        """Test agent initialization"""
        agent = SimpleMinecraftAgent(config=test_config)
        
        # Mock the bridge initialization
        with patch.object(agent, 'bridge', mock_bridge):
            # Mock event processor
            mock_event_processor = MagicMock()
            mock_event_processor.get_world_state.return_value = {}
            
            with patch.object(agent, 'event_processor', mock_event_processor):
                await agent.initialize()
                
                assert agent.agent is not None
                assert agent.runner is not None
                assert agent.session is not None
                assert agent.name == "MinecraftAgent"
                assert agent.model == "gemini-2.0-flash"
    
    async def test_agent_cleanup(self, mock_bridge, test_config):
        """Test agent cleanup"""
        agent = SimpleMinecraftAgent(config=test_config)
        agent.bridge = mock_bridge
        
        await agent.cleanup()
        mock_bridge.close.assert_called_once()
    
    async def test_fallback_commands(self, mock_bridge, test_config):
        """Test fallback command handling when ADK fails"""
        agent = SimpleMinecraftAgent(config=test_config)
        
        with patch.object(agent, 'bridge', mock_bridge):
            mock_event_processor = MagicMock()
            mock_event_processor.get_world_state.return_value = {}
            
            with patch.object(agent, 'event_processor', mock_event_processor):
                await agent.initialize()
                
                # Test inventory fallback
                response = await agent.process_command("check my inventory")
                assert "inventory" in response.lower()
                
                # Test position fallback  
                response = await agent.process_command("what's my position")
                assert "position" in response.lower()


class TestSimpleEnhancedAgent:
    """Test the enhanced agent with conversation history"""
    
    async def test_enhanced_agent_initialization(self, mock_bridge, test_config):
        """Test enhanced agent initialization"""
        agent = SimpleEnhancedAgent(mock_bridge, test_config)
        await agent.initialize()
        
        assert agent.agent is not None
        assert agent.session is not None
        assert "conversation_history" in agent.session.state
        assert "performance_metrics" in agent.session.state
    
    async def test_conversation_history(self, mock_bridge, test_config):
        """Test conversation history tracking"""
        agent = SimpleEnhancedAgent(mock_bridge, test_config)
        await agent.initialize()
        
        initial_length = len(agent.session.state["conversation_history"])
        
        # Add some mock history
        agent.session.state["conversation_history"].append({
            "type": "test",
            "content": "test message"
        })
        
        summary = agent.get_conversation_summary()
        assert summary["conversation_length"] == initial_length + 1
        assert "performance_metrics" in summary
    
    async def test_session_context_update(self, mock_bridge, test_config):
        """Test session context updating"""
        agent = SimpleEnhancedAgent(mock_bridge, test_config)
        await agent.initialize()
        
        await agent._update_session_context("TestPlayer")
        
        # Verify position and inventory were called
        mock_bridge.get_position.assert_called()
        mock_bridge.get_inventory.assert_called()


class TestWorkflowAgents:
    """Test workflow agent creation and composition"""
    
    async def test_workflow_factory_creation(self, mock_bridge, test_config):
        """Test workflow agent factory"""
        factory = WorkflowAgentFactory(mock_bridge, test_config)
        
        assert factory.bridge == mock_bridge
        assert factory.config == test_config
    
    async def test_sequential_agent_creation(self, mock_bridge, test_config):
        """Test sequential agent creation"""
        factory = WorkflowAgentFactory(mock_bridge, test_config)
        
        sequential_agent = factory.create_gather_and_build_sequential()
        
        assert sequential_agent.name == "GatherAndBuild"
        assert len(sequential_agent.sub_agents) == 2
        assert sequential_agent.sub_agents[0].name == "ResourceGatherer"
        assert sequential_agent.sub_agents[1].name == "SimpleBuilder"
    
    async def test_parallel_agent_creation(self, mock_bridge, test_config):
        """Test parallel agent creation"""
        factory = WorkflowAgentFactory(mock_bridge, test_config)
        
        parallel_agent = factory.create_multi_gatherer_parallel()
        
        assert parallel_agent.name == "MultiGatherer"
        assert len(parallel_agent.sub_agents) == 2
        assert parallel_agent.sub_agents[0].name == "WoodGatherer"
        assert parallel_agent.sub_agents[1].name == "StoneGatherer"
    
    async def test_loop_agent_creation(self, mock_bridge, test_config):
        """Test loop agent creation"""
        factory = WorkflowAgentFactory(mock_bridge, test_config)
        
        loop_agent = factory.create_retry_loop_agent()
        
        assert loop_agent.name == "RetryMovement"
        assert len(loop_agent.sub_agents) == 1
        assert loop_agent.sub_agents[0].name == "MovementRetrier"
        assert loop_agent.max_iterations == 3


class TestConfiguration:
    """Test configuration management"""
    
    def test_config_creation(self):
        """Test configuration creation with defaults"""
        config = AgentConfig()
        
        assert config.default_model == "gemini-2.0-flash"
        assert config.agent_temperature == 0.2
        assert config.max_output_tokens == 500
        assert config.minecraft_host == "localhost"
        assert config.minecraft_port == 25565
    
    def test_config_with_overrides(self):
        """Test configuration with custom values"""
        config = AgentConfig(
            default_model="gemini-1.5-pro",
            agent_temperature=0.5,
            minecraft_port=25565
        )
        
        assert config.default_model == "gemini-1.5-pro"
        assert config.agent_temperature == 0.5
        assert config.minecraft_port == 25565
    
    def test_config_credentials_setup(self):
        """Test credential setup"""
        from src.config import setup_google_ai_credentials
        
        config = AgentConfig(google_ai_api_key="test_key")
        
        credentials = setup_google_ai_credentials(config)
        assert "api_key" in credentials
        assert credentials["api_key"] == "test_key"


class TestErrorHandling:
    """Test error handling scenarios"""
    
    async def test_bridge_connection_failure(self, test_config):
        """Test handling of bridge connection failures"""
        agent = SimpleMinecraftAgent(config=test_config)
        
        # Mock a failing bridge
        mock_bridge = AsyncMock()
        mock_bridge.get_position.side_effect = Exception("Connection failed")
        mock_bridge.get_inventory.side_effect = Exception("Connection failed")
        
        with patch.object(agent, 'bridge', mock_bridge):
            mock_event_processor = MagicMock()
            mock_event_processor.get_world_state.return_value = {}
            
            with patch.object(agent, 'event_processor', mock_event_processor):
                await agent.initialize()
                
                # Should handle gracefully with fallback messages
                response = await agent.process_command("check inventory")
                assert "server" in response.lower() or "error" in response.lower()
    
    async def test_invalid_command_handling(self, mock_bridge, test_config):
        """Test handling of invalid commands"""
        agent = SimpleMinecraftAgent(config=test_config)
        
        with patch.object(agent, 'bridge', mock_bridge):
            mock_event_processor = MagicMock()
            mock_event_processor.get_world_state.return_value = {}
            
            with patch.object(agent, 'event_processor', mock_event_processor):
                await agent.initialize()
                
                # Test with empty command
                response = await agent.process_command("")
                assert isinstance(response, str)
                assert len(response) > 0
                
                # Test with very long command
                long_command = "x" * 1000
                response = await agent.process_command(long_command)
                assert isinstance(response, str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])