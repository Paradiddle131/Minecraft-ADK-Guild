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

RECIPE KNOWLEDGE BASE:

Basic Materials:
- wooden_planks: 1 log → 4 planks (any wood type)
- sticks: 2 planks → 4 sticks (vertical arrangement)
- torch: 1 coal + 1 stick → 4 torches

Tools (all require sticks):
- wooden_pickaxe: 3 planks (top row) + 2 sticks (middle column)
- stone_pickaxe: 3 cobblestone + 2 sticks
- iron_pickaxe: 3 iron_ingots + 2 sticks
- diamond_pickaxe: 3 diamonds + 2 sticks
- wooden_axe: 3 planks (L-shape) + 2 sticks
- stone_axe: 3 cobblestone (L-shape) + 2 sticks
- wooden_shovel: 1 plank + 2 sticks (vertical)
- stone_shovel: 1 cobblestone + 2 sticks
- wooden_sword: 2 planks + 1 stick (vertical)
- stone_sword: 2 cobblestone + 1 stick

Utility Blocks:
- crafting_table: 4 planks (2x2 square)
- furnace: 8 cobblestone (hollow square)
- chest: 8 planks (hollow square)
- ladder: 7 sticks (H-pattern) → 3 ladders

Building Blocks:
- stone_bricks: 4 stone → 4 stone bricks
- stairs: 6 blocks (stair pattern) → 4 stairs
- slabs: 3 blocks (horizontal) → 6 slabs

RECIPE PATTERNS:
- Tools follow consistent patterns (materials + sticks)
- Many recipes require crafting_table (3x3 grid)
- Some items need furnace smelting (not crafting)
- Check prerequisites before attempting craft

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
    
    def get_recipe_requirements(self, item: str) -> dict:
        """Get crafting requirements for an item
        
        Args:
            item: Item to craft
            
        Returns:
            Dictionary with recipe requirements
        """
        # Define recipe database
        recipes = {
            "wooden_planks": {"log": 1},
            "planks": {"log": 1},
            "sticks": {"planks": 2},
            "stick": {"planks": 2},
            "crafting_table": {"planks": 4},
            "wooden_pickaxe": {"planks": 3, "sticks": 2},
            "stone_pickaxe": {"cobblestone": 3, "sticks": 2},
            "iron_pickaxe": {"iron_ingot": 3, "sticks": 2},
            "diamond_pickaxe": {"diamond": 3, "sticks": 2},
            "wooden_axe": {"planks": 3, "sticks": 2},
            "stone_axe": {"cobblestone": 3, "sticks": 2},
            "wooden_shovel": {"planks": 1, "sticks": 2},
            "stone_shovel": {"cobblestone": 1, "sticks": 2},
            "wooden_sword": {"planks": 2, "sticks": 1},
            "stone_sword": {"cobblestone": 2, "sticks": 1},
            "furnace": {"cobblestone": 8},
            "chest": {"planks": 8},
            "torch": {"coal": 1, "stick": 1},
            "ladder": {"sticks": 7}
        }
        
        # Normalize item name
        item_key = item.lower().replace(" ", "_")
        
        # Try to find exact match
        if item_key in recipes:
            return {
                "item": item,
                "recipe": recipes[item_key],
                "requires_crafting_table": self._needs_crafting_table(item_key)
            }
            
        # Try partial matches
        for recipe_name, ingredients in recipes.items():
            if recipe_name in item_key or item_key in recipe_name:
                return {
                    "item": recipe_name,
                    "recipe": ingredients,
                    "requires_crafting_table": self._needs_crafting_table(recipe_name)
                }
                
        return {
            "item": item,
            "recipe": None,
            "error": f"Unknown recipe for {item}"
        }
        
    def _needs_crafting_table(self, item: str) -> bool:
        """Check if item requires crafting table (3x3 grid)
        
        Args:
            item: Item name
            
        Returns:
            True if needs crafting table
        """
        # Items that can be crafted in 2x2 inventory grid
        inventory_craftable = [
            "wooden_planks", "planks", "sticks", "stick", 
            "crafting_table", "torch"
        ]
        
        return item.lower() not in inventory_craftable
        
    def analyze_crafting_prerequisites(self, item: str, inventory: dict) -> dict:
        """Analyze what's needed to craft an item
        
        Args:
            item: Item to craft
            inventory: Current inventory
            
        Returns:
            Analysis of prerequisites
        """
        requirements = self.get_recipe_requirements(item)
        
        if requirements.get("error"):
            return requirements
            
        recipe = requirements["recipe"]
        missing = {}
        available = {}
        
        # Check each required material
        for material, needed in recipe.items():
            have = inventory.get(material, 0)
            if have < needed:
                missing[material] = needed - have
            available[material] = have
            
        # Check for crafting table requirement
        needs_table = requirements["requires_crafting_table"]
        has_table = inventory.get("crafting_table", 0) > 0
        
        return {
            "item": requirements["item"],
            "can_craft": len(missing) == 0 and (not needs_table or has_table),
            "missing_materials": missing,
            "available_materials": available,
            "requires_crafting_table": needs_table,
            "has_crafting_table": has_table,
            "recipe": recipe
        }