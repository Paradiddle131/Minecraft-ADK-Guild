"""
Integration tests for the complete ADK system
"""

import asyncio
import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.simple_agent import SimpleMinecraftAgent
from src.bridge.bridge_manager import BridgeManager, BridgeConfig
from src.config import AgentConfig
from src.tools.mineflayer_tools import create_mineflayer_tools


@pytest.fixture
def integration_config():
    """Configuration for integration tests"""
    return AgentConfig(
        default_model="gemini-2.0-flash",
        agent_temperature=0.1,  # More deterministic for testing
        max_output_tokens=200,   # Smaller for faster tests
        command_timeout_ms=3000
    )


@pytest.fixture
async def integration_bridge():
    """Mock bridge that simulates realistic Minecraft server responses"""
    
    class IntegrationBridge:
        def __init__(self):
            self.bot_position = {"x": 0, "y": 64, "z": 0}
            self.bot_inventory = [
                {"name": "stone", "count": 64},
                {"name": "oak_log", "count": 32},
                {"name": "iron_pickaxe", "count": 1}
            ]
            self.world_blocks = {
                "stone": [{"x": 5, "y": 63, "z": 0}, {"x": 6, "y": 63, "z": 0}],
                "oak_log": [{"x": -10, "y": 70, "z": 5}]
            }
            self.chat_messages = []
            
        async def get_position(self):
            return self.bot_position.copy()
            
        async def get_inventory(self):
            return self.bot_inventory.copy()
            
        async def move_to(self, x, y, z):
            self.bot_position = {"x": x, "y": y, "z": z}
            await asyncio.sleep(0.1)  # Simulate movement time
            
        async def dig_block(self, x, y, z):
            # Simulate block mining
            await asyncio.sleep(0.05)
            # Add block to inventory
            self.bot_inventory.append({"name": "stone", "count": 1})
            
        async def place_block(self, x, y, z, face="top"):
            # Simulate block placement
            await asyncio.sleep(0.05)
            # Remove block from inventory
            for item in self.bot_inventory:
                if item["name"] == "stone" and item["count"] > 0:
                    item["count"] -= 1
                    break
                    
        async def chat(self, message):
            self.chat_messages.append(message)
            
        async def execute_command(self, command, **kwargs):
            if command == "world.findBlocks":
                block_name = kwargs.get("name", "stone")
                return self.world_blocks.get(block_name, [])
            return {}
            
        async def close(self):
            pass
            
        # Mock event stream
        event_stream = MagicMock()
        event_stream.register_handler = MagicMock()
    
    return IntegrationBridge()


class TestEndToEndWorkflow:
    """Test complete end-to-end workflows"""
    
    async def test_complete_agent_lifecycle(self, integration_bridge, integration_config):
        """Test complete agent initialization and cleanup"""
        agent = SimpleMinecraftAgent(config=integration_config)
        
        with patch.object(agent, 'bridge', integration_bridge):
            mock_event_processor = MagicMock()
            mock_event_processor.get_world_state.return_value = {
                "nearby_players": ["TestPlayer"],
                "world_time": 1000
            }
            
            with patch.object(agent, 'event_processor', mock_event_processor):
                # Test initialization
                start_time = time.time()
                await agent.initialize()
                init_time = time.time() - start_time
                
                assert init_time < 2.0, "Initialization should be fast"
                assert agent.agent is not None
                assert agent.session is not None
                
                # Test cleanup
                await agent.cleanup()
    
    async def test_command_processing_pipeline(self, integration_bridge, integration_config):
        """Test the complete command processing pipeline"""
        agent = SimpleMinecraftAgent(config=integration_config)
        
        with patch.object(agent, 'bridge', integration_bridge):
            mock_event_processor = MagicMock()
            mock_event_processor.get_world_state.return_value = {}
            
            with patch.object(agent, 'event_processor', mock_event_processor):
                await agent.initialize()
                
                # Test sequence of commands
                commands = [
                    "What's in my inventory?",
                    "Where am I?", 
                    "Say hello to everyone"
                ]
                
                responses = []
                for command in commands:
                    start_time = time.time()
                    response = await agent.process_command(command, player="TestPlayer")
                    response_time = time.time() - start_time
                    
                    assert isinstance(response, str)
                    assert len(response) > 0
                    assert response_time < 1.0, f"Command '{command}' took too long: {response_time}s"
                    
                    responses.append(response)
                
                # Verify session state was updated
                assert agent.session.state.get("requesting_player") == "TestPlayer"
    
    async def test_tool_integration_workflow(self, integration_bridge, integration_config):
        """Test tool integration in a realistic workflow"""
        # Set up bridge with tools
        from src.tools.mineflayer_tools import _set_bridge_manager
        _set_bridge_manager(integration_bridge)
        
        # Test tool sequence
        from src.tools.mineflayer_tools import get_inventory, move_to, send_chat
        
        # Check inventory
        inventory_result = await get_inventory()
        assert inventory_result["status"] == "success"
        assert len(inventory_result["items"]) > 0
        
        # Move to new location
        move_result = await move_to(10, 64, 10)
        assert move_result["status"] == "success"
        assert integration_bridge.bot_position["x"] == 10
        
        # Send chat message
        chat_result = await send_chat("Integration test message")
        assert chat_result["status"] == "success"
        assert "Integration test message" in integration_bridge.chat_messages
    
    async def test_error_recovery_workflow(self, integration_config):
        """Test error recovery in various failure scenarios"""
        agent = SimpleMinecraftAgent(config=integration_config)
        
        # Test with failing bridge
        failing_bridge = AsyncMock()
        failing_bridge.get_position.side_effect = Exception("Network error")
        failing_bridge.get_inventory.side_effect = Exception("Server down")
        failing_bridge.close = AsyncMock()
        
        with patch.object(agent, 'bridge', failing_bridge):
            mock_event_processor = MagicMock()
            mock_event_processor.get_world_state.return_value = {}
            
            with patch.object(agent, 'event_processor', mock_event_processor):
                await agent.initialize()
                
                # Should handle errors gracefully
                response = await agent.process_command("check inventory")
                assert "server" in response.lower() or "error" in response.lower()
                
                response = await agent.process_command("where am I")
                assert "server" in response.lower() or "error" in response.lower()
                
                # Cleanup should still work
                await agent.cleanup()


