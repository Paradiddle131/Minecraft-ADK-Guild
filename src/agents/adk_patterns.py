"""
ADK Pattern Demonstrations - Core patterns for Phase 1.2
"""
import asyncio
from typing import Dict, Any, List

import structlog
from google.adk.agents import LlmAgent, SequentialAgent, ParallelAgent, LoopAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from ..config import AgentConfig, get_config, setup_google_ai_credentials
from ..tools.mineflayer_tools import create_mineflayer_tools

logger = structlog.get_logger(__name__)


class ADKPatternDemonstrator:
    """Demonstrates core ADK patterns with minimal examples"""
    
    def __init__(self, bridge_manager, config: AgentConfig = None):
        self.bridge = bridge_manager
        self.config = config or get_config()
        self.session_service = InMemorySessionService()
        self.credentials = setup_google_ai_credentials(self.config)
    
    def create_basic_llm_agent(self) -> LlmAgent:
        """Create a basic LlmAgent with structured output support"""
        tools = create_mineflayer_tools(self.bridge)
        
        agent_kwargs = {
            "name": "BasicLlmAgent",
            "model": self.config.default_model,
            "description": "Basic Minecraft agent demonstrating LlmAgent patterns",
            "instruction": """You are a Minecraft assistant. Use tools to help players.
            
            Always structure your responses with:
            1. Understanding of the request
            2. Actions taken
            3. Results achieved
            
            Be concise and helpful.""",
            "tools": tools,
            "output_key": "assistant_response",
            "generate_content_config": types.GenerateContentConfig(
                temperature=self.config.agent_temperature,
                max_output_tokens=self.config.max_output_tokens
            )
        }
        
        if self.credentials:
            agent_kwargs.update(self.credentials)
        
        return LlmAgent(**agent_kwargs)
    
    def create_sequential_demo(self) -> SequentialAgent:
        """Create a simple 2-step sequential agent"""
        
        # Step 1: Analyze request
        analyzer_kwargs = {
            "name": "TaskAnalyzer",
            "model": self.config.default_model,
            "description": "Analyzes task requirements",
            "instruction": """Analyze the given task and determine:
            1. What blocks/items are needed
            2. Where to find them
            3. Potential challenges
            
            Store your analysis in the 'task_analysis' output key.""",
            "output_key": "task_analysis",
            "generate_content_config": types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=200
            )
        }
        
        if self.credentials:
            analyzer_kwargs.update(self.credentials)
        
        analyzer = LlmAgent(**analyzer_kwargs)
        
        # Step 2: Execute based on analysis
        executor_kwargs = {
            "name": "TaskExecutor", 
            "model": self.config.default_model,
            "description": "Executes tasks based on analysis",
            "instruction": """Based on the task analysis in {task_analysis}, execute the required actions.
            
            Use the available tools to complete the task efficiently.""",
            "tools": create_mineflayer_tools(self.bridge),
            "output_key": "execution_result",
            "generate_content_config": types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=300
            )
        }
        
        if self.credentials:
            executor_kwargs.update(self.credentials)
        
        executor = LlmAgent(**executor_kwargs)
        
        return SequentialAgent(
            name="AnalyzeAndExecute",
            description="Analyzes then executes tasks",
            sub_agents=[analyzer, executor]
        )
    
    def create_parallel_demo(self) -> ParallelAgent:
        """Create a simple parallel agent for concurrent operations"""
        
        # Position checker
        position_checker_kwargs = {
            "name": "PositionChecker",
            "model": self.config.default_model,
            "description": "Checks current position",
            "instruction": """Get the bot's current position and store it clearly.""",
            "tools": [self._create_position_tool()],
            "output_key": "position_info",
            "generate_content_config": types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=100
            )
        }
        
        if self.credentials:
            position_checker_kwargs.update(self.credentials)
        
        position_checker = LlmAgent(**position_checker_kwargs)
        
        # Inventory checker
        inventory_checker_kwargs = {
            "name": "InventoryChecker",
            "model": self.config.default_model,
            "description": "Checks current inventory",
            "instruction": """Get the bot's inventory and summarize what's available.""",
            "tools": [self._create_inventory_tool()],
            "output_key": "inventory_info",
            "generate_content_config": types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=200
            )
        }
        
        if self.credentials:
            inventory_checker_kwargs.update(self.credentials)
        
        inventory_checker = LlmAgent(**inventory_checker_kwargs)
        
        return ParallelAgent(
            name="StatusChecker",
            description="Checks position and inventory concurrently",
            sub_agents=[position_checker, inventory_checker]
        )
    
    def create_loop_demo(self) -> LoopAgent:
        """Create a simple loop agent with retry mechanism"""
        
        # Movement attempt agent
        movement_agent_kwargs = {
            "name": "MovementAttempt",
            "model": self.config.default_model,
            "description": "Attempts to move to target position",
            "instruction": """Try to move to the target position stored in {target_position}.
            
            If movement fails, store the error in 'movement_error'.
            If successful, store 'success' in 'movement_status'.""",
            "tools": [self._create_movement_tool()],
            "output_key": "movement_result",
            "generate_content_config": types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=150
            )
        }
        
        if self.credentials:
            movement_agent_kwargs.update(self.credentials)
        
        movement_agent = LlmAgent(**movement_agent_kwargs)
        
        # Success checker
        success_checker_kwargs = {
            "name": "SuccessChecker",
            "model": self.config.default_model,
            "description": "Checks if movement succeeded",
            "instruction": """Check if the movement was successful based on {movement_result}.
            
            Set 'should_continue' to false if successful, true if retry needed.""",
            "output_key": "loop_control",
            "generate_content_config": types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=100
            )
        }
        
        if self.credentials:
            success_checker_kwargs.update(self.credentials)
        
        success_checker = LlmAgent(**success_checker_kwargs)
        
        return LoopAgent(
            name="RetryMovement",
            description="Retries movement up to 3 times",
            sub_agents=[movement_agent, success_checker],
            max_iterations=3,
            loop_condition_key="should_continue"
        )
    
    def _create_position_tool(self):
        """Create a position checking tool"""
        async def get_position() -> Dict[str, Any]:
            """Get the bot's current position."""
            try:
                pos = await self.bridge.get_position()
                if isinstance(pos, dict) and 'error' not in pos:
                    return {
                        "status": "success",
                        "position": pos,
                        "message": f"Currently at x={pos['x']}, y={pos['y']}, z={pos['z']}"
                    }
                else:
                    return {
                        "status": "error",
                        "error": "Not connected to server"
                    }
            except Exception as e:
                return {
                    "status": "error",
                    "error": str(e)
                }
        
        return get_position
    
    def _create_inventory_tool(self):
        """Create an inventory checking tool"""
        async def check_inventory() -> Dict[str, Any]:
            """Check the bot's inventory."""
            try:
                from ..tools.mineflayer_tools import get_inventory, _set_bridge_manager
                _set_bridge_manager(self.bridge)
                return await get_inventory()
            except Exception as e:
                return {
                    "status": "error",
                    "error": str(e)
                }
        
        return check_inventory
    
    def _create_movement_tool(self):
        """Create a movement tool"""
        async def attempt_move(x: int, y: int, z: int) -> Dict[str, Any]:
            """Attempt to move to coordinates."""
            try:
                from ..tools.mineflayer_tools import move_to, _set_bridge_manager
                _set_bridge_manager(self.bridge)
                return await move_to(x, y, z)
            except Exception as e:
                return {
                    "status": "error",
                    "error": str(e)
                }
        
        return attempt_move
    
    async def demonstrate_all_patterns(self):
        """Run demonstrations of all ADK patterns"""
        logger.info("Starting ADK pattern demonstrations")
        
        # Create session for demonstrations
        session = await self.session_service.create_session(
            app_name="adk_demos",
            user_id="demo_user"
        )
        
        # Demo 1: Basic LlmAgent
        logger.info("Demo 1: Basic LlmAgent with output_key")
        basic_agent = self.create_basic_llm_agent()
        runner = Runner(
            agent=basic_agent,
            app_name="adk_demos",
            session_service=self.session_service
        )
        
        user_msg = types.Content(
            role='user',
            parts=[types.Part(text="Check my position and tell me what you see")]
        )
        
        async for event in runner.run_async(
            user_id="demo_user",
            session_id=session.id,
            new_message=user_msg
        ):
            if event.is_final_response():
                logger.info(f"Basic agent response: {session.state.get('assistant_response')}")
        
        await asyncio.sleep(2)
        
        # Demo 2: Sequential Agent
        logger.info("Demo 2: Sequential Agent (Analyze -> Execute)")
        sequential_agent = self.create_sequential_demo()
        runner = Runner(
            agent=sequential_agent,
            app_name="adk_demos",
            session_service=self.session_service
        )
        
        user_msg = types.Content(
            role='user',
            parts=[types.Part(text="I need to gather 10 oak logs")]
        )
        
        async for event in runner.run_async(
            user_id="demo_user",
            session_id=session.id,
            new_message=user_msg
        ):
            if hasattr(event, 'state_delta'):
                logger.info(f"State update: {event.state_delta}")
        
        logger.info(f"Analysis: {session.state.get('task_analysis')}")
        logger.info(f"Execution: {session.state.get('execution_result')}")
        
        await asyncio.sleep(2)
        
        # Demo 3: Parallel Agent
        logger.info("Demo 3: Parallel Agent (Position + Inventory)")
        parallel_agent = self.create_parallel_demo()
        runner = Runner(
            agent=parallel_agent,
            app_name="adk_demos",
            session_service=self.session_service  
        )
        
        user_msg = types.Content(
            role='user',
            parts=[types.Part(text="Check my status")]
        )
        
        async for event in runner.run_async(
            user_id="demo_user",
            session_id=session.id,
            new_message=user_msg
        ):
            pass
        
        logger.info(f"Position: {session.state.get('position_info')}")
        logger.info(f"Inventory: {session.state.get('inventory_info')}")
        
        await asyncio.sleep(2)
        
        # Demo 4: Loop Agent
        logger.info("Demo 4: Loop Agent (Retry Movement)")
        loop_agent = self.create_loop_demo()
        runner = Runner(
            agent=loop_agent,
            app_name="adk_demos",
            session_service=self.session_service
        )
        
        # Set target position
        session.state["target_position"] = {"x": 100, "y": 65, "z": 100}
        await self.session_service.update_session(session)
        
        user_msg = types.Content(
            role='user',
            parts=[types.Part(text="Move to the target position")]
        )
        
        async for event in runner.run_async(
            user_id="demo_user",
            session_id=session.id,
            new_message=user_msg
        ):
            if hasattr(event, 'state_delta'):
                logger.info(f"Loop state: {event.state_delta}")
        
        logger.info("ADK pattern demonstrations complete")