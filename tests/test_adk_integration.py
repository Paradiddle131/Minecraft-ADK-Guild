"""
Integration tests specifically for Google ADK integration
"""

import asyncio
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.simple_agent import SimpleMinecraftAgent
from src.agents.simple_enhanced_agent import SimpleEnhancedAgent
from src.agents.workflow_agents import WorkflowAgentFactory
from src.config import AgentConfig
from src.tools.mineflayer_tools import _set_bridge_manager


@pytest.fixture
def adk_test_config():
    """Configuration for ADK integration tests"""
    return AgentConfig(
        google_ai_api_key="test-api-key",  # Mock API key
        default_model="gemini-2.0-flash",
        agent_temperature=0.1,
        max_output_tokens=100,
        command_timeout_ms=2000
    )


@pytest.fixture
def mock_bridge_for_adk():
    """Mock bridge that simulates realistic responses"""
    bridge = AsyncMock()
    bridge.get_position.return_value = {"x": 10, "y": 64, "z": -5}
    bridge.get_inventory.return_value = [
        {"name": "stone", "count": 32},
        {"name": "oak_planks", "count": 64}
    ]
    bridge.chat = AsyncMock()
    bridge.move_to = AsyncMock()
    bridge.dig_block = AsyncMock()
    bridge.place_block = AsyncMock()
    bridge.execute_command = AsyncMock(return_value={"success": True})
    
    # Mock event stream
    mock_event_stream = MagicMock()
    mock_event_stream.register_handler = MagicMock()
    bridge.event_stream = mock_event_stream
    
    # Set bridge for tools
    _set_bridge_manager(bridge)
    
    return bridge


class TestADKIntegration:
    """Test Google ADK integration components"""
    
    @pytest.mark.asyncio
    async def test_simple_agent_with_mock_adk(self, adk_test_config, mock_bridge_for_adk):
        """Test SimpleMinecraftAgent with mocked ADK responses"""
        
        # Create agent
        agent = SimpleMinecraftAgent(config=adk_test_config)
        
        # Mock the bridge initialization
        with patch.object(agent, 'bridge', mock_bridge_for_adk):
            # Mock event processor
            mock_event_processor = MagicMock()
            mock_event_processor.get_world_state.return_value = {
                "nearby_players": [],
                "recent_blocks": []
            }
            
            with patch.object(agent, 'event_processor', mock_event_processor):
                # Mock the runner to avoid actual API calls
                mock_runner = AsyncMock()
                
                # Create a mock event that simulates ADK response
                mock_event = MagicMock()
                mock_event.is_final_response.return_value = True
                mock_event.content = MagicMock()
                mock_event.content.parts = [MagicMock(text="I found stone at position x=10, y=64, z=-5")]
                
                # Make runner return our mock event
                async def mock_run_async(*args, **kwargs):
                    yield mock_event
                
                mock_runner.run_async = mock_run_async
                
                with patch.object(agent, 'runner', mock_runner):
                    # Test command processing
                    response = await agent.process_command("Find stone blocks nearby")
                    
                    assert response == "I found stone at position x=10, y=64, z=-5"
                    assert mock_runner.run_async.called
    
    @pytest.mark.asyncio
    async def test_enhanced_agent_conversation_tracking(self, adk_test_config, mock_bridge_for_adk):
        """Test SimpleEnhancedAgent conversation history tracking"""
        
        agent = SimpleEnhancedAgent(mock_bridge_for_adk, adk_test_config)
        
        # Mock initialization
        with patch.object(agent, 'session_manager') as mock_session_manager:
            mock_session = MagicMock()
            mock_session.id = "test-session"
            mock_session.state = {}
            mock_session_manager.create_session = AsyncMock(return_value=mock_session)
            
            await agent.initialize()
            
            # Verify conversation history was initialized
            assert "conversation_history" in mock_session.state
            assert "performance_metrics" in mock_session.state
            
            # Test conversation tracking
            with patch.object(agent, 'runner') as mock_runner:
                mock_event = MagicMock()
                mock_event.is_final_response.return_value = True
                mock_event.content = MagicMock()
                mock_event.content.parts = [MagicMock(text="I'll help you build")]
                
                async def mock_run_async(*args, **kwargs):
                    yield mock_event
                
                mock_runner.run_async = mock_run_async
                agent.session = mock_session
                
                # Process command
                response = await agent.process_enhanced_command("Build a house", "TestPlayer")
                
                # Check conversation history
                history = mock_session.state.get("conversation_history", [])
                assert len(history) >= 1
                assert any(h.get("command") == "Build a house" for h in history)
    
    @pytest.mark.asyncio 
    async def test_workflow_agent_creation(self, adk_test_config, mock_bridge_for_adk):
        """Test WorkflowAgentFactory creates proper workflow agents"""
        
        factory = WorkflowAgentFactory(mock_bridge_for_adk, adk_test_config)
        
        # Test Sequential Agent creation
        sequential = factory.create_gather_and_build_sequential()
        assert sequential.name == "GatherAndBuild"
        assert len(sequential.sub_agents) == 2
        assert sequential.sub_agents[0].name == "ResourceGatherer"
        assert sequential.sub_agents[1].name == "SimpleBuilder"
        
        # Test Parallel Agent creation
        parallel = factory.create_multi_gatherer_parallel()
        assert parallel.name == "MultiGatherer"
        assert len(parallel.sub_agents) == 2
        assert parallel.sub_agents[0].name == "WoodGatherer"
        assert parallel.sub_agents[1].name == "StoneGatherer"
        
        # Test Loop Agent creation
        loop = factory.create_retry_loop_agent()
        assert loop.name == "RetryMovement"
        assert loop.max_iterations == 3
        assert len(loop.sub_agents) == 1
    
    @pytest.mark.asyncio
    async def test_tool_integration_with_adk(self, adk_test_config, mock_bridge_for_adk):
        """Test that tools work properly with ADK agents"""
        
        from src.tools.mineflayer_tools import move_to, get_inventory, find_blocks
        
        # Test move_to tool
        result = await move_to(10, 65, -5)
        assert result["status"] == "success"
        assert result["position"] == {"x": 10, "y": 65, "z": -5}
        assert "distance_traveled" in result
        
        # Test get_inventory tool
        inv_result = await get_inventory()
        assert inv_result["status"] == "success"
        assert "items" in inv_result
        assert inv_result["summary"]["stone"] == 32
        assert inv_result["summary"]["oak_planks"] == 64
        
        # Test find_blocks tool
        mock_bridge_for_adk.execute_command.return_value = [
            {"x": 5, "y": 63, "z": 0},
            {"x": 6, "y": 63, "z": 0}
        ]
        
        blocks_result = await find_blocks("stone", 64, 10)
        assert blocks_result["status"] == "success"
        assert blocks_result["block_type"] == "stone"
        assert blocks_result["count"] == 2


