"""
CoordinatorAgent - Main interface for user communication and task delegation
Implements ADK multi-agent patterns for orchestrating GathererAgent and CrafterAgent
"""

import structlog
from typing import List, Optional, Dict, Any
from google.adk.agents import LlmAgent
from google.adk.sessions import SessionService

from .base_minecraft_agent import BaseMinecraftAgent
from ..bridge.bridge_manager import BridgeManager

logger = structlog.get_logger(__name__)


class CoordinatorAgent(BaseMinecraftAgent):
    """Main coordinator agent that handles user interaction and delegates to sub-agents"""
    
    def __init__(
        self,
        name: str = "CoordinatorAgent",
        model: str = "gemini-2.0-flash",
        sub_agents: Optional[List[Any]] = None,
        session_service: Optional[SessionService] = None,
        bridge_manager: Optional[BridgeManager] = None,
        ai_credentials: Optional[Dict[str, Any]] = None,
        config=None
    ):
        """Initialize the coordinator agent
        
        Args:
            name: Agent name for identification
            model: LLM model to use
            sub_agents: List of sub-agents (GathererAgent, CrafterAgent)
            session_service: ADK session service for state management
            bridge_manager: Shared BridgeManager instance
            ai_credentials: Google AI credentials
            config: Agent configuration
        """
        # Initialize base class
        super().__init__(name, bridge_manager, config)
        
        self.model = model
        self.sub_agents = sub_agents or []
        self.session_service = session_service
        if ai_credentials:
            self.ai_credentials = ai_credentials
        self.agent = None
        
        logger.info(f"Initializing {self.name} with {len(self.sub_agents)} sub-agents")
        
    def _create_instruction(self) -> str:
        """Create the coordinator's instruction prompt
        
        Returns:
            Instruction string for the LLM
        """
        return """You are the Coordinator Agent for a Minecraft bot system. Your role is to:

1. Analyze user requests and understand the intent
2. Delegate tasks to the appropriate sub-agent:
   - GathererAgent: For resource collection tasks (finding and mining blocks, collecting items)
   - CrafterAgent: For item crafting tasks (creating tools, blocks, or other items)
3. Monitor task progress through shared session state
4. Synthesize results and respond to the user

DELEGATION PROCESS:
- When you identify a gathering task, use transfer_to_agent('GathererAgent')
- When you identify a crafting task, use transfer_to_agent('CrafterAgent')
- The sub-agent will update session.state with results
- After delegation, check the task results in state and provide a user-friendly response

SESSION STATE KEYS:
- user_request: The original user request
- minecraft.inventory: Current inventory state
- minecraft.position: Current bot position
- task.gather.result: Results from GathererAgent
- task.craft.result: Results from CrafterAgent
- current_task: Active task being processed
- task_status: Status of current task

TASK ANALYSIS:
- "gather", "collect", "mine", "find" keywords → GathererAgent
- "craft", "make", "create", "build" keywords → CrafterAgent
- "check inventory", "what do I have" → Direct inventory check (no delegation)
- Complex requests may require multiple delegations

RESPONSE GUIDELINES:
- Always acknowledge the user's request
- Explain what you're delegating and why
- Report results clearly after delegation
- If a task fails, explain why and suggest alternatives
- Provide helpful context about the Minecraft world state

IMPORTANT:
- You are the ONLY agent that communicates with the user
- Sub-agents work silently and communicate only through state
- Always read task results from state after delegation
- Maintain a helpful, informative tone

Current sub-agents available: {sub_agent_names}
"""
    
    def create_agent(self) -> LlmAgent:
        """Create the ADK LlmAgent instance
        
        Returns:
            Configured LlmAgent for coordination
        """
        # Get sub-agent names for the instruction
        sub_agent_names = [agent.name for agent in self.sub_agents]
        instruction = self._create_instruction().format(
            sub_agent_names=", ".join(sub_agent_names)
        )
        
        # Configure the coordinator agent with transfer settings
        agent_config = {
            "name": self.name,
            "model": self.model,
            "instruction": instruction,
            "description": "Main coordinator for Minecraft multi-agent system",
            "sub_agents": self.sub_agents,
            "output_key": "coordinator_response",
            # Enable agent transfer capabilities
            "enable_transfers": True,
            "transfer_mode": "SINGLE"  # Only one transfer per turn
        }
        
        # Add credentials if available
        if self.ai_credentials:
            agent_config.update(self.ai_credentials)
            
        self.agent = LlmAgent(**agent_config)
        logger.info(f"{self.name} created with sub-agents: {sub_agent_names}")
        
        return self.agent