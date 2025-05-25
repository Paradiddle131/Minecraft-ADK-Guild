"""
Tests for Google ADK integration with SimpleMinecraftAgent
"""
import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from google.genai import types

from src.agents.simple_agent import SimpleMinecraftAgent
from src.bridge.bridge_manager import BridgeManager


@pytest.fixture
async def mock_bridge():
    """Create a mock bridge manager"""
    bridge = AsyncMock(spec=BridgeManager)
    bridge.initialize = AsyncMock()
    bridge.close = AsyncMock()
    bridge.get_inventory = AsyncMock(return_value=[
        {"name": "stone", "count": 64},
        {"name": "oak_log", "count": 10}
    ])
    bridge.get_position = AsyncMock(return_value={"x": 100, "y": 65, "z": 100})
    bridge.move_to = AsyncMock()
    bridge.chat = AsyncMock()
    bridge.execute_command = AsyncMock()
    bridge.dig_block = AsyncMock()
    bridge.place_block = AsyncMock()
    
    # Mock event stream
    bridge.event_stream = MagicMock()
    bridge.event_stream.register_handler = MagicMock()
    
    return bridge


@pytest.fixture
async def agent(mock_bridge):
    """Create an agent with mocked bridge"""
    agent = SimpleMinecraftAgent(name="TestAgent", model="gemini-2.0-flash")
    
    # Patch the bridge creation
    with patch('src.agents.simple_agent.BridgeManager', return_value=mock_bridge):
        await agent.initialize()
    
    return agent


@pytest.mark.asyncio
async def test_agent_initialization(agent, mock_bridge):
    """Test that agent initializes properly"""
    assert agent.name == "TestAgent"
    assert agent.model == "gemini-2.0-flash"
    assert agent.agent is not None
    assert agent.session is not None
    assert agent.runner is not None
    
    # Verify bridge was initialized
    mock_bridge.initialize.assert_called_once()


@pytest.mark.asyncio 
async def test_agent_tools_created(agent):
    """Test that Mineflayer tools are properly created"""
    tools = agent.agent.tools
    assert len(tools) > 0
    
    # Check that tools are functions
    tool_names = [tool.__name__ for tool in tools]
    expected_tools = [
        "move_to", "dig_block", "place_block", 
        "find_blocks", "get_inventory", "send_chat", 
        "get_position"
    ]
    
    for expected in expected_tools:
        assert expected in tool_names, f"Tool {expected} not found"


@pytest.mark.asyncio
async def test_process_command_with_mock_runner(agent):
    """Test processing a command with mocked runner"""
    # Mock the runner's run_async method
    mock_event = MagicMock()
    mock_event.content = types.Content(
        parts=[types.Part(text="I am at position x=100, y=65, z=100")],
        role="model"
    )
    
    async def mock_run_async(*args, **kwargs):
        yield mock_event
    
    agent.runner.run_async = mock_run_async
    
    # Process a command
    response = await agent.process_command("What is my position?")
    
    assert response == "I am at position x=100, y=65, z=100"


@pytest.mark.asyncio
async def test_process_command_with_tool_call(agent):
    """Test processing a command that triggers a tool call"""
    # Mock events showing tool execution
    events = [
        MagicMock(
            content=types.Content(
                parts=[types.Part(function_call=types.FunctionCall(
                    name="get_inventory",
                    args={}
                ))],
                role="model"
            )
        ),
        MagicMock(
            content=types.Content(
                parts=[types.Part(text="Your inventory contains: 64 stone blocks and 10 oak logs.")],
                role="model"
            )
        )
    ]
    
    async def mock_run_async(*args, **kwargs):
        for event in events:
            yield event
    
    agent.runner.run_async = mock_run_async
    
    response = await agent.process_command("Check my inventory")
    
    assert "stone" in response or "inventory" in response.lower()


@pytest.mark.asyncio
async def test_process_command_error_handling(agent):
    """Test error handling in command processing"""
    # Mock runner to raise an exception
    async def mock_run_async(*args, **kwargs):
        raise Exception("Connection lost")
        yield  # This won't be reached
    
    agent.runner.run_async = mock_run_async
    
    response = await agent.process_command("Do something")
    
    assert "cannot perform" in response.lower() or "error" in response.lower()


@pytest.mark.asyncio
async def test_session_state_management(agent):
    """Test that session state is properly managed"""
    # Set some state
    agent.session.state["test_key"] = "test_value"
    
    # Mock event processor world state
    agent.event_processor.get_world_state = MagicMock(
        return_value={"world_time": 12000, "weather": "clear"}
    )
    
    # Process a command with a player
    async def mock_run_async(*args, **kwargs):
        # Verify state was updated
        assert agent.session.state["requesting_player"] == "TestPlayer"
        assert agent.session.state["world_time"] == 12000
        
        yield MagicMock(
            content=types.Content(
                parts=[types.Part(text="Command processed")],
                role="model"
            )
        )
    
    agent.runner.run_async = mock_run_async
    
    response = await agent.process_command("test command", player="TestPlayer")
    
    assert response == "Command processed"


@pytest.mark.asyncio
async def test_cleanup(agent, mock_bridge):
    """Test that cleanup properly closes resources"""
    await agent.cleanup()
    
    mock_bridge.close.assert_called_once()


@pytest.mark.asyncio
async def test_api_key_warning():
    """Test that agent warns about missing API key"""
    # Temporarily remove API key
    original_key = os.environ.get("GOOGLE_API_KEY")
    if original_key:
        del os.environ["GOOGLE_API_KEY"]
    
    try:
        with patch('src.agents.simple_agent.config') as mock_config:
            mock_config.validate_api_key.return_value = False
            mock_config.api_key = None
            
            agent = SimpleMinecraftAgent()
            with patch('src.agents.simple_agent.BridgeManager') as mock_bridge_class:
                mock_bridge_instance = AsyncMock()
                mock_bridge_instance.initialize = AsyncMock()
                mock_bridge_instance.event_stream = MagicMock()
                mock_bridge_instance.event_stream.register_handler = MagicMock()
                mock_bridge_class.return_value = mock_bridge_instance
                
                with patch('src.agents.simple_agent.config.jspy_command_timeout', 5000):
                    with patch('src.agents.simple_agent.config.jspy_batch_size', 10):
                        await agent.initialize()
            
            # Check that warning was logged (would need to check logs)
            
    finally:
        # Restore API key
        if original_key:
            os.environ["GOOGLE_API_KEY"] = original_key