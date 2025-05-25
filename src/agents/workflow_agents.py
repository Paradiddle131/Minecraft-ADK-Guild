"""
ADK Workflow Agent Demonstrations
Examples of Sequential, Parallel, and Loop agents using Google ADK patterns
"""

import asyncio
from typing import Any, Dict, List

import structlog
from google.adk.agents import LlmAgent, LoopAgent, ParallelAgent, SequentialAgent
from pydantic import BaseModel, Field

from ..config import AgentConfig, get_config, setup_google_ai_credentials
from ..tools.mineflayer_tools import (
    dig_block, find_blocks, get_inventory, move_to, place_block, send_chat
)

logger = structlog.get_logger(__name__)


class WorkflowAgentFactory:
    """Factory for creating workflow agent examples"""
    
    def __init__(self, bridge_manager, config: AgentConfig = None):
        self.bridge = bridge_manager
        self.config = config or get_config()
        
        # Setup Google AI credentials
        try:
            self.ai_credentials = setup_google_ai_credentials(self.config)
            logger.info("Workflow agents: Google AI credentials configured")
        except ValueError as e:
            logger.warning(f"Google AI credentials not configured: {e}")
            self.ai_credentials = None
    
    def _get_agent_config(self) -> Dict[str, Any]:
        """Get common agent configuration"""
        config = {}
        
        if self.ai_credentials:
            config.update(self.ai_credentials)
        
        return config
    
    def create_gather_and_build_sequential(self) -> SequentialAgent:
        """Create a SequentialAgent that gathers resources then builds
        
        Demonstrates: Ordered task execution with state passing
        """
        
        # Step 1: Resource gathering agent
        gatherer = LlmAgent(
            name="ResourceGatherer",
            model=self.config.default_model,
            instruction="""You are a resource gathering specialist.
            
Your task is to find and collect the materials specified in the task.
Use find_blocks to locate resources, move_to to reach them, and dig_block to collect them.
Always report what you found and collected.

Available tools: find_blocks, move_to, dig_block, get_inventory, send_chat""",
            description="Finds and collects specific resources",
            tools=[find_blocks, move_to, dig_block, get_inventory, send_chat],
            output_key="gathered_materials",
            **self._get_agent_config()
        )
        
        # Step 2: Building agent
        builder = LlmAgent(
            name="SimpleBuilder",
            model=self.config.default_model,
            instruction="""You are a construction specialist.
            
Your task is to build structures using the materials gathered by the resource agent.
The previous agent's output in 'gathered_materials' tells you what materials are available.
Use place_block to construct the requested structure.

Available tools: place_block, move_to, get_inventory, send_chat""",
            description="Builds structures using collected materials",
            tools=[place_block, move_to, get_inventory, send_chat],
            output_key="construction_result",
            **self._get_agent_config()
        )
        
        return SequentialAgent(
            name="GatherAndBuild",
            sub_agents=[gatherer, builder]
        )
    
    def create_multi_gatherer_parallel(self) -> ParallelAgent:
        """Create a ParallelAgent that gathers multiple resources concurrently
        
        Demonstrates: Concurrent task execution
        """
        
        # Wood gatherer
        wood_gatherer = LlmAgent(
            name="WoodGatherer",
            model=self.config.default_model,
            instruction="""You are a wood gathering specialist.
            
Find and collect oak logs, birch logs, or any wood materials within 64 blocks.
Report the total amount of wood collected.

Available tools: find_blocks, move_to, dig_block, get_inventory, send_chat""",
            description="Specializes in collecting wood materials",
            tools=[find_blocks, move_to, dig_block, get_inventory, send_chat],
            output_key="wood_collected",
            **self._get_agent_config()
        )
        
        # Stone gatherer
        stone_gatherer = LlmAgent(
            name="StoneGatherer", 
            model=self.config.default_model,
            instruction="""You are a stone gathering specialist.
            
Find and collect stone, cobblestone, or any stone materials within 64 blocks.
Report the total amount of stone collected.

Available tools: find_blocks, move_to, dig_block, get_inventory, send_chat""",
            description="Specializes in collecting stone materials",
            tools=[find_blocks, move_to, dig_block, get_inventory, send_chat],
            output_key="stone_collected",
            **self._get_agent_config()
        )
        
        return ParallelAgent(
            name="MultiGatherer",
            sub_agents=[wood_gatherer, stone_gatherer]
        )
    
    def create_retry_loop_agent(self) -> LoopAgent:
        """Create a LoopAgent that retries movement until successful
        
        Demonstrates: Iterative task execution with success detection
        """
        
        # Movement agent that might fail
        movement_agent = LlmAgent(
            name="MovementRetrier",
            model=self.config.default_model,
            instruction="""You are a movement specialist that attempts to reach specific coordinates.
            
Try to move to the target coordinates provided in the task.
If you encounter obstacles or fail to reach the destination, report the issue clearly.
Success means you reached within 2 blocks of the target coordinates.

Available tools: move_to, get_inventory, send_chat""",
            description="Attempts movement with retry capability",
            tools=[move_to, get_inventory, send_chat],
            output_key="movement_result",
            **self._get_agent_config()
        )
        
        return LoopAgent(
            name="RetryMovement",
            sub_agents=[movement_agent],
            max_iterations=3
        )


async def demonstrate_workflow_patterns(bridge_manager, config: AgentConfig = None):
    """Demonstrate all workflow patterns with simple examples"""
    
    logger.info("Starting workflow pattern demonstrations")
    factory = WorkflowAgentFactory(bridge_manager, config)
    
    # Demonstrate Sequential Agent
    logger.info("=== Sequential Agent Demo ===")
    sequential_agent = factory.create_gather_and_build_sequential()
    logger.info(f"Created SequentialAgent: {sequential_agent.name}")
    logger.info("Sequential agents execute steps in order, passing state between them")
    
    # Demonstrate Parallel Agent 
    logger.info("=== Parallel Agent Demo ===")
    parallel_agent = factory.create_multi_gatherer_parallel()
    logger.info(f"Created ParallelAgent: {parallel_agent.name}")
    logger.info("Parallel agents execute multiple tasks concurrently")
    
    # Demonstrate Loop Agent
    logger.info("=== Loop Agent Demo ===")
    loop_agent = factory.create_retry_loop_agent()
    logger.info(f"Created LoopAgent: {loop_agent.name}")
    logger.info("Loop agents retry tasks until success or max iterations")
    
    return {
        "sequential": sequential_agent,
        "parallel": parallel_agent,
        "loop": loop_agent
    }