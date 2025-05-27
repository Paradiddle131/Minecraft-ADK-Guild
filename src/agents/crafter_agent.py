"""
CrafterAgent - Specialized agent for item crafting tasks in Minecraft
Handles recipe management, crafting operations, and item creation
"""

import structlog
from typing import List, Optional, Dict, Any
from google.adk.agents import LlmAgent
from google.adk.sessions import InMemorySessionService

from .base_minecraft_agent import BaseMinecraftAgent
from ..bridge.bridge_manager import BridgeManager
from .crafter_agent.prompt import CRAFTER_INSTRUCTIONS

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
    
    def _plan_crafting_steps(self, item: str, inventory: dict) -> list:
        """Plan multi-step crafting sequence
        
        Args:
            item: Final item to craft
            inventory: Current inventory
            
        Returns:
            List of crafting steps in order
        """
        steps = []
        items_to_craft = [item]
        crafted_items = set()
        
        # Work backwards from target item
        while items_to_craft:
            current_item = items_to_craft.pop(0)
            
            # Skip if already planned
            if current_item in crafted_items:
                continue
                
            analysis = self.analyze_crafting_prerequisites(current_item, inventory)
            
            if analysis.get("error"):
                steps.append({
                    "type": "error",
                    "item": current_item,
                    "error": analysis["error"]
                })
                continue
                
            # Check if we can craft directly
            if analysis["can_craft"]:
                steps.append({
                    "type": "craft",
                    "item": current_item,
                    "recipe": analysis["recipe"],
                    "requires_crafting_table": analysis["requires_crafting_table"]
                })
                crafted_items.add(current_item)
                
                # Update virtual inventory
                for material, count in analysis["recipe"].items():
                    inventory[material] = inventory.get(material, 0) - count
                inventory[current_item] = inventory.get(current_item, 0) + 1
            else:
                # Need to craft prerequisites first
                if analysis["missing_materials"]:
                    for material, needed in analysis["missing_materials"].items():
                        # Check if material is craftable
                        if self._is_craftable(material):
                            items_to_craft.insert(0, material)
                        else:
                            steps.append({
                                "type": "gather_required",
                                "item": material,
                                "amount": needed,
                                "for": current_item
                            })
                            
                # Need crafting table
                if analysis["requires_crafting_table"] and not analysis["has_crafting_table"]:
                    if "crafting_table" not in crafted_items:
                        items_to_craft.insert(0, "crafting_table")
                        
                # Re-queue this item for later
                items_to_craft.append(current_item)
                
        return self._optimize_crafting_order(steps)
        
    def _is_craftable(self, item: str) -> bool:
        """Check if an item can be crafted (vs gathered)
        
        Args:
            item: Item name
            
        Returns:
            True if craftable
        """
        craftable_items = [
            "planks", "wooden_planks", "sticks", "stick",
            "crafting_table", "torch", "ladder", "chest",
            "wooden_pickaxe", "stone_pickaxe", "iron_pickaxe",
            "wooden_axe", "stone_axe", "wooden_shovel",
            "stone_shovel", "wooden_sword", "stone_sword",
            "furnace", "stone_bricks"
        ]
        
        return item.lower() in craftable_items
        
    def _optimize_crafting_order(self, steps: list) -> list:
        """Optimize crafting step order
        
        Args:
            steps: List of crafting steps
            
        Returns:
            Optimized step list
        """
        # Separate steps by type
        gather_steps = [s for s in steps if s["type"] == "gather_required"]
        craft_steps = [s for s in steps if s["type"] == "craft"]
        error_steps = [s for s in steps if s["type"] == "error"]
        
        # Order: gather first, then craft (simple items before complex)
        optimized = []
        
        # Add all gathering steps first
        optimized.extend(gather_steps)
        
        # Sort crafting steps by complexity (simple items first)
        craft_priority = {
            "planks": 1, "wooden_planks": 1,
            "sticks": 2, "stick": 2,
            "crafting_table": 3,
            "torch": 4
        }
        
        craft_steps.sort(key=lambda x: craft_priority.get(x["item"], 99))
        optimized.extend(craft_steps)
        
        # Add errors last
        optimized.extend(error_steps)
        
        return optimized