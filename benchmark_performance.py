#!/usr/bin/env python3
"""
Performance Benchmark for ADK Integration
Establishes baseline metrics for the Minecraft multi-agent system
"""

import asyncio
import json
import statistics
import time
from typing import Dict, List
from unittest.mock import AsyncMock, MagicMock

import structlog

from src.agents.simple_agent import SimpleMinecraftAgent
from src.agents.simple_enhanced_agent import SimpleEnhancedAgent
from src.agents.workflow_agents import WorkflowAgentFactory
from src.config import AgentConfig
from src.tools.mineflayer_tools import create_mineflayer_tools


class PerformanceBenchmark:
    """Performance benchmark suite for ADK agents"""
    
    def __init__(self):
        self.logger = structlog.get_logger(__name__)
        self.config = AgentConfig(
            agent_temperature=0.1,
            max_output_tokens=200,
            command_timeout_ms=5000
        )
        self.results = {}
    
    def create_mock_bridge(self):
        """Create a realistic mock bridge for benchmarking"""
        mock_bridge = AsyncMock()
        mock_bridge.get_position.return_value = {"x": 0, "y": 64, "z": 0}
        mock_bridge.get_inventory.return_value = [
            {"name": "stone", "count": 64},
            {"name": "oak_log", "count": 32},
            {"name": "iron_pickaxe", "count": 1}
        ]
        mock_bridge.chat = AsyncMock()
        mock_bridge.move_to = AsyncMock()
        mock_bridge.dig_block = AsyncMock()
        mock_bridge.place_block = AsyncMock()
        mock_bridge.execute_command = AsyncMock(return_value=[])
        mock_bridge.close = AsyncMock()
        
        # Mock event stream
        mock_event_stream = MagicMock()
        mock_event_stream.register_handler = MagicMock()
        mock_bridge.event_stream = mock_event_stream
        
        return mock_bridge
    
    async def benchmark_agent_initialization(self) -> Dict[str, float]:
        """Benchmark agent initialization time"""
        self.logger.info("Benchmarking agent initialization")
        
        results = {}
        
        # Test SimpleMinecraftAgent
        times = []
        for i in range(5):
            mock_bridge = self.create_mock_bridge()
            agent = SimpleMinecraftAgent(config=self.config)
            
            start_time = time.time()
            
            # Mock the initialization components
            agent.bridge = mock_bridge
            mock_event_processor = MagicMock()
            mock_event_processor.get_world_state.return_value = {}
            agent.event_processor = mock_event_processor
            
            await agent.initialize()
            
            init_time = time.time() - start_time
            times.append(init_time)
            
            await agent.cleanup()
        
        results["simple_agent_init"] = {
            "mean": statistics.mean(times),
            "median": statistics.median(times),
            "min": min(times),
            "max": max(times),
            "std": statistics.stdev(times) if len(times) > 1 else 0
        }
        
        self.logger.info(f"SimpleAgent init: {results['simple_agent_init']['mean']:.3f}s avg")
        return results
    
    async def benchmark_command_processing(self) -> Dict[str, float]:
        """Benchmark command processing latency"""
        self.logger.info("Benchmarking command processing")
        
        mock_bridge = self.create_mock_bridge()
        agent = SimpleMinecraftAgent(config=self.config)
        
        # Setup agent
        agent.bridge = mock_bridge
        mock_event_processor = MagicMock()
        mock_event_processor.get_world_state.return_value = {}
        agent.event_processor = mock_event_processor
        
        await agent.initialize()
        
        test_commands = [
            "Check my inventory",
            "What's my current position?",
            "Say hello to everyone",
            "Find some stone blocks",
            "Move to coordinates 10, 64, 20"
        ]
        
        results = {}
        
        for command_type, command in enumerate(test_commands):
            times = []
            
            for _ in range(3):  # Run each command multiple times
                start_time = time.time()
                
                try:
                    response = await agent.process_command(command, player="BenchmarkPlayer")
                    processing_time = time.time() - start_time
                    
                    if isinstance(response, str) and len(response) > 0:
                        times.append(processing_time)
                    else:
                        self.logger.warning(f"Invalid response for command: {command}")
                        
                except Exception as e:
                    self.logger.error(f"Command failed: {command}, error: {e}")
                    # Include failed attempts in timing
                    processing_time = time.time() - start_time
                    times.append(processing_time)
            
            if times:
                results[f"command_{command_type}"] = {
                    "command": command,
                    "mean": statistics.mean(times),
                    "median": statistics.median(times),
                    "min": min(times),
                    "max": max(times),
                    "std": statistics.stdev(times) if len(times) > 1 else 0
                }
        
        await agent.cleanup()
        
        # Calculate overall stats
        all_times = []
        for cmd_result in results.values():
            if isinstance(cmd_result, dict) and "mean" in cmd_result:
                all_times.append(cmd_result["mean"])
        
        if all_times:
            results["overall"] = {
                "mean": statistics.mean(all_times),
                "median": statistics.median(all_times),
                "min": min(all_times),
                "max": max(all_times)
            }
            
            self.logger.info(f"Command processing: {results['overall']['mean']:.3f}s avg")
        
        return results
    
    async def benchmark_tool_execution(self) -> Dict[str, float]:
        """Benchmark individual tool execution times"""
        self.logger.info("Benchmarking tool execution")
        
        mock_bridge = self.create_mock_bridge()
        
        # Setup tools
        from src.tools.mineflayer_tools import _set_bridge_manager
        _set_bridge_manager(mock_bridge)
        
        from src.tools.mineflayer_tools import (
            get_inventory, move_to, send_chat, find_blocks, dig_block
        )
        
        tools_to_test = [
            ("get_inventory", lambda: get_inventory()),
            ("move_to", lambda: move_to(10, 64, 20)),
            ("send_chat", lambda: send_chat("Benchmark test message")),
            ("find_blocks", lambda: find_blocks("stone", 32, 10)),
            ("dig_block", lambda: dig_block(5, 63, 0))
        ]
        
        results = {}
        
        for tool_name, tool_func in tools_to_test:
            times = []
            
            for _ in range(5):  # Run each tool multiple times
                start_time = time.time()
                
                try:
                    result = await tool_func()
                    execution_time = time.time() - start_time
                    
                    if isinstance(result, dict) and "status" in result:
                        times.append(execution_time)
                    else:
                        self.logger.warning(f"Invalid result for tool: {tool_name}")
                        
                except Exception as e:
                    self.logger.error(f"Tool failed: {tool_name}, error: {e}")
                    execution_time = time.time() - start_time
                    times.append(execution_time)
            
            if times:
                results[tool_name] = {
                    "mean": statistics.mean(times),
                    "median": statistics.median(times),
                    "min": min(times),
                    "max": max(times),
                    "std": statistics.stdev(times) if len(times) > 1 else 0
                }
        
        return results
    
    async def benchmark_workflow_agents(self) -> Dict[str, float]:
        """Benchmark workflow agent creation time"""
        self.logger.info("Benchmarking workflow agents")
        
        mock_bridge = self.create_mock_bridge()
        
        results = {}
        
        # Test workflow agent creation times
        creation_tests = [
            ("sequential_agent", lambda factory: factory.create_gather_and_build_sequential()),
            ("parallel_agent", lambda factory: factory.create_multi_gatherer_parallel()),
            ("loop_agent", lambda factory: factory.create_retry_loop_agent())
        ]
        
        for agent_type, creation_func in creation_tests:
            times = []
            
            for _ in range(5):
                start_time = time.time()
                
                try:
                    factory = WorkflowAgentFactory(mock_bridge, self.config)
                    agent = creation_func(factory)
                    creation_time = time.time() - start_time
                    
                    if agent is not None:
                        times.append(creation_time)
                    
                except Exception as e:
                    self.logger.error(f"Workflow agent creation failed: {agent_type}, error: {e}")
                    creation_time = time.time() - start_time
                    times.append(creation_time)
            
            if times:
                results[agent_type] = {
                    "mean": statistics.mean(times),
                    "median": statistics.median(times),
                    "min": min(times),
                    "max": max(times),
                    "std": statistics.stdev(times) if len(times) > 1 else 0
                }
        
        return results
    
    async def benchmark_memory_usage(self) -> Dict[str, int]:
        """Benchmark memory usage patterns"""
        self.logger.info("Benchmarking memory usage")
        
        import gc
        import sys
        
        # Get initial memory baseline
        gc.collect()
        initial_objects = len(gc.get_objects())
        
        mock_bridge = self.create_mock_bridge()
        agent = SimpleMinecraftAgent(config=self.config)
        
        # Setup agent
        agent.bridge = mock_bridge
        mock_event_processor = MagicMock()
        mock_event_processor.get_world_state.return_value = {}
        agent.event_processor = mock_event_processor
        
        await agent.initialize()
        
        after_init_objects = len(gc.get_objects())
        
        # Process several commands
        for i in range(10):
            await agent.process_command(f"test command {i}", player="MemoryTest")
        
        after_commands_objects = len(gc.get_objects())
        
        await agent.cleanup()
        gc.collect()
        
        after_cleanup_objects = len(gc.get_objects())
        
        results = {
            "initial_objects": initial_objects,
            "after_init_objects": after_init_objects,
            "after_commands_objects": after_commands_objects,
            "after_cleanup_objects": after_cleanup_objects,
            "init_growth": after_init_objects - initial_objects,
            "command_growth": after_commands_objects - after_init_objects,
            "cleanup_recovery": after_commands_objects - after_cleanup_objects
        }
        
        self.logger.info(f"Memory growth - Init: {results['init_growth']}, Commands: {results['command_growth']}")
        
        return results
    
    async def run_full_benchmark(self) -> Dict:
        """Run complete benchmark suite"""
        self.logger.info("Starting full performance benchmark")
        
        benchmark_start = time.time()
        
        # Run all benchmarks
        self.results["agent_initialization"] = await self.benchmark_agent_initialization()
        self.results["command_processing"] = await self.benchmark_command_processing()
        self.results["tool_execution"] = await self.benchmark_tool_execution()
        self.results["workflow_agents"] = await self.benchmark_workflow_agents()
        self.results["memory_usage"] = await self.benchmark_memory_usage()
        
        total_time = time.time() - benchmark_start
        self.results["benchmark_metadata"] = {
            "total_benchmark_time": total_time,
            "timestamp": time.time(),
            "config": {
                "model": self.config.default_model,
                "temperature": self.config.agent_temperature,
                "max_tokens": self.config.max_output_tokens
            }
        }
        
        self.logger.info(f"Benchmark completed in {total_time:.2f}s")
        return self.results
    
    def generate_report(self) -> str:
        """Generate a human-readable performance report"""
        if not self.results:
            return "No benchmark results available"
        
        report = []
        report.append("=" * 60)
        report.append("MINECRAFT ADK SYSTEM PERFORMANCE BENCHMARK")
        report.append("=" * 60)
        
        # Agent Initialization
        if "agent_initialization" in self.results:
            init_data = self.results["agent_initialization"]["simple_agent_init"]
            report.append(f"\n📊 AGENT INITIALIZATION")
            report.append(f"  Average: {init_data['mean']:.3f}s")
            report.append(f"  Range:   {init_data['min']:.3f}s - {init_data['max']:.3f}s")
        
        # Command Processing
        if "command_processing" in self.results:
            cmd_data = self.results["command_processing"]["overall"]
            report.append(f"\n⚡ COMMAND PROCESSING")
            report.append(f"  Average: {cmd_data['mean']:.3f}s")
            report.append(f"  Range:   {cmd_data['min']:.3f}s - {cmd_data['max']:.3f}s")
            
            # Individual commands
            for key, value in self.results["command_processing"].items():
                if key.startswith("command_") and isinstance(value, dict):
                    report.append(f"    {value['command'][:30]:30} {value['mean']:.3f}s")
        
        # Tool Execution
        if "tool_execution" in self.results:
            report.append(f"\n🔧 TOOL EXECUTION")
            for tool_name, tool_data in self.results["tool_execution"].items():
                report.append(f"  {tool_name:15} {tool_data['mean']:.3f}s")
        
        # Workflow Agents
        if "workflow_agents" in self.results:
            report.append(f"\n🔄 WORKFLOW AGENTS")
            for agent_type, agent_data in self.results["workflow_agents"].items():
                report.append(f"  {agent_type:15} {agent_data['mean']:.3f}s")
        
        # Memory Usage
        if "memory_usage" in self.results:
            mem_data = self.results["memory_usage"]
            report.append(f"\n💾 MEMORY USAGE")
            report.append(f"  Init growth:    {mem_data['init_growth']} objects")
            report.append(f"  Command growth: {mem_data['command_growth']} objects")
            report.append(f"  Cleanup:        {mem_data['cleanup_recovery']} objects recovered")
        
        # Performance Assessment
        report.append(f"\n✅ PERFORMANCE ASSESSMENT")
        
        # Check against targets from project plan
        if "command_processing" in self.results:
            cmd_avg = self.results["command_processing"]["overall"]["mean"]
            if cmd_avg < 0.5:
                report.append(f"  Command latency: EXCELLENT ({cmd_avg:.3f}s < 500ms target)")
            elif cmd_avg < 1.0:
                report.append(f"  Command latency: GOOD ({cmd_avg:.3f}s)")
            else:
                report.append(f"  Command latency: NEEDS IMPROVEMENT ({cmd_avg:.3f}s)")
        
        if "memory_usage" in self.results:
            mem_growth = self.results["memory_usage"]["command_growth"]
            if mem_growth < 100:
                report.append(f"  Memory efficiency: EXCELLENT ({mem_growth} objects)")
            elif mem_growth < 500:
                report.append(f"  Memory efficiency: GOOD ({mem_growth} objects)")
            else:
                report.append(f"  Memory efficiency: MONITOR ({mem_growth} objects)")
        
        report.append("\n" + "=" * 60)
        
        return "\n".join(report)


async def main():
    """Run the performance benchmark"""
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
    
    benchmark = PerformanceBenchmark()
    
    print("Starting Minecraft ADK Performance Benchmark...")
    print("This may take a few minutes...\n")
    
    # Run benchmark
    results = await benchmark.run_full_benchmark()
    
    # Generate and display report
    report = benchmark.generate_report()
    print(report)
    
    # Save detailed results
    with open("performance_baseline.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\nDetailed results saved to: performance_baseline.json")
    
    # Return success if performance meets basic requirements
    if "command_processing" in results:
        avg_latency = results["command_processing"]["overall"]["mean"]
        if avg_latency < 2.0:  # Basic requirement: under 2 seconds
            print("✅ Performance benchmark PASSED")
            return True
        else:
            print("❌ Performance benchmark FAILED - latency too high")
            return False
    
    return True


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)