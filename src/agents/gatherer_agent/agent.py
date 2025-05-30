"""
GathererAgent - Specialized agent for resource collection tasks in Minecraft
Handles finding and mining blocks, collecting items, and managing resources
"""

from typing import List, Optional, Dict, Any
from google.adk.agents import LlmAgent
from google.adk.sessions import InMemorySessionService

from ..base_minecraft_agent import BaseMinecraftAgent
from ..callbacks import (
    log_agent_thoughts_callback, 
    log_tool_execution_callback, 
    log_tool_call_callback,
    log_before_agent_callback,
    log_after_agent_callback
)
from ...bridge.bridge_manager import BridgeManager
from ...logging_config import get_logger
from .prompt import GATHERER_INSTRUCTIONS

logger = get_logger(__name__)


class GathererAgent(BaseMinecraftAgent):
    """Agent specialized in resource gathering and collection tasks"""
    
    def __init__(
        self,
        name: str = "GathererAgent",
        model: Optional[str] = None,
        tools: Optional[List[Any]] = None,
        session_service: Optional[InMemorySessionService] = None,
        bridge_manager: Optional[BridgeManager] = None,
        ai_credentials: Optional[Dict[str, Any]] = None,
        config=None,
        mc_data_service=None,
        bot_controller=None
    ):
        """Initialize the gatherer agent
        
        Args:
            name: Agent name for identification
            model: LLM model to use
            tools: List of Mineflayer tools for gathering operations
            session_service: ADK session service for state management
            bridge_manager: Shared BridgeManager instance
            ai_credentials: Google AI credentials
            config: Agent configuration
            mc_data_service: Optional shared MinecraftDataService instance
            bot_controller: Optional shared BotController instance
        """
        # Initialize base class with optional shared services
        super().__init__(name, bridge_manager, config, mc_data_service, bot_controller)
        
        self.model = model or (config.default_model if config else "gemini-2.0-flash")
        self.tools = tools or []
        self.session_service = session_service
        if ai_credentials:
            self.ai_credentials = ai_credentials
        self.agent = None
        
        logger.info(f"Initializing {self.name} with {len(self.tools)} tools")
        
    def _create_instruction(self) -> str:
        """Create the gatherer's instruction prompt
        
        Returns:
            Instruction string for the LLM
        """
        return GATHERER_INSTRUCTIONS
    
    def create_agent(self) -> LlmAgent:
        """Create the ADK LlmAgent instance
        
        Returns:
            Configured LlmAgent for gathering tasks
        """
        # Configure the gatherer agent
        agent_config = {
            "name": self.name,
            "model": self.model,
            "instruction": self._create_instruction(),
            "description": "Specialized agent for Minecraft resource gathering",
            "tools": self.tools,
            "output_key": "gatherer_response",
            "before_agent_callback": log_before_agent_callback,
            "after_agent_callback": log_after_agent_callback,
            "after_model_callback": log_agent_thoughts_callback,
            "before_tool_callback": log_tool_call_callback,
            "after_tool_callback": log_tool_execution_callback
        }
            
        self.agent = LlmAgent(**agent_config)
        logger.info(f"{self.name} created with {len(self.tools)} gathering tools")
        
        return self.agent