class TestADKErrorHandling:
    """Test error handling in ADK integration"""
    
    @pytest.mark.asyncio
    async def test_agent_handles_missing_credentials(self, mock_bridge_for_adk):
        """Test agent behavior when Google AI credentials are missing"""
        
        # Create config without API key
        config = AgentConfig()
        
        agent = SimpleMinecraftAgent(config=config)
        
        # Agent should initialize but warn about missing credentials
        with patch.object(agent, 'bridge', mock_bridge_for_adk):
            assert agent.ai_credentials is None
    
    @pytest.mark.asyncio
    async def test_fallback_on_adk_failure(self, adk_test_config, mock_bridge_for_adk):
        """Test fallback behavior when ADK fails"""
        
        agent = SimpleMinecraftAgent(config=adk_test_config)
        
        with patch.object(agent, 'bridge', mock_bridge_for_adk):
            mock_event_processor = MagicMock()
            mock_event_processor.get_world_state.return_value = {}
            
            with patch.object(agent, 'event_processor', mock_event_processor):
                # Simulate ADK failure
                with patch.object(agent, 'runner') as mock_runner:
                    mock_runner.run_async = AsyncMock(side_effect=Exception("ADK Error"))
                    
                    # Test inventory fallback
                    response = await agent.process_command("check inventory")
                    assert "inventory" in response.lower()
                    
                    # Test position fallback
                    response = await agent.process_command("what's my position")
                    assert "position" in response.lower()


@pytest.mark.asyncio
async def test_adk_performance_baseline(adk_test_config, mock_bridge_for_adk):
    """Establish performance baseline for ADK operations"""
    
    import time
    
    agent = SimpleMinecraftAgent(config=adk_test_config)
    
    with patch.object(agent, 'bridge', mock_bridge_for_adk):
        mock_event_processor = MagicMock()
        mock_event_processor.get_world_state.return_value = {}
        
        with patch.object(agent, 'event_processor', mock_event_processor):
            # Mock fast ADK response
            mock_runner = AsyncMock()
            
            mock_event = MagicMock()
            mock_event.is_final_response.return_value = True
            mock_event.content = MagicMock()
            mock_event.content.parts = [MagicMock(text="Response")]
            
            async def mock_run_async(*args, **kwargs):
                await asyncio.sleep(0.05)  # Simulate 50ms latency
                yield mock_event
            
            mock_runner.run_async = mock_run_async
            
            with patch.object(agent, 'runner', mock_runner):
                # Measure command latency
                start = time.time()
                response = await agent.process_command("test command")
                latency = (time.time() - start) * 1000  # Convert to ms
                
                assert response == "Response"
                assert latency < 500  # Should be under 500ms for Phase 1
                
                # Log performance metric
                print(f"ADK command latency: {latency:.2f}ms")