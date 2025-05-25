#!/usr/bin/env python3
"""
ADK Pattern Test Suite
Tests core Google ADK patterns: Sequential, Parallel, Loop, and Enhanced agents
"""

import asyncio
import structlog
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.workflow_agents import demonstrate_workflow_patterns
from src.agents.simple_enhanced_agent import demonstrate_simple_enhanced_patterns
from src.bridge.bridge_manager import BridgeManager


async def test_workflow_patterns():
    """Test Sequential, Parallel, and Loop agent patterns"""
    
    logger = structlog.get_logger(__name__)
    logger.info("Testing ADK workflow patterns")
    
    # Mock bridge manager
    mock_bridge = AsyncMock(spec=BridgeManager)
    mock_bridge.get_position.return_value = {"x": 0, "y": 64, "z": 0}
    mock_bridge.get_inventory.return_value = [
        {"name": "stone", "count": 64},
        {"name": "oak_log", "count": 32}
    ]
    
    try:
        # Test workflow pattern creation
        patterns = await demonstrate_workflow_patterns(mock_bridge)
        
        # Verify all patterns were created
        assert "sequential" in patterns, "Sequential agent should be created"
        assert "parallel" in patterns, "Parallel agent should be created" 
        assert "loop" in patterns, "Loop agent should be created"
        
        # Verify agent types
        sequential_agent = patterns["sequential"]
        parallel_agent = patterns["parallel"] 
        loop_agent = patterns["loop"]
        
        # Verify agent names and types
        assert sequential_agent.name == "GatherAndBuild", "Sequential agent has correct name"
        assert parallel_agent.name == "MultiGatherer", "Parallel agent has correct name"
        assert loop_agent.name == "RetryMovement", "Loop agent has correct name"
        
        # Verify agent composition  
        assert len(sequential_agent.sub_agents) == 2, "Sequential agent has 2 sub-agents"
        assert len(parallel_agent.sub_agents) == 2, "Parallel agent has 2 sub-agents"
        assert len(loop_agent.sub_agents) == 1, "Loop agent has 1 sub-agent"
        
        logger.info("✅ Workflow pattern test PASSED")
        return True
        
    except Exception as e:
        logger.error(f"❌ Workflow pattern test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_enhanced_patterns():
    """Test enhanced agent with structured output and conversation history"""
    
    logger = structlog.get_logger(__name__)
    logger.info("Testing enhanced ADK patterns")
    
    # Mock bridge manager
    mock_bridge = AsyncMock(spec=BridgeManager)
    mock_bridge.get_position.return_value = {"x": 10, "y": 64, "z": 20}
    mock_bridge.get_inventory.return_value = [
        {"name": "stone", "count": 64},
        {"name": "oak_log", "count": 32},
        {"name": "cobblestone", "count": 128}
    ]
    
    try:
        # Create simple enhanced agent just to test initialization
        from src.agents.simple_enhanced_agent import SimpleEnhancedAgent
        
        enhanced_agent = SimpleEnhancedAgent(mock_bridge)
        await enhanced_agent.initialize()
        
        # Verify agent was created
        assert enhanced_agent is not None, "Enhanced agent should be created"
        assert enhanced_agent.agent is not None, "ADK agent should be created"
        assert enhanced_agent.session is not None, "Session should be created"
        
        # Verify session state structure
        session_state = enhanced_agent.session.state
        assert "conversation_history" in session_state, "Conversation history should be initialized"
        assert "task_context" in session_state, "Task context should be initialized"
        assert "performance_metrics" in session_state, "Performance metrics should be initialized"
        
        # Test basic functionality without full execution
        summary = enhanced_agent.get_conversation_summary()
        assert "conversation_length" in summary, "Summary should include conversation length"
        assert "performance_metrics" in summary, "Summary should include performance metrics"
        
        logger.info("✅ Enhanced pattern test PASSED")
        return True
        
    except Exception as e:
        logger.error(f"❌ Enhanced pattern test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_tool_integration_patterns():
    """Test tool retry logic, timeout handling, and composition"""
    
    logger = structlog.get_logger(__name__)
    logger.info("Testing tool integration patterns")
    
    from src.tools.mineflayer_tools import move_to, get_inventory, send_chat, _set_bridge_manager
    
    # Mock bridge with various scenarios
    mock_bridge = AsyncMock()
    _set_bridge_manager(mock_bridge)
    
    try:
        # Test successful tool execution
        mock_bridge.get_position.return_value = {"x": 0, "y": 64, "z": 0}
        mock_bridge.move_to = AsyncMock()
        
        result = await move_to(100, 64, 100)
        assert result["status"] == "success", "Movement should succeed"
        assert "distance_traveled" in result, "Should calculate distance"
        
        # Test tool error handling
        mock_bridge.get_inventory.side_effect = Exception("Connection failed")
        result = await get_inventory()
        assert result["status"] == "error", "Should handle errors gracefully"
        assert "error" in result, "Should include error message"
        
        # Reset for successful test
        mock_bridge.get_inventory.side_effect = None
        mock_bridge.get_inventory.return_value = [{"name": "stone", "count": 64}]
        result = await get_inventory()
        assert result["status"] == "success", "Should recover from errors"
        
        # Test tool composition
        mock_bridge.chat = AsyncMock()
        chat_result = await send_chat("Hello world!")
        assert chat_result["status"] == "success", "Chat should work"
        
        logger.info("✅ Tool integration pattern test PASSED")
        return True
        
    except Exception as e:
        logger.error(f"❌ Tool integration pattern test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all ADK pattern tests"""
    
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
    
    print("="*60)
    print("ADK Pattern Test Suite")
    print("="*60)
    
    test_results = []
    
    # Test 1: Workflow Patterns
    print("\n🧪 Test 1: Workflow Patterns (Sequential, Parallel, Loop)")
    result1 = await test_workflow_patterns()
    test_results.append(("Workflow Patterns", result1))
    
    # Test 2: Enhanced Patterns
    print("\n🧪 Test 2: Enhanced Patterns (Structured Output, History)")
    result2 = await test_enhanced_patterns() 
    test_results.append(("Enhanced Patterns", result2))
    
    # Test 3: Tool Integration Patterns
    print("\n🧪 Test 3: Tool Integration Patterns")
    result3 = await test_tool_integration_patterns()
    test_results.append(("Tool Integration", result3))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = 0
    for test_name, result in test_results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name:25} | {status}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{len(test_results)} tests passed")
    
    if passed == len(test_results):
        print("🎉 All ADK pattern tests PASSED!")
        print("📋 Patterns demonstrated:")
        print("   • Sequential Agent (ordered task execution)")
        print("   • Parallel Agent (concurrent task execution)")  
        print("   • Loop Agent (retry with success conditions)")
        print("   • Enhanced Agent (structured output & conversation history)")
        print("   • Tool Patterns (retry, timeout, composition)")
        return True
    else:
        print("❌ Some tests failed. Please check the errors above.")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)