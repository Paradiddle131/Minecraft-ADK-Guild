"""
CrafterAgent - Specialized agent for item crafting tasks in Minecraft
Handles recipe management, crafting operations, and item creation
"""

import structlog
from typing import List, Optional, Dict, Any
from google.adk.agents import LlmAgent
from google.adk.sessions import SessionService

from .base_minecraft_agent import BaseMinecraftAgent
from ..bridge.bridge_manager import BridgeManager

logger = structlog.get_logger(__name__)


class CrafterAgent(BaseMinecraftAgent):
    """Agent specialized in crafting items and managing recipes"""
    
    def __init__(
        self,
        name: str = "CrafterAgent",
        model: str = "gemini-2.0-flash",
        tools: Optional[List[Any]] = None,
        session_service: Optional[SessionService] = None,
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
        return """You are the Crafter Agent, specialized in item crafting for Minecraft. Your responsibilities:

1. RECIPE KNOWLEDGE:
   - Understand Minecraft crafting recipes and requirements
   - Identify prerequisite items needed for crafting
   - Plan multi-step crafting sequences when needed

2. CRAFTING PROCESS:
   - Check inventory for required materials using get_inventory
   - Use craft_item with the correct recipe name and count
   - Handle crafting table placement if needed
   - Verify successful crafting completion

3. PREREQUISITE MANAGEMENT:
   - Identify missing materials for recipes
   - Report what's needed if crafting cannot proceed
   - Suggest alternatives when possible

4. STATE UPDATES:
   - Read initial state from session.state['user_request']
   - Update session.state['task.craft.result'] with:
     * status: 'success' or 'error'
     * crafted: number of items crafted
     * item_type: what was crafted
     * missing_materials: list of missing items (if any)
     * error: error message if failed

AVAILABLE TOOLS:
- get_inventory(): Check available materials
- craft_item(recipe, count): Craft specific items
- place_block(x, y, z, block_type, face): Place crafting table if needed
- find_blocks(block_name, max_distance, count): Find crafting tables
- move_to(x, y, z): Navigate to crafting locations

COMMON RECIPES:
- wooden_planks: From any log (1 log → 4 planks)
- sticks: From planks (2 planks → 4 sticks)
- crafting_table: 4 planks in square
- wooden_pickaxe: 3 planks + 2 sticks (T-shape)
- stone_pickaxe: 3 cobblestone + 2 sticks
- wooden_axe: 3 planks + 2 sticks (L-shape)
- furnace: 8 cobblestone in square

CRAFTING STRATEGY:
1. Check inventory for required materials
2. If materials missing, report what's needed
3. If have materials, attempt crafting
4. For complex items, craft prerequisites first
5. Verify success and update state

IMPORTANT:
- You do NOT communicate with users directly
- All communication happens through state updates
- Be precise about material requirements
- Report detailed errors if crafting fails"""
    
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
        
        # Add credentials if available
        if self.ai_credentials:
            agent_config.update(self.ai_credentials)
            
        self.agent = LlmAgent(**agent_config)
        logger.info(f"{self.name} created with {len(self.tools)} crafting tools")
        
        return self.agent