"""
CoordinatorAgent - Main interface for user communication and task delegation
Implements ADK multi-agent patterns for orchestrating GathererAgent and CrafterAgent
"""

from typing import List, Optional, Dict, Any
from google.adk.agents import LlmAgent
from google.adk.sessions import InMemorySessionService

from ..base_minecraft_agent import BaseMinecraftAgent
from ..callbacks import (
    log_agent_thoughts_callback, 
    log_before_agent_callback, 
    log_after_agent_callback,
    log_tool_call_callback,
    log_tool_execution_callback
)
from ...bridge.bridge_manager import BridgeManager
from ...logging_config import get_logger
from .prompt import COORDINATOR_INSTRUCTIONS

logger = get_logger(__name__)


class CoordinatorAgent(BaseMinecraftAgent):
    """Main coordinator agent that handles user interaction and delegates to sub-agents"""
    
    def __init__(
        self,
        name: str = "CoordinatorAgent",
        model: str = "gemini-2.0-flash",
        sub_agents: Optional[List[Any]] = None,
        session_service: Optional[InMemorySessionService] = None,
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
        return COORDINATOR_INSTRUCTIONS
    
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
            "before_agent_callback": log_before_agent_callback,
            "after_agent_callback": log_after_agent_callback,
            "after_model_callback": log_agent_thoughts_callback,
            "before_tool_callback": log_tool_call_callback,
            "after_tool_callback": log_tool_execution_callback
        }
           
        self.agent = LlmAgent(**agent_config)
        logger.info(f"{self.name} created with sub-agents: {sub_agent_names}")
        
        return self.agent