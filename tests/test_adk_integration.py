"""
Integration tests for ADK components and patterns
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from google.genai import types

from src.agents.simple_agent import SimpleMinecraftAgent
from src.agents.adk_patterns import ADKPatternDemonstrator
from src.bridge.bridge_manager import BridgeManager
from src.config import AgentConfig, setup_google_ai_credentials
from src.tools.mineflayer_tools import (
    move_to, dig_block, place_block, find_blocks,
    get_inventory, send_chat, _set_bridge_manager
)


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
    """Test configuration with mock credentials"""
    return AgentConfig(
        default_model="gemini-2.0-flash",
        agent_temperature=0.2,
        max_output_tokens=500,
        command_timeout_ms=5000,
        google_ai_api_key="test-api-key"
    )


@pytest.fixture
def mock_runner_response():
    """Mock runner response for ADK testing"""
    class MockEvent:
        def __init__(self, is_final=False, content=None, state_delta=None, tool_calls=None):
            self._is_final = is_final
            self.content = content
            self.state_delta = state_delta
            self.tool_calls = tool_calls or []
            self.type = "response" if is_final else "tool_call"
        
        def is_final_response(self):
            return self._is_final
    
    return MockEvent


class TestADKIntegration:
    """Test real ADK integration components"""
    
    @pytest.mark.asyncio
    async def test_agent_initialization_with_adk(self, mock_bridge, test_config):
        """Test that agent properly initializes with ADK components"""
        agent = SimpleMinecraftAgent(config=test_config)
        
        with patch.object(agent, 'bridge', mock_bridge):
            mock_event_processor = MagicMock()
            mock_event_processor.get_world_state.return_value = {}
            
            with patch.object(agent, 'event_processor', mock_event_processor):
                await agent.initialize()
                
                # Verify ADK components
                assert agent.agent is not None
                assert agent.agent.name == "MinecraftAgent"
                assert agent.agent.model == "gemini-2.0-flash"
                assert agent.agent.output_key == "agent_response"
                assert len(agent.agent.tools) > 0
                
                assert agent.runner is not None
                assert agent.session is not None
                assert agent.session_manager is not None
    
    @pytest.mark.asyncio
    async def test_process_command_with_adk(self, mock_bridge, test_config, mock_runner_response):
        """Test command processing through ADK runner"""
        agent = SimpleMinecraftAgent(config=test_config)
        
        with patch.object(agent, 'bridge', mock_bridge):
            mock_event_processor = MagicMock()
            mock_event_processor.get_world_state.return_value = {
                "nearby_players": ["TestPlayer"],
                "loaded_chunks": 25
            }
            
            with patch.object(agent, 'event_processor', mock_event_processor):
                await agent.initialize()
                
                # Mock runner response
                mock_events = [
                    mock_runner_response(
                        is_final=False,
                        tool_calls=[MagicMock(function=MagicMock(name="get_inventory", arguments={}))]
                    ),
                    mock_runner_response(
                        is_final=True,
                        content=types.Content(
                            role='assistant',
                            parts=[types.Part(text="I checked your inventory.")]
                        )
                    )
                ]
                
                with patch.object(agent.runner, 'run_async', return_value=asyncio.create_task(self._async_generator(mock_events)).__await__()):
                    response = await agent.process_command("check my inventory", "TestPlayer")
                    
                    assert "inventory" in response.lower()
                    assert agent.session.state["requesting_player"] == "TestPlayer"
                    assert "nearby_players" in agent.session.state
    
    @pytest.mark.asyncio
    async def test_session_state_management(self, mock_bridge, test_config):
        """Test session state updates and persistence"""
        agent = SimpleMinecraftAgent(config=test_config)
        
        with patch.object(agent, 'bridge', mock_bridge):
            mock_event_processor = MagicMock()
            mock_event_processor.get_world_state.return_value = {}
            
            with patch.object(agent, 'event_processor', mock_event_processor):
                await agent.initialize()
                
                # Test initial state
                assert isinstance(agent.session.state, dict)
                
                # Update state
                agent.session.state["test_key"] = "test_value"
                agent.session.state["current_task"] = "mining"
                
                # Verify state persists
                await agent.session_manager.update_session(agent.session)
                retrieved_session = await agent.session_manager.get_session(
                    agent.session.app_name,
                    agent.session.user_id,
                    agent.session.id
                )
                
                assert retrieved_session.state["test_key"] == "test_value"
                assert retrieved_session.state["current_task"] == "mining"
    
    async def _async_generator(self, items):
        """Helper to create async generator from list"""
        for item in items:
            yield item


class TestMineflayerTools:
    """Test Mineflayer tool functions with ADK compliance"""
    
    @pytest.mark.asyncio
    async def test_move_to_tool(self, mock_bridge):
        """Test move_to tool function"""
        _set_bridge_manager(mock_bridge)
        
        # Test successful movement
        result = await move_to(100, 65, 100)
        
        assert result["status"] == "success"
        assert result["position"] == {"x": 100, "y": 65, "z": 100}
        assert "distance_traveled" in result
        assert "message" in result
        
        mock_bridge.move_to.assert_called_once_with(100, 65, 100)
    
    @pytest.mark.asyncio
    async def test_move_to_validation(self, mock_bridge):
        """Test move_to coordinate validation"""
        _set_bridge_manager(mock_bridge)
        
        # Test invalid coordinates
        result = await move_to(50000, 65, 50000)
        
        assert result["status"] == "error"
        assert "out of world bounds" in result["error"]
        
        # Verify movement was not attempted
        mock_bridge.move_to.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_get_inventory_tool(self, mock_bridge):
        """Test get_inventory tool function"""
        _set_bridge_manager(mock_bridge)
        
        result = await get_inventory()
        
        assert result["status"] == "success"
        assert result["total_items"] == 96  # 64 + 32
        assert result["summary"]["stone"] == 64
        assert result["summary"]["oak_log"] == 32
        assert "message" in result
    
    @pytest.mark.asyncio
    async def test_dig_block_tool(self, mock_bridge):
        """Test dig_block tool function"""
        _set_bridge_manager(mock_bridge)
        
        # Mock block info
        mock_bridge.execute_command.return_value = {"name": "stone"}
        
        result = await dig_block(10, 64, 10)
        
        assert result["status"] == "success"
        assert result["block"] == "stone"
        assert result["position"] == {"x": 10, "y": 64, "z": 10}
        assert "message" in result
        
        mock_bridge.dig_block.assert_called_once_with(10, 64, 10)
    
    @pytest.mark.asyncio
    async def test_dig_block_validation(self, mock_bridge):
        """Test dig_block prevents digging air and bedrock"""
        _set_bridge_manager(mock_bridge)
        
        # Test digging air
        mock_bridge.execute_command.return_value = {"name": "air"}
        result = await dig_block(10, 64, 10)
        
        assert result["status"] == "error"
        assert "already air" in result["error"]
        
        # Test digging bedrock
        mock_bridge.execute_command.return_value = {"name": "bedrock"}
        result = await dig_block(10, 0, 10)
        
        assert result["status"] == "error"
        assert "unbreakable" in result["error"]
    
    @pytest.mark.asyncio
    async def test_place_block_tool(self, mock_bridge):
        """Test place_block tool function"""
        _set_bridge_manager(mock_bridge)
        
        result = await place_block(10, 64, 10, "stone", "top")
        
        assert result["status"] == "success"
        assert result["block"] == "stone"
        assert result["face"] == "top"
        assert "message" in result
        
        mock_bridge.execute_command.assert_called_with(
            "inventory.equip", item="stone", destination="hand"
        )
        mock_bridge.place_block.assert_called_once_with(10, 64, 10, "top")
    
    @pytest.mark.asyncio
    async def test_place_block_validation(self, mock_bridge):
        """Test place_block validation"""
        _set_bridge_manager(mock_bridge)
        
        # Test invalid face
        result = await place_block(10, 64, 10, "stone", "diagonal")
        
        assert result["status"] == "error"
        assert "Invalid face" in result["error"]
        
        # Test no block in inventory
        mock_bridge.get_inventory.return_value = []
        result = await place_block(10, 64, 10, "diamond_block", "top")
        
        assert result["status"] == "error"
        assert "No diamond_block in inventory" in result["error"]
    
    @pytest.mark.asyncio
    async def test_find_blocks_tool(self, mock_bridge):
        """Test find_blocks tool function"""
        _set_bridge_manager(mock_bridge)
        
        mock_bridge.execute_command.return_value = [
            {"x": 10, "y": 64, "z": 10},
            {"x": 15, "y": 64, "z": 15},
            {"x": 20, "y": 65, "z": 20}
        ]
        
        result = await find_blocks("oak_log", 32, 10)
        
        assert result["status"] == "success"
        assert result["block_type"] == "oak_log"
        assert result["count"] == 3
        assert len(result["positions"]) == 3
        assert "message" in result
    
    @pytest.mark.asyncio
    async def test_send_chat_tool(self, mock_bridge):
        """Test send_chat tool function"""
        _set_bridge_manager(mock_bridge)
        
        result = await send_chat("Hello, world!")
        
        assert result["status"] == "success"
        assert result["message"] == "Hello, world!"
        assert result["length"] == 13
        
        mock_bridge.chat.assert_called_once_with("Hello, world!")
    
    @pytest.mark.asyncio
    async def test_send_chat_validation(self, mock_bridge):
        """Test send_chat validation"""
        _set_bridge_manager(mock_bridge)
        
        # Test empty message
        result = await send_chat("")
        assert result["status"] == "error"
        assert "empty message" in result["error"]
        
        # Test long message
        long_msg = "x" * 300
        result = await send_chat(long_msg)
        assert result["status"] == "error"
        assert "too long" in result["error"]


class TestADKPatterns:
    """Test ADK pattern demonstrations"""
    
    @pytest.mark.asyncio
    async def test_pattern_demonstrator_initialization(self, mock_bridge, test_config):
        """Test ADK pattern demonstrator initialization"""
        demonstrator = ADKPatternDemonstrator(mock_bridge, test_config)
        
        assert demonstrator.bridge == mock_bridge
        assert demonstrator.config == test_config
        assert demonstrator.session_service is not None
        assert demonstrator.credentials is not None
    
    @pytest.mark.asyncio
    async def test_basic_llm_agent_creation(self, mock_bridge, test_config):
        """Test basic LlmAgent creation"""
        demonstrator = ADKPatternDemonstrator(mock_bridge, test_config)
        
        agent = demonstrator.create_basic_llm_agent()
        
        assert agent.name == "BasicLlmAgent"
        assert agent.model == "gemini-2.0-flash"
        assert agent.output_key == "assistant_response"
        assert len(agent.tools) > 0
        assert "structure your responses" in agent.instruction
    
    @pytest.mark.asyncio
    async def test_sequential_agent_creation(self, mock_bridge, test_config):
        """Test SequentialAgent creation"""
        demonstrator = ADKPatternDemonstrator(mock_bridge, test_config)
        
        sequential = demonstrator.create_sequential_demo()
        
        assert sequential.name == "AnalyzeAndExecute"
        assert len(sequential.sub_agents) == 2
        assert sequential.sub_agents[0].name == "TaskAnalyzer"
        assert sequential.sub_agents[1].name == "TaskExecutor"
        
        # Verify analyzer has no tools
        assert len(sequential.sub_agents[0].tools) == 0
        # Verify executor has tools
        assert len(sequential.sub_agents[1].tools) > 0
    
    @pytest.mark.asyncio
    async def test_parallel_agent_creation(self, mock_bridge, test_config):
        """Test ParallelAgent creation"""
        demonstrator = ADKPatternDemonstrator(mock_bridge, test_config)
        
        parallel = demonstrator.create_parallel_demo()
        
        assert parallel.name == "StatusChecker"
        assert len(parallel.sub_agents) == 2
        assert parallel.sub_agents[0].name == "PositionChecker"
        assert parallel.sub_agents[1].name == "InventoryChecker"
        
        # Both should have exactly one tool each
        assert len(parallel.sub_agents[0].tools) == 1
        assert len(parallel.sub_agents[1].tools) == 1
    
    @pytest.mark.asyncio
    async def test_loop_agent_creation(self, mock_bridge, test_config):
        """Test LoopAgent creation"""
        demonstrator = ADKPatternDemonstrator(mock_bridge, test_config)
        
        loop = demonstrator.create_loop_demo()
        
        assert loop.name == "RetryMovement"
        assert loop.max_iterations == 3
        assert loop.loop_condition_key == "should_continue"
        assert len(loop.sub_agents) == 2
        assert loop.sub_agents[0].name == "MovementAttempt"
        assert loop.sub_agents[1].name == "SuccessChecker"


class TestErrorHandling:
    """Test error handling in ADK integration"""
    
    @pytest.mark.asyncio
    async def test_credential_error_handling(self, mock_bridge):
        """Test handling of missing credentials"""
        config = AgentConfig()  # No API key
        
        with pytest.raises(ValueError, match="No Google AI credentials"):
            setup_google_ai_credentials(config)
    
    @pytest.mark.asyncio
    async def test_bridge_error_handling(self, mock_bridge, test_config):
        """Test handling of bridge errors in tools"""
        _set_bridge_manager(mock_bridge)
        
        # Mock bridge error
        mock_bridge.get_position.side_effect = Exception("Connection lost")
        
        result = await move_to(100, 65, 100)
        
        assert result["status"] == "error"
        assert "Connection lost" in result["error"]
    
    @pytest.mark.asyncio
    async def test_server_disconnected_handling(self, mock_bridge, test_config):
        """Test handling when server is not connected"""
        _set_bridge_manager(mock_bridge)
        
        # Mock disconnected state
        mock_bridge.get_inventory.return_value = {"error": "Not connected to server"}
        
        result = await get_inventory()
        
        assert result["status"] == "error"
        assert "not connected to server" in result["error"].lower()


class TestStatePersistence:
    """Test session state persistence patterns"""
    
    @pytest.mark.asyncio
    async def test_state_updates_during_execution(self, mock_bridge, test_config):
        """Test that state updates persist during agent execution"""
        agent = SimpleMinecraftAgent(config=test_config)
        
        with patch.object(agent, 'bridge', mock_bridge):
            mock_event_processor = MagicMock()
            mock_event_processor.get_world_state.return_value = {}
            
            with patch.object(agent, 'event_processor', mock_event_processor):
                await agent.initialize()
                
                # Set initial state
                agent.session.state["task_count"] = 0
                agent.session.state["visited_locations"] = []
                
                # Simulate state update
                agent.session.state["task_count"] += 1
                agent.session.state["visited_locations"].append({"x": 100, "y": 65, "z": 100})
                
                # Save state
                await agent.session_manager.update_session(agent.session)
                
                # Retrieve and verify
                session = await agent.session_manager.get_session(
                    agent.session.app_name,
                    agent.session.user_id,
                    agent.session.id
                )
                
                assert session.state["task_count"] == 1
                assert len(session.state["visited_locations"]) == 1
                assert session.state["visited_locations"][0]["x"] == 100


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])