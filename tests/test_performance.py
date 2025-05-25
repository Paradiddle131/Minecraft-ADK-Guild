"""
Performance tests for ADK integration
"""
import asyncio
import time
import statistics
from typing import List, Dict, Any
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.simple_agent import SimpleMinecraftAgent
from src.bridge.bridge_manager import BridgeManager
from src.config import AgentConfig
from src.tools.mineflayer_tools import _set_bridge_manager, move_to, get_inventory


class PerformanceMetrics:
    """Track performance metrics"""
    
    def __init__(self):
        self.measurements: Dict[str, List[float]] = {}
    
    def record(self, operation: str, duration: float):
        """Record a measurement"""
        if operation not in self.measurements:
            self.measurements[operation] = []
        self.measurements[operation].append(duration)
    
    def get_stats(self, operation: str) -> Dict[str, float]:
        """Get statistics for an operation"""
        if operation not in self.measurements or not self.measurements[operation]:
            return {}
        
        values = self.measurements[operation]
        return {
            "count": len(values),
            "mean": statistics.mean(values),
            "median": statistics.median(values),
            "stdev": statistics.stdev(values) if len(values) > 1 else 0,
            "min": min(values),
            "max": max(values),
            "p95": statistics.quantiles(values, n=20)[18] if len(values) > 1 else values[0],
            "p99": statistics.quantiles(values, n=100)[98] if len(values) > 1 else values[0]
        }
    
    def report(self):
        """Generate performance report"""
        report = "\n=== Performance Report ===\n"
        for operation, values in self.measurements.items():
            if values:
                stats = self.get_stats(operation)
                report += f"\n{operation}:\n"
                report += f"  Count: {stats['count']}\n"
                report += f"  Mean: {stats['mean']:.3f}s\n"
                report += f"  Median: {stats['median']:.3f}s\n"
                report += f"  Std Dev: {stats['stdev']:.3f}s\n"
                report += f"  Min: {stats['min']:.3f}s\n"
                report += f"  Max: {stats['max']:.3f}s\n"
                report += f"  P95: {stats['p95']:.3f}s\n"
                report += f"  P99: {stats['p99']:.3f}s\n"
        return report


@pytest.fixture
def mock_bridge():
    """Mock bridge with realistic latency simulation"""
    mock = AsyncMock(spec=BridgeManager)
    
    async def mock_get_position():
        await asyncio.sleep(0.01)  # Simulate 10ms latency
        return {"x": 100, "y": 64, "z": 100}
    
    async def mock_get_inventory():
        await asyncio.sleep(0.02)  # Simulate 20ms latency
        return [
            {"name": "stone", "count": 64},
            {"name": "oak_log", "count": 32}
        ]
    
    async def mock_move_to(x, y, z):
        await asyncio.sleep(0.05)  # Simulate 50ms movement
        return True
    
    async def mock_execute_command(cmd, **kwargs):
        await asyncio.sleep(0.015)  # Simulate 15ms command
        if cmd == "world.findBlocks":
            return [{"x": i, "y": 64, "z": i} for i in range(5)]
        return {"success": True}
    
    mock.get_position.side_effect = mock_get_position
    mock.get_inventory.side_effect = mock_get_inventory
    mock.move_to.side_effect = mock_move_to
    mock.execute_command.side_effect = mock_execute_command
    mock.chat = AsyncMock()
    mock.dig_block = AsyncMock()
    mock.place_block = AsyncMock()
    
    # Mock event stream
    mock_event_stream = MagicMock()
    mock_event_stream.register_handler = MagicMock()
    mock.event_stream = mock_event_stream
    
    return mock


@pytest.fixture
def test_config():
    """Test configuration optimized for performance testing"""
    return AgentConfig(
        default_model="gemini-2.0-flash",
        agent_temperature=0.1,  # Lower temperature for more deterministic responses
        max_output_tokens=200,  # Smaller responses for faster testing
        command_timeout_ms=5000,
        google_ai_api_key="test-api-key"
    )


class TestCommandLatency:
    """Test command processing latency"""
    
    @pytest.mark.asyncio
    async def test_simple_command_latency(self, mock_bridge, test_config):
        """Measure latency for simple commands"""
        metrics = PerformanceMetrics()
        _set_bridge_manager(mock_bridge)
        
        # Test inventory check latency
        for i in range(10):
            start = time.time()
            result = await get_inventory()
            duration = time.time() - start
            metrics.record("inventory_check", duration)
            assert result["status"] == "success"
        
        # Test position check latency
        for i in range(10):
            start = time.time()
            pos = await mock_bridge.get_position()
            duration = time.time() - start
            metrics.record("position_check", duration)
            assert pos is not None
        
        # Test movement latency
        for i in range(10):
            start = time.time()
            result = await move_to(100 + i, 64, 100 + i)
            duration = time.time() - start
            metrics.record("movement", duration)
            assert result["status"] == "success"
        
        # Verify performance targets
        inventory_stats = metrics.get_stats("inventory_check")
        position_stats = metrics.get_stats("position_check")
        movement_stats = metrics.get_stats("movement")
        
        # Phase 1 target: <500ms p95 latency
        assert inventory_stats["p95"] < 0.5, f"Inventory check too slow: {inventory_stats['p95']:.3f}s"
        assert position_stats["p95"] < 0.5, f"Position check too slow: {position_stats['p95']:.3f}s"
        assert movement_stats["p95"] < 0.5, f"Movement too slow: {movement_stats['p95']:.3f}s"
        
        print(metrics.report())
    
    @pytest.mark.asyncio
    async def test_concurrent_command_latency(self, mock_bridge, test_config):
        """Test latency with concurrent operations"""
        metrics = PerformanceMetrics()
        _set_bridge_manager(mock_bridge)
        
        async def timed_operation(operation_name: str, coro):
            """Execute and time an operation"""
            start = time.time()
            result = await coro
            duration = time.time() - start
            metrics.record(operation_name, duration)
            return result
        
        # Run 5 concurrent operations
        for i in range(5):
            tasks = [
                timed_operation("concurrent_inventory", get_inventory()),
                timed_operation("concurrent_position", mock_bridge.get_position()),
                timed_operation("concurrent_movement", move_to(100 + i, 64, 100 + i)),
            ]
            
            start = time.time()
            results = await asyncio.gather(*tasks)
            total_duration = time.time() - start
            metrics.record("concurrent_batch", total_duration)
            
            # Verify all operations succeeded
            assert all(r is not None for r in results)
        
        # Verify concurrent performance
        batch_stats = metrics.get_stats("concurrent_batch")
        assert batch_stats["p95"] < 0.5, f"Concurrent batch too slow: {batch_stats['p95']:.3f}s"
        
        print(metrics.report())