class TestPerformance:
    """Performance and load testing"""
    
    async def test_command_latency(self, integration_bridge, integration_config):
        """Test command processing latency"""
        agent = SimpleMinecraftAgent(config=integration_config)
        
        with patch.object(agent, 'bridge', integration_bridge):
            mock_event_processor = MagicMock()
            mock_event_processor.get_world_state.return_value = {}
            
            with patch.object(agent, 'event_processor', mock_event_processor):
                await agent.initialize()
                
                # Measure latency for different command types
                latencies = []
                test_commands = [
                    "check inventory",
                    "get position", 
                    "hello world",
                    "what can you do"
                ]
                
                for command in test_commands:
                    start_time = time.time()
                    await agent.process_command(command)
                    latency = time.time() - start_time
                    latencies.append(latency)
                
                # Performance requirements (adjust based on needs)
                avg_latency = sum(latencies) / len(latencies)
                max_latency = max(latencies)
                
                assert avg_latency < 0.5, f"Average latency too high: {avg_latency}s"
                assert max_latency < 1.0, f"Max latency too high: {max_latency}s"
                
                print(f"Performance metrics:")
                print(f"  Average latency: {avg_latency:.3f}s")
                print(f"  Max latency: {max_latency:.3f}s")
                print(f"  Min latency: {min(latencies):.3f}s")
    
    async def test_concurrent_commands(self, integration_bridge, integration_config):
        """Test handling of concurrent commands"""
        agent = SimpleMinecraftAgent(config=integration_config)
        
        with patch.object(agent, 'bridge', integration_bridge):
            mock_event_processor = MagicMock()
            mock_event_processor.get_world_state.return_value = {}
            
            with patch.object(agent, 'event_processor', mock_event_processor):
                await agent.initialize()
                
                # Send multiple commands concurrently
                commands = [
                    "check inventory",
                    "get position",
                    "say hello",
                    "what time is it"
                ]
                
                start_time = time.time()
                
                # Run commands concurrently
                tasks = [
                    agent.process_command(cmd, player=f"Player{i}")
                    for i, cmd in enumerate(commands)
                ]
                
                responses = await asyncio.gather(*tasks, return_exceptions=True)
                total_time = time.time() - start_time
                
                # Verify all succeeded
                for i, response in enumerate(responses):
                    if isinstance(response, Exception):
                        pytest.fail(f"Command {i} failed: {response}")
                    assert isinstance(response, str)
                    assert len(response) > 0
                
                # Should be faster than sequential execution
                assert total_time < 2.0, f"Concurrent execution too slow: {total_time}s"
                
                print(f"Concurrent execution time: {total_time:.3f}s for {len(commands)} commands")
    
    async def test_memory_usage(self, integration_bridge, integration_config):
        """Test memory usage during operation"""
        import gc
        
        agent = SimpleMinecraftAgent(config=integration_config)
        
        with patch.object(agent, 'bridge', integration_bridge):
            mock_event_processor = MagicMock()
            mock_event_processor.get_world_state.return_value = {}
            
            with patch.object(agent, 'event_processor', mock_event_processor):
                await agent.initialize()
                
                # Force garbage collection
                gc.collect()
                initial_objects = len(gc.get_objects())
                
                # Process many commands
                for i in range(10):
                    await agent.process_command(f"test command {i}")
                
                # Force garbage collection again
                gc.collect()
                final_objects = len(gc.get_objects())
                
                # Memory growth should be reasonable
                growth = final_objects - initial_objects
                assert growth < 1000, f"Too much memory growth: {growth} objects"
                
                print(f"Memory growth: {growth} objects")


class TestSessionStateManagement:
    """Test session state and context management"""
    
    async def test_session_persistence(self, integration_bridge, integration_config):
        """Test session state persistence across commands"""
        agent = SimpleMinecraftAgent(config=integration_config)
        
        with patch.object(agent, 'bridge', integration_bridge):
            mock_event_processor = MagicMock()
            mock_event_processor.get_world_state.return_value = {"world_time": 1000}
            
            with patch.object(agent, 'event_processor', mock_event_processor):
                await agent.initialize()
                
                # Process commands that should update state
                await agent.process_command("hello", player="Alice")
                await agent.process_command("check inventory", player="Bob")
                
                # Verify state contains expected information
                assert agent.session.state.get("requesting_player") == "Bob"
                
                # Process another command
                await agent.process_command("test", player="Charlie")
                assert agent.session.state.get("requesting_player") == "Charlie"
    
    async def test_world_state_updates(self, integration_bridge, integration_config):
        """Test world state updating and context injection"""
        agent = SimpleMinecraftAgent(config=integration_config)
        
        with patch.object(agent, 'bridge', integration_bridge):
            mock_event_processor = MagicMock()
            world_state = {
                "nearby_players": ["Alice", "Bob"],
                "world_time": 2000,
                "weather": "clear"
            }
            mock_event_processor.get_world_state.return_value = world_state
            
            with patch.object(agent, 'event_processor', mock_event_processor):
                await agent.initialize()
                
                await agent.process_command("status check")
                
                # Verify world state was added to session
                for key, value in world_state.items():
                    assert agent.session.state.get(key) == value


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])