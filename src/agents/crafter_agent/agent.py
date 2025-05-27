"""
CrafterAgent - Specialized agent for item crafting tasks in Minecraft
Handles recipe management, crafting operations, and item creation
"""

import structlog
from typing import List, Optional, Dict, Any
from google.adk.agents import LlmAgent
from google.adk.sessions import InMemorySessionService

from ..base_minecraft_agent import BaseMinecraftAgent
from ...bridge.bridge_manager import BridgeManager
from .prompt import CRAFTER_INSTRUCTIONS

logger = structlog.get_logger(__name__)


class CrafterAgent(BaseMinecraftAgent):
    """Agent specialized in crafting items and managing recipes"""
    
    def __init__(
        self,
        name: str = "CrafterAgent",
        model: str = "gemini-2.0-flash",
        tools: Optional[List[Any]] = None,
        session_service: Optional[InMemorySessionService] = None,
        bridge_manager: Optional[BridgeManager] = None,
        ai_credentials: Optional[Dict[str, Any]] = None,
        config=None
    ):
        """Initialize the crafter agent
        
        Args:
            name: Agent name for identification
            model: LLM model to use
            tools: List of Mineflayer tools for crafting operations
            session_service: ADK session service for state management
            bridge_manager: Shared BridgeManager instance
            ai_credentials: Google AI credentials
            config: Agent configuration
        """
        # Initialize base class
        super().__init__(name, bridge_manager, config)
        
        self.model = model
        self.tools = tools or []
        self.session_service = session_service
        if ai_credentials:
            self.ai_credentials = ai_credentials
        self.agent = None
        
        logger.info(f"Initializing {self.name} with {len(self.tools)} tools")
        
    def _create_instruction(self) -> str:
        """Create the crafter's instruction prompt
        
        Returns:
            Instruction string for the LLM
        """
        return CRAFTER_INSTRUCTIONS
    
    def create_agent(self) -> LlmAgent:
        """Create the ADK LlmAgent instance
        
        Returns:
            Configured LlmAgent for crafting tasks
        """
        # Configure the crafter agent
        agent_config = {
            "name": self.name,
            "model": self.model,
            "instruction": self._create_instruction(),
            "description": "Specialized agent for Minecraft item crafting",
            "tools": self.tools,
            "output_key": "crafter_response"
        }
        
        self.agent = LlmAgent(**agent_config)
        logger.info(f"{self.name} created with {len(self.tools)} crafting tools")
        
        return self.agent