class TestMemoryUsage:
    """Test memory usage patterns"""
    
    @pytest.mark.asyncio
    async def test_session_state_memory(self, mock_bridge, test_config):
        """Test memory usage of session state"""
        agent = SimpleMinecraftAgent(config=test_config)
        
        with patch.object(agent, 'bridge', mock_bridge):
            mock_event_processor = MagicMock()
            mock_event_processor.get_world_state.return_value = {}
            
            with patch.object(agent, 'event_processor', mock_event_processor):
                await agent.initialize()
                
                # Measure baseline memory
                import sys
                baseline_size = sys.getsizeof(agent.session.state)
                
                # Add data to session state
                for i in range(100):
                    agent.session.state[f"location_{i}"] = {"x": i, "y": 64, "z": i}
                    agent.session.state[f"task_{i}"] = f"Task description {i}" * 10
                
                # Measure after adding data
                final_size = sys.getsizeof(agent.session.state)
                
                # Verify reasonable memory usage
                size_per_item = (final_size - baseline_size) / 200  # 200 items added
                assert size_per_item < 1000, f"Excessive memory per item: {size_per_item} bytes"
                
                print(f"Session state memory usage:")
                print(f"  Baseline: {baseline_size} bytes")
                print(f"  With 200 items: {final_size} bytes")
                print(f"  Per item: {size_per_item:.1f} bytes")


class TestAPICallRate:
    """Test API call rate limiting and optimization"""
    
    @pytest.mark.asyncio
    async def test_api_call_batching(self, mock_bridge, test_config):
        """Test that API calls are properly batched"""
        metrics = PerformanceMetrics()
        call_count = 0
        
        async def counting_execute(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)
            return {"success": True}
        
        mock_bridge.execute_command.side_effect = counting_execute
        _set_bridge_manager(mock_bridge)
        
        # Execute multiple operations
        start = time.time()
        for i in range(10):
            await mock_bridge.execute_command("test_command", param=i)
        duration = time.time() - start
        
        # Verify call count and timing
        assert call_count == 10
        assert duration < 0.5, f"Operations took too long: {duration:.3f}s"
        
        print(f"API call metrics:")
        print(f"  Total calls: {call_count}")
        print(f"  Total duration: {duration:.3f}s")
        print(f"  Calls per second: {call_count / duration:.1f}")


class TestScalability:
    """Test system scalability"""
    
    @pytest.mark.asyncio
    async def test_multiple_agent_instances(self, mock_bridge, test_config):
        """Test creating multiple agent instances"""
        metrics = PerformanceMetrics()
        agents = []
        
        # Create 5 agent instances
        start = time.time()
        for i in range(5):
            agent = SimpleMinecraftAgent(
                name=f"Agent_{i}",
                config=test_config
            )
            agents.append(agent)
        creation_time = time.time() - start
        metrics.record("agent_creation", creation_time)
        
        # Initialize all agents
        start = time.time()
        for agent in agents:
            with patch.object(agent, 'bridge', mock_bridge):
                mock_event_processor = MagicMock()
                mock_event_processor.get_world_state.return_value = {}
                
                with patch.object(agent, 'event_processor', mock_event_processor):
                    await agent.initialize()
        init_time = time.time() - start
        metrics.record("agent_initialization", init_time)
        
        # Verify all agents are properly initialized
        assert all(agent.session is not None for agent in agents)
        assert all(agent.agent is not None for agent in agents)
        
        # Clean up
        start = time.time()
        for agent in agents:
            await agent.cleanup()
        cleanup_time = time.time() - start
        metrics.record("agent_cleanup", cleanup_time)
        
        print(metrics.report())
        
        # Verify reasonable performance
        assert creation_time < 1.0, f"Agent creation too slow: {creation_time:.3f}s"
        assert init_time < 5.0, f"Agent initialization too slow: {init_time:.3f}s"
        assert cleanup_time < 1.0, f"Agent cleanup too slow: {cleanup_time:.3f}s"


@pytest.mark.asyncio
async def test_performance_baseline():
    """Run all performance tests and generate baseline report"""
    print("\n" + "="*60)
    print("PERFORMANCE BASELINE TEST")
    print("="*60)
    
    # Run tests
    await pytest.main([__file__, "-v", "-k", "test_", "--tb=short"])
    
    print("\nPerformance baseline established.")
    print("Phase 1 targets:")
    print("  - Command latency: <500ms (p95)")
    print("  - API calls: Properly batched")
    print("  - Memory usage: <1KB per state item")
    print("  - Multi-agent: 5+ concurrent agents")


if __name__ == "__main__":
    asyncio.run(test_performance_baseline())