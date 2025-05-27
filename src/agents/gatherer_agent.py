"""
GathererAgent - Specialized agent for resource collection tasks in Minecraft
Handles finding and mining blocks, collecting items, and managing resources
"""

import structlog
from typing import List, Optional, Dict, Any
from google.adk.agents import LlmAgent
from google.adk.sessions import InMemorySessionService

from .base_minecraft_agent import BaseMinecraftAgent
from ..bridge.bridge_manager import BridgeManager
from .gatherer_agent.prompt import GATHERER_INSTRUCTIONS

logger = structlog.get_logger(__name__)


class GathererAgent(BaseMinecraftAgent):
    """Agent specialized in resource gathering and collection tasks"""
    
    def __init__(
        self,
        name: str = "GathererAgent",
        model: str = "gemini-2.0-flash",
        tools: Optional[List[Any]] = None,
        session_service: Optional[InMemorySessionService] = None,
        bridge_manager: Optional[BridgeManager] = None,
        ai_credentials: Optional[Dict[str, Any]] = None,
        config=None
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
            "output_key": "gatherer_response"
        }
            
        self.agent = LlmAgent(**agent_config)
        logger.info(f"{self.name} created with {len(self.tools)} gathering tools")
        
        return self.agent
    
    def _update_gather_state(self, session_state: dict, status: str, 
                           gathered: int = 0, item_type: str = "", error: str = "") -> None:
        """Update gathering state with results
        
        Args:
            session_state: Session state dictionary
            status: Task status (success/error/partial)
            gathered: Number of items gathered
            item_type: Type of item gathered
            error: Error message if any
        """
        from .state_schema import StateKeys, create_gather_result
        
        # Create result using helper function
        result = create_gather_result(
            status=status,
            gathered=gathered,
            item_type=item_type,
            error=error
        )
        
        # Update state
        session_state[StateKeys.GATHER_RESULT] = result
        
        # Update progress tracking
        if StateKeys.GATHER_PROGRESS in session_state:
            progress = session_state[StateKeys.GATHER_PROGRESS]
            progress["final_count"] = gathered
            progress["completed"] = True
            
        # Log the update
        logger.info(f"GathererAgent state updated: {status}, gathered {gathered} {item_type}")
        
    async def analyze_gathering_task(self, request: str) -> dict:
        """Analyze a gathering request to extract details
        
        Args:
            request: User's gathering request
            
        Returns:
            Dictionary with task details
        """
        # Parse common gathering patterns
        import re
        
        # Extract quantity (e.g., "3 oak logs", "gather 5 stone")
        quantity_match = re.search(r'(\d+)\s+(\w+)', request)
        if quantity_match:
            quantity = int(quantity_match.group(1))
            resource = quantity_match.group(2)
        else:
            # Default to 1 if no quantity specified
            quantity = 1
            # Extract resource name
            words = request.lower().split()
            resource_words = []
            for word in words:
                if word in ['gather', 'collect', 'mine', 'get', 'find']:
                    continue
                resource_words.append(word)
            resource = ' '.join(resource_words).strip()
            
        # Map common names to Minecraft block names
        block_mapping = {
            'logs': 'log',
            'wood': 'log',
            'oak': 'oak_log',
            'birch': 'birch_log',
            'spruce': 'spruce_log',
            'stone': 'stone',
            'cobblestone': 'cobblestone',
            'coal': 'coal_ore',
            'iron': 'iron_ore',
            'diamond': 'diamond_ore',
            'dirt': 'dirt',
            'sand': 'sand',
            'gravel': 'gravel'
        }
        
        # Find best match for block name
        minecraft_block = resource
        for key, value in block_mapping.items():
            if key in resource.lower():
                minecraft_block = value
                break
                
        return {
            "quantity": quantity,
            "resource": resource,
            "minecraft_block": minecraft_block,
            "original_request": request
        }