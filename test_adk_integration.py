#!/usr/bin/env python3
"""
Google ADK Integration Test Suite
Tests the Google ADK agent integration without requiring a Minecraft server
"""

import asyncio
import structlog
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.simple_agent import SimpleMinecraftAgent
from src.bridge.bridge_manager import BridgeManager, BridgeConfig


async def test_adk_integration():
    """Test the real ADK integration with mocked bridge"""
    
    # Configure logging
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    logger = structlog.get_logger(__name__)
    logger.info("Starting Google ADK Integration Test")
    
    # Create agent
    agent = SimpleMinecraftAgent(name="TestAgent", model="gemini-2.0-flash")
    
    # Mock the bridge to avoid needing a Minecraft server
    mock_bridge = AsyncMock(spec=BridgeManager)
    mock_bridge.get_position.return_value = {"x": 0, "y": 64, "z": 0}
    mock_bridge.get_inventory.return_value = [
        {"name": "stone", "count": 64},
        {"name": "oak_log", "count": 32}
    ]
    mock_bridge.chat = AsyncMock()
    mock_bridge.move_to = AsyncMock()
    mock_bridge.dig_block = AsyncMock()
    mock_bridge.place_block = AsyncMock()
    mock_bridge.execute_command = AsyncMock()
    
    # Mock event stream and processor
    mock_event_stream = MagicMock()
    mock_event_stream.register_handler = MagicMock()
    mock_bridge.event_stream = mock_event_stream
    
    mock_event_processor = MagicMock()
    mock_event_processor.get_world_state.return_value = {
        "nearby_players": ["TestPlayer"],
        "world_time": 1000
    }
    
    # Patch the bridge initialization
    with patch.object(agent, 'bridge', mock_bridge), \
         patch.object(agent, 'event_processor', mock_event_processor):
        
        try:
            # Initialize agent (this will create the real ADK agent)
            await agent.initialize()
            logger.info("✅ Agent initialization successful")
            
            # Verify agent components are created
            assert agent.agent is not None, "ADK Agent should be created"
            assert agent.runner is not None, "ADK Runner should be created"
            assert agent.session is not None, "Session should be created"
            logger.info("✅ All ADK components created successfully")
            
            # Test simple command processing
            logger.info("Testing command processing...")
            
            # This should now use real ADK execution
            response = await agent.process_command("Hello, can you help me?", player="TestPlayer")
            logger.info(f"Agent response: {response}")
            
            # Verify response is not empty
            assert response is not None, "Response should not be None"
            assert len(response.strip()) > 0, "Response should not be empty"
            logger.info("✅ Command processing successful")
            
            # Test inventory query
            logger.info("Testing inventory query...")
            inventory_response = await agent.process_command("Check my inventory", player="TestPlayer")
            logger.info(f"Inventory response: {inventory_response}")
            logger.info("✅ Inventory query successful")
            
            logger.info("🎉 Google ADK Integration Test PASSED!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Test failed: {e}")
            import traceback
            traceback.print_exc()
            return False
            
        finally:
            await agent.cleanup()


async def test_tool_integration():
    """Test that tools are properly integrated with ADK"""
    
    logger = structlog.get_logger(__name__)
    logger.info("Testing tool integration...")
    
    from src.tools.mineflayer_tools import create_mineflayer_tools
    
    # Mock bridge manager
    mock_bridge = AsyncMock()
    mock_bridge.get_position.return_value = {"x": 10, "y": 64, "z": 20}
    mock_bridge.get_inventory.return_value = [{"name": "stone", "count": 64}]
    
    # Create tools
    tools = create_mineflayer_tools(mock_bridge)
    
    # Verify tools are created
    assert len(tools) == 8, f"Expected 8 tools, got {len(tools)}"
    logger.info(f"✅ Created {len(tools)} tools successfully")
    
    # Test individual tool functions
    from src.tools.mineflayer_tools import get_inventory, move_to, send_chat
    
    # Test inventory tool
    inventory_result = await get_inventory()
    assert inventory_result["status"] == "success", "Inventory tool should succeed"
    logger.info("✅ Inventory tool working")
    
    # Test movement tool
    mock_bridge.move_to = AsyncMock()
    move_result = await move_to(100, 64, 100)
    assert move_result["status"] == "success", "Movement tool should succeed"
    logger.info("✅ Movement tool working")
    
    # Test chat tool
    mock_bridge.chat = AsyncMock()
    chat_result = await send_chat("Hello world!")
    assert chat_result["status"] == "success", "Chat tool should succeed"
    logger.info("✅ Chat tool working")
    
    logger.info("🎉 Tool Integration Test PASSED!")
    return True


async def main():
    """Run all ADK integration tests"""
    print("="*60)
    print("Google ADK Integration Test Suite")
    print("="*60)
    
    test_results = []
    
    # Test 1: Basic ADK Integration
    print("\n🧪 Test 1: ADK Integration")
    result1 = await test_adk_integration()
    test_results.append(("ADK Integration", result1))
    
    # Test 2: Tool Integration
    print("\n🧪 Test 2: Tool Integration")
    result2 = await test_tool_integration()
    test_results.append(("Tool Integration", result2))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = 0
    for test_name, result in test_results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name:20} | {status}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{len(test_results)} tests passed")
    
    if passed == len(test_results):
        print("🎉 All ADK integration tests PASSED!")
        return True
    else:
        print("❌ Some tests failed. Please check the errors above.")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)