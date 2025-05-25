"""
Workflow Agents - Demonstrating ADK workflow patterns
"""
import asyncio
from typing import List, Dict, Any

import structlog
from google.adk import Runner
from google.adk.agents import (
    LlmAgent, 
    SequentialAgent, 
    ParallelAgent, 
    LoopAgent,
    BaseAgent
)
from google.adk.sessions import InMemorySessionService
from google.adk.runners import RunConfig
from google.genai import types

from ..bridge.bridge_manager import BridgeManager
from ..tools.mineflayer_tools import create_mineflayer_tools
from ..config import config

logger = structlog.get_logger(__name__)


class SimpleSequentialWorkflow:
    """Demonstrates SequentialAgent pattern for ordered tasks"""
    
    def __init__(self, bridge_manager: BridgeManager):
        self.bridge = bridge_manager
        self.session_service = InMemorySessionService()
        
    def create_agents(self) -> SequentialAgent:
        """Create a sequential workflow for gather-then-build pattern"""
        
        # Step 1: Resource Gatherer
        gatherer = LlmAgent(
            name="resource_gatherer",
            model=config.adk_model,
            instruction="""You are a resource gathering specialist.
            Your task is to:
            1. Find and gather the requested materials
            2. Report what you've collected
            3. Store the materials count in state['gathered_resources']
            
            Use find_blocks to locate resources and dig_block to collect them.
            """,
            tools=create_mineflayer_tools(self.bridge),
            output_key="gathered_resources"
        )
        
        # Step 2: Builder
        builder = LlmAgent(
            name="simple_builder", 
            model=config.adk_model,
            instruction="""You are a construction specialist.
            Check state['gathered_resources'] to see available materials.
            Build a simple structure at the specified location using place_block.
            Report what you've built.
            """,
            tools=create_mineflayer_tools(self.bridge),
            output_key="build_result"
        )
        
        # Create sequential workflow
        return SequentialAgent(
            name="gather_and_build",
            description="Gathers resources then builds a structure",
            agents=[gatherer, builder]
        )


class SimpleParallelWorkflow:
    """Demonstrates ParallelAgent pattern for concurrent tasks"""
    
    def __init__(self, bridge_manager: BridgeManager):
        self.bridge = bridge_manager
        self.session_service = InMemorySessionService()
        
    def create_agents(self) -> ParallelAgent:
        """Create parallel workflow for concurrent resource gathering"""
        
        # Wood Gatherer
        wood_gatherer = LlmAgent(
            name="wood_gatherer",
            model=config.adk_model, 
            instruction="""You specialize in gathering wood.
            Find and collect oak_log blocks within 32 blocks.
            Report how many you collected.
            """,
            tools=create_mineflayer_tools(self.bridge),
            output_key="wood_collected"
        )
        
        # Stone Gatherer  
        stone_gatherer = LlmAgent(
            name="stone_gatherer",
            model=config.adk_model,
            instruction="""You specialize in gathering stone.
            Find and collect stone blocks within 32 blocks.
            Report how many you collected.
            """,
            tools=create_mineflayer_tools(self.bridge),
            output_key="stone_collected"
        )
        
        # Create parallel workflow
        return ParallelAgent(
            name="multi_gatherer",
            description="Gathers multiple resource types concurrently",
            agents=[wood_gatherer, stone_gatherer]
        )


class SimpleLoopWorkflow:
    """Demonstrates LoopAgent pattern for iterative tasks"""
    
    def __init__(self, bridge_manager: BridgeManager):
        self.bridge = bridge_manager
        self.session_service = InMemorySessionService()
        
    def create_agents(self) -> LoopAgent:
        """Create loop workflow for retrying until success"""
        
        # Task executor
        task_agent = LlmAgent(
            name="task_executor",
            model=config.adk_model,
            instruction="""Try to complete the requested task.
            If you encounter an error, report it and we'll retry.
            Set state['task_complete'] = True when successful.
            """,
            tools=create_mineflayer_tools(self.bridge),
            output_key="task_status"
        )
        
        # Completion checker
        def check_completion(state: Dict[str, Any]) -> bool:
            """Check if task is complete"""
            return state.get("task_complete", False)
        
        # Create loop workflow
        return LoopAgent(
            name="retry_until_success",
            description="Retries task until successful completion",
            agent=task_agent,
            max_iterations=3,
            should_continue=lambda state: not check_completion(state)
        )


class WorkflowDemo:
    """Demonstrates all workflow patterns"""
    
    def __init__(self, bridge_manager: BridgeManager):
        self.bridge = bridge_manager
        self.sequential = SimpleSequentialWorkflow(bridge_manager)
        self.parallel = SimpleParallelWorkflow(bridge_manager) 
        self.loop = SimpleLoopWorkflow(bridge_manager)
        self.session_service = InMemorySessionService()
        
    async def demonstrate_sequential(self):
        """Run sequential workflow demo"""
        logger.info("Starting sequential workflow demo")
        
        workflow = self.sequential.create_agents()
        session = await self.session_service.create_session(
            app_name="sequential_demo",
            user_id="demo_user"
        )
        
        runner = Runner(
            app_name="sequential_demo",
            agent=workflow,
            session_service=self.session_service
        )
        
        # Run workflow
        content = types.Content(
            parts=[types.Part(text="Gather 10 wood logs then build a 3x3 platform")],
            role="user"
        )
        
        async for event in runner.run_async(
            session_id=session.id,
            user_id="demo_user", 
            new_message=content,
            run_config=RunConfig()
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        logger.info(f"Sequential: {part.text}")
                        
    async def demonstrate_parallel(self):
        """Run parallel workflow demo"""
        logger.info("Starting parallel workflow demo")
        
        workflow = self.parallel.create_agents()
        session = await self.session_service.create_session(
            app_name="parallel_demo",
            user_id="demo_user"
        )
        
        runner = Runner(
            app_name="parallel_demo",
            agent=workflow,
            session_service=self.session_service
        )
        
        # Run workflow
        content = types.Content(
            parts=[types.Part(text="Gather both wood and stone resources")],
            role="user"
        )
        
        async for event in runner.run_async(
            session_id=session.id,
            user_id="demo_user",
            new_message=content,
            run_config=RunConfig()
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        logger.info(f"Parallel: {part.text}")
                        
    async def demonstrate_loop(self):
        """Run loop workflow demo"""
        logger.info("Starting loop workflow demo")
        
        workflow = self.loop.create_agents()
        session = await self.session_service.create_session(
            app_name="loop_demo",
            user_id="demo_user"
        )
        
        runner = Runner(
            app_name="loop_demo",
            agent=workflow,
            session_service=self.session_service
        )
        
        # Run workflow
        content = types.Content(
            parts=[types.Part(text="Place a torch at coordinates 100, 65, 100")],
            role="user"
        )
        
        async for event in runner.run_async(
            session_id=session.id,
            user_id="demo_user",
            new_message=content,
            run_config=RunConfig()
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        logger.info(f"Loop: {part.text}")
                        
    async def run_all_demos(self):
        """Run all workflow demonstrations"""
        logger.info("Starting workflow demonstrations")
        
        try:
            await self.demonstrate_sequential()
            await asyncio.sleep(2)
            
            await self.demonstrate_parallel()
            await asyncio.sleep(2)
            
            await self.demonstrate_loop()
            
            logger.info("All workflow demonstrations complete")
            
        except Exception as e:
            logger.error(f"Error in workflow demo: {e}", exc_info=True)