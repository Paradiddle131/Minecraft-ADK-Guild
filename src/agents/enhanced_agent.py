"""
Enhanced Minecraft Agent - Demonstrates advanced ADK features
"""
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

import structlog
from google.adk import Runner
from google.adk.agents import LlmAgent
from google.adk.sessions import InMemorySessionService
from google.adk.runners import RunConfig
from google.genai import types

from ..bridge.bridge_manager import BridgeManager
from ..tools.mineflayer_tools import create_mineflayer_tools
from ..config import config

logger = structlog.get_logger(__name__)


class TaskAnalysis(BaseModel):
    """Schema for structured task analysis output"""
    task_type: str = Field(description="Type of task: movement, building, gathering, etc")
    required_tools: List[str] = Field(description="List of tools needed for the task")
    estimated_steps: int = Field(description="Estimated number of steps to complete")
    resources_needed: Dict[str, int] = Field(description="Resources required (name: count)")
    feasibility: str = Field(description="Whether task is feasible: easy, moderate, hard, impossible")


class BuildPlan(BaseModel):
    """Schema for structured building plans"""
    structure_name: str = Field(description="Name of the structure to build")
    dimensions: Dict[str, int] = Field(description="Width, height, depth of structure")
    materials: Dict[str, int] = Field(description="Materials needed (block_type: count)")
    build_steps: List[str] = Field(description="Ordered steps to build the structure")
    
    
class ResourceReport(BaseModel):
    """Schema for resource gathering reports"""
    target_resource: str = Field(description="Resource that was gathered")
    amount_gathered: int = Field(description="Amount successfully gathered")
    locations_mined: List[Dict[str, int]] = Field(description="Coordinates where resources were found")
    time_taken: float = Field(description="Approximate time taken in seconds")
    obstacles: List[str] = Field(description="Any obstacles encountered")


