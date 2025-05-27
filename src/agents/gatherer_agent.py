"""
GathererAgent - Specialized agent for resource collection tasks in Minecraft
Handles finding and mining blocks, collecting items, and managing resources
"""

import structlog
from typing import List, Optional, Dict, Any
from google.adk.agents import LlmAgent
from google.adk.sessions import SessionService

from .base_minecraft_agent import BaseMinecraftAgent
from ..bridge.bridge_manager import BridgeManager

logger = structlog.get_logger(__name__)


class GathererAgent(BaseMinecraftAgent):
    """Agent specialized in resource gathering and collection tasks"""
    
    def __init__(
        self,
        name: str = "GathererAgent",
        model: str = "gemini-2.0-flash",
        tools: Optional[List[Any]] = None,
        session_service: Optional[SessionService] = None,
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
        return """You are the Gatherer Agent, specialized in resource collection for Minecraft. Your responsibilities:

1. RESOURCE FINDING:
   - Use find_blocks to locate specific resources
   - Navigate efficiently using move_to with pathfinding
   - Track resource locations in your environment

2. COLLECTION PROCESS:
   - Mine blocks using dig_block at specific coordinates
   - Ensure you're in range before attempting to mine
   - Handle obstacles and navigate around them

3. INVENTORY MANAGEMENT:
   - Check inventory using get_inventory before and after gathering
   - Track what items were collected
   - Report collection results accurately

4. STATE UPDATES:
   - Read initial state from session.state['user_request']
   - Update session.state['task.gather.result'] with:
     * status: 'success' or 'error'
     * gathered: number of items collected
     * item_type: what was gathered
     * error: error message if failed

AVAILABLE TOOLS:
- find_blocks(block_name, max_distance, count): Locate resources
- move_to(x, y, z): Navigate to positions
- dig_block(x, y, z): Mine specific blocks
- get_inventory(): Check current items
- get_position(): Get current location

GATHERING STRATEGY:
1. First, check current inventory to know starting amounts
2. Find the requested blocks within reasonable distance
3. Navigate to each block location
4. Mine the blocks
5. Verify collection in inventory
6. Update state with results

IMPORTANT:
- You do NOT communicate with users directly
- All communication happens through state updates
- Focus on efficiency and successful resource collection
- Handle errors gracefully and report them in state"""
    
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
        
        # Add credentials if available
        if self.ai_credentials:
            agent_config.update(self.ai_credentials)
            
        self.agent = LlmAgent(**agent_config)
        logger.info(f"{self.name} created with {len(self.tools)} gathering tools")
        
        return self.agent