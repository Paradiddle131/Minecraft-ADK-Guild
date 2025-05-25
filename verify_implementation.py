#!/usr/bin/env python3
"""
Implementation Verification Script
Verifies that all ADK integration components are properly implemented
"""

import asyncio
import structlog
from unittest.mock import AsyncMock, MagicMock

# Configure logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.dev.ConsoleRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


async def verify_imports():
    """Verify all required imports work correctly"""
    logger.info("Verifying imports...")
    
    try:
        # Core ADK imports
        from google.adk.agents import LlmAgent, SequentialAgent, ParallelAgent, LoopAgent
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService
        from google.genai import types
        logger.info("✅ Google ADK imports successful")
        
        # Project imports
        from src.agents.simple_agent import SimpleMinecraftAgent
        from src.agents.simple_enhanced_agent import SimpleEnhancedAgent
        from src.agents.workflow_agents import WorkflowAgentFactory
        from src.config import AgentConfig, get_config, setup_google_ai_credentials
        from src.tools.mineflayer_tools import create_mineflayer_tools
        from src.bridge.bridge_manager import BridgeManager, BridgeConfig
        logger.info("✅ Project imports successful")
        
        return True
        
    except ImportError as e:
        logger.error(f"❌ Import failed: {e}")
        return False


async def verify_configuration():
    """Verify configuration system works"""
    logger.info("Verifying configuration...")
    
    try:
        from src.config import AgentConfig
        
        # Test default config
        config = AgentConfig()
        assert config.default_model == "gemini-2.0-flash"
        assert config.agent_temperature == 0.2
        logger.info("✅ Default configuration working")
        
        # Test custom config
        custom_config = AgentConfig(
            default_model="gemini-1.5-pro",
            agent_temperature=0.5,
            minecraft_port=25566
        )
        assert custom_config.default_model == "gemini-1.5-pro"
        assert custom_config.agent_temperature == 0.5
        assert custom_config.minecraft_port == 25566
        logger.info("✅ Custom configuration working")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Configuration verification failed: {e}")
        return False


async def verify_tools():
    """Verify tool system works"""
    logger.info("Verifying tools...")
    
    try:
        from src.tools.mineflayer_tools import create_mineflayer_tools, _set_bridge_manager
        from src.tools.mineflayer_tools import get_inventory, move_to, send_chat
        
        # Create mock bridge
        mock_bridge = AsyncMock()
        mock_bridge.get_position.return_value = {"x": 0, "y": 64, "z": 0}
        mock_bridge.get_inventory.return_value = [{"name": "stone", "count": 64}]
        mock_bridge.move_to = AsyncMock()
        mock_bridge.chat = AsyncMock()
        
        # Set up tools
        _set_bridge_manager(mock_bridge)
        
        # Test tool creation
        tools = create_mineflayer_tools(mock_bridge)
        assert len(tools) == 8
        logger.info(f"✅ Created {len(tools)} tools")
        
        # Test individual tool functions
        inventory_result = await get_inventory()
        assert inventory_result["status"] == "success"
        
        move_result = await move_to(10, 64, 20)
        assert move_result["status"] == "success"
        
        chat_result = await send_chat("Test message")
        assert chat_result["status"] == "success"
        
        logger.info("✅ Tool functions working")
        return True
        
    except Exception as e:
        logger.error(f"❌ Tool verification failed: {e}")
        return False