class EnhancedMinecraftAgent:
    """Enhanced agent with structured outputs and advanced features"""
    
    def __init__(self, name: str = "EnhancedAgent", model: str = None):
        self.name = name
        self.model = model or config.adk_model
        self.bridge = None
        self.session_service = InMemorySessionService()
        
    async def initialize(self, bridge_manager: BridgeManager):
        """Initialize the enhanced agent"""
        self.bridge = bridge_manager
        
        # Create different agent configurations
        self.task_analyzer = self._create_task_analyzer()
        self.build_planner = self._create_build_planner()
        self.resource_gatherer = self._create_resource_gatherer()
        self.general_agent = self._create_general_agent()
        
        logger.info(f"Enhanced agent {self.name} initialized")
        
    def _create_task_analyzer(self) -> LlmAgent:
        """Create agent for analyzing tasks"""
        return LlmAgent(
            name="task_analyzer",
            model=self.model,
            instruction="""You are a Minecraft task analysis expert.
            Analyze the given task and provide a structured analysis including:
            - What type of task it is
            - What tools/functions will be needed
            - How many steps it will take
            - What resources are required
            - How feasible the task is
            
            Be realistic about Minecraft game mechanics.""",
            output_schema=TaskAnalysis,
            output_key="task_analysis"
        )
        
    def _create_build_planner(self) -> LlmAgent:
        """Create agent for planning builds"""
        return LlmAgent(
            name="build_planner",
            model=self.model,
            instruction="""You are a Minecraft construction planning expert.
            Create detailed building plans including:
            - Structure name and dimensions
            - Exact materials needed
            - Step-by-step building instructions
            
            Keep structures simple and buildable.""",
            output_schema=BuildPlan,
            output_key="build_plan"
        )
        
    def _create_resource_gatherer(self) -> LlmAgent:
        """Create agent for gathering resources with reporting"""
        return LlmAgent(
            name="resource_gatherer",
            model=self.model,
            instruction="""You are a Minecraft resource gathering specialist.
            When gathering resources:
            1. Use find_blocks to locate the resource
            2. Move to each location and dig_block
            3. Track what you gather and where
            4. Report obstacles like water, lava, or hostile mobs
            
            After gathering, provide a detailed report.""",
            tools=create_mineflayer_tools(self.bridge),
            output_schema=ResourceReport,
            output_key="gathering_report"
        )
        
    def _create_general_agent(self) -> LlmAgent:
        """Create general purpose agent with all tools"""
        return LlmAgent(
            name="general_minecraft_agent",
            model=self.model,
            instruction="""You are an advanced Minecraft assistant with full capabilities.
            
            You can:
            - Move around the world (move_to)
            - Gather resources (find_blocks, dig_block)
            - Build structures (place_block)
            - Check inventory (get_inventory)
            - Communicate (send_chat)
            - Check position (get_position)
            
            Guidelines:
            1. Always acknowledge requests before starting
            2. Break complex tasks into steps
            3. Report progress during long tasks
            4. Handle errors gracefully
            5. Be helpful and informative
            
            State Management:
            - Store important locations in state['locations']
            - Track resources in state['resources']
            - Remember ongoing tasks in state['current_task']
            """,
            tools=create_mineflayer_tools(self.bridge),
            output_key="action_result",
            generate_content_config=types.GenerateContentConfig(
                temperature=0.7,
                max_output_tokens=500
            )
        )
        
    async def analyze_task(self, task_description: str) -> TaskAnalysis:
        """Analyze a task and return structured analysis"""
        session = await self.session_service.create_session(
            app_name="task_analysis",
            user_id="analyzer"
        )
        
        runner = Runner(
            app_name="task_analysis",
            agent=self.task_analyzer,
            session_service=self.session_service
        )
        
        content = types.Content(
            parts=[types.Part(text=task_description)],
            role="user"
        )
        
        analysis = None
        async for event in runner.run_async(
            session_id=session.id,
            user_id="analyzer",
            new_message=content,
            run_config=RunConfig()
        ):
            # The structured output will be in state
            if event.author == "task_analyzer":
                analysis = session.state.get("task_analysis")
                
        return analysis
        
    async def plan_build(self, structure_request: str) -> BuildPlan:
        """Create a building plan"""
        session = await self.session_service.create_session(
            app_name="build_planning", 
            user_id="planner"
        )
        
        runner = Runner(
            app_name="build_planning",
            agent=self.build_planner,
            session_service=self.session_service
        )
        
        content = types.Content(
            parts=[types.Part(text=structure_request)],
            role="user"
        )
        
        plan = None
        async for event in runner.run_async(
            session_id=session.id,
            user_id="planner",
            new_message=content,
            run_config=RunConfig()
        ):
            if event.author == "build_planner":
                plan = session.state.get("build_plan")
                
        return plan
        
    async def execute_task(self, task: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Execute a general task with full capabilities"""
        session = await self.session_service.create_session(
            app_name="minecraft_tasks",
            user_id="player",
            state=context or {}
        )
        
        runner = Runner(
            app_name="minecraft_tasks",
            agent=self.general_agent,
            session_service=self.session_service
        )
        
        content = types.Content(
            parts=[types.Part(text=task)],
            role="user"
        )
        
        response_text = ""
        async for event in runner.run_async(
            session_id=session.id,
            user_id="player",
            new_message=content,
            run_config=RunConfig(max_llm_calls=100)
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        response_text += part.text
                        
        return response_text
        
    async def demonstrate_features(self):
        """Demonstrate enhanced agent features"""
        logger.info("Starting enhanced agent demonstration")
        
        # 1. Task Analysis
        logger.info("=== Task Analysis Demo ===")
        analysis = await self.analyze_task(
            "Build a house with a door and windows near the spawn point"
        )
        if analysis:
            logger.info(f"Task type: {analysis.task_type}")
            logger.info(f"Feasibility: {analysis.feasibility}")
            logger.info(f"Tools needed: {analysis.required_tools}")
            
        # 2. Build Planning
        logger.info("=== Build Planning Demo ===")
        plan = await self.plan_build("Design a simple 5x5 shelter with a roof")
        if plan:
            logger.info(f"Structure: {plan.structure_name}")
            logger.info(f"Materials: {plan.materials}")
            logger.info(f"Steps: {len(plan.build_steps)}")
            
        # 3. General Execution
        logger.info("=== General Execution Demo ===")
        result = await self.execute_task(
            "Check my inventory and tell me what building materials I have"
        )
        logger.info(f"Result: {result}")
        
        logger.info("Enhanced agent demonstration complete")