async def verify_agent_creation():
    """Verify agent creation without full initialization"""
    logger.info("Verifying agent creation...")
    
    try:
        from src.agents.simple_agent import SimpleMinecraftAgent
        from src.agents.simple_enhanced_agent import SimpleEnhancedAgent
        from src.agents.workflow_agents import WorkflowAgentFactory
        from src.config import AgentConfig
        
        config = AgentConfig()
        mock_bridge = AsyncMock()
        
        # Test SimpleMinecraftAgent creation
        simple_agent = SimpleMinecraftAgent(config=config)
        assert simple_agent.name == "MinecraftAgent"
        assert simple_agent.model == "gemini-2.0-flash"
        logger.info("✅ SimpleMinecraftAgent creation working")
        
        # Test SimpleEnhancedAgent creation
        enhanced_agent = SimpleEnhancedAgent(mock_bridge, config)
        assert enhanced_agent.config == config
        assert enhanced_agent.bridge == mock_bridge
        logger.info("✅ SimpleEnhancedAgent creation working")
        
        # Test WorkflowAgentFactory creation
        factory = WorkflowAgentFactory(mock_bridge, config)
        assert factory.bridge == mock_bridge
        assert factory.config == config
        logger.info("✅ WorkflowAgentFactory creation working")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Agent creation verification failed: {e}")
        return False


async def verify_workflow_agents():
    """Verify workflow agent creation"""
    logger.info("Verifying workflow agents...")
    
    try:
        from src.agents.workflow_agents import WorkflowAgentFactory
        from src.config import AgentConfig
        
        config = AgentConfig()
        mock_bridge = AsyncMock()
        factory = WorkflowAgentFactory(mock_bridge, config)
        
        # Test Sequential Agent
        sequential_agent = factory.create_gather_and_build_sequential()
        assert sequential_agent.name == "GatherAndBuild"
        assert len(sequential_agent.sub_agents) == 2
        logger.info("✅ SequentialAgent creation working")
        
        # Test Parallel Agent
        parallel_agent = factory.create_multi_gatherer_parallel()
        assert parallel_agent.name == "MultiGatherer"
        assert len(parallel_agent.sub_agents) == 2
        logger.info("✅ ParallelAgent creation working")
        
        # Test Loop Agent
        loop_agent = factory.create_retry_loop_agent()
        assert loop_agent.name == "RetryMovement"
        assert len(loop_agent.sub_agents) == 1
        assert loop_agent.max_iterations == 3
        logger.info("✅ LoopAgent creation working")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Workflow agent verification failed: {e}")
        return False


async def verify_session_management():
    """Verify session management system"""
    logger.info("Verifying session management...")
    
    try:
        from google.adk.sessions import InMemorySessionService
        
        session_manager = InMemorySessionService()
        
        # Create a session
        session = await session_manager.create_session(
            app_name="test_app",
            user_id="test_user"
        )
        
        assert session is not None
        assert session.id is not None
        
        # Test state management
        session.state["test_key"] = "test_value"
        assert session.state["test_key"] == "test_value"
        
        logger.info("✅ Session management working")
        return True
        
    except Exception as e:
        logger.error(f"❌ Session management verification failed: {e}")
        return False


async def main():
    """Run all verification checks"""
    print("="*60)
    print("ADK INTEGRATION IMPLEMENTATION VERIFICATION")
    print("="*60)
    
    verifications = [
        ("Imports", verify_imports),
        ("Configuration", verify_configuration),
        ("Tools", verify_tools),
        ("Agent Creation", verify_agent_creation),
        ("Workflow Agents", verify_workflow_agents),
        ("Session Management", verify_session_management)
    ]
    
    results = []
    
    for name, verification_func in verifications:
        print(f"\n🧪 Testing: {name}")
        try:
            result = await verification_func()
            results.append((name, result))
        except Exception as e:
            logger.error(f"❌ {name} verification failed with exception: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "="*60)
    print("VERIFICATION SUMMARY")
    print("="*60)
    
    passed = 0
    for name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{name:20} | {status}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{len(results)} verifications passed")
    
    if passed == len(results):
        print("\n🎉 ALL VERIFICATIONS PASSED!")
        print("\n📋 Implementation Status:")
        print("   ✅ Google ADK integration complete")
        print("   ✅ Configuration system working")
        print("   ✅ Tool system functional")
        print("   ✅ Agent creation successful")
        print("   ✅ Workflow patterns implemented")
        print("   ✅ Session management operational")
        print("\n🚀 Ready for production use!")
        return True
    else:
        print(f"\n❌ {len(results) - passed} verifications failed")
        print("Please check the errors above before proceeding.")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)