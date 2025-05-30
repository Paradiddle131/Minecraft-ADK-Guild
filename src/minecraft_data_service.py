"""
Minecraft Data Service - Centralized Python service for all Minecraft data lookups
"""
import logging
import sys
import os
from typing import Dict, List, Optional, Any

# Add python-minecraft-data to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(project_root, 'python-minecraft-data'))

import minecraft_data

logger = logging.getLogger(__name__)


class MinecraftDataService:
    """Service for handling all Minecraft data lookups using python-minecraft-data"""
    
    def __init__(self, mc_version: str = "1.21.1"):
        """Initialize the MinecraftDataService with specified Minecraft version
        
        Args:
            mc_version: Minecraft version string (e.g., "1.21.1")
        """
        try:
            # Initialize minecraft_data as shown in example.py
            self.mc_data = minecraft_data(mc_version)
            self.version = mc_version
            logger.info(f"Initialized MinecraftDataService for version {mc_version}")
        except Exception as e:
            logger.error(f"Failed to initialize minecraft-data for version {mc_version}: {e}")
            raise
    
    def get_block_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get block data by name
        
        Args:
            name: Block name (e.g., "stone", "oak_log")
            
        Returns:
            Block data dict or None if not found
        """
        try:
            # blocks_name directly contains the full block data
            return self.mc_data.blocks_name.get(name)
        except Exception as e:
            logger.error(f"Error getting block by name '{name}': {e}")
            return None
    
    def get_block_by_id(self, block_id: int) -> Optional[Dict[str, Any]]:
        """Get block data by ID
        
        Args:
            block_id: Block numeric ID
            
        Returns:
            Block data dict or None if not found
        """
        try:
            # Use blocks_list for ID lookup
            if 0 <= block_id < len(self.mc_data.blocks_list):
                return self.mc_data.blocks_list[block_id]
            return None
        except Exception as e:
            logger.error(f"Error getting block by id {block_id}: {e}")
            return None
    
    def get_item_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get item data by name
        
        Args:
            name: Item name (e.g., "diamond", "stick")
            
        Returns:
            Item data dict or None if not found
        """
        try:
            # items_name directly contains the full item data
            item = self.mc_data.items_name.get(name)
            if item:
                return item
            
            # If not found, try using find_item_or_block method
            result = self.mc_data.find_item_or_block(name)
            if result:
                return result
                
            return None
        except Exception as e:
            logger.error(f"Error getting item by name '{name}': {e}")
            return None
    
    def get_item_by_id(self, item_id: int) -> Optional[Dict[str, Any]]:
        """Get item data by ID
        
        Args:
            item_id: Item numeric ID
            
        Returns:
            Item data dict or None if not found
        """
        try:
            # Use items_list for ID lookup
            if 0 <= item_id < len(self.mc_data.items_list):
                return self.mc_data.items_list[item_id]
            return None
        except Exception as e:
            logger.error(f"Error getting item by id {item_id}: {e}")
            return None
    
    def find_blocks(self, options: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Find blocks matching specified criteria
        
        Args:
            options: Search options dict with filters
            
        Returns:
            List of matching blocks
        """
        try:
            results = []
            
            # Filter by name pattern if provided
            if 'name_pattern' in options:
                pattern = options['name_pattern'].lower()
                for name, block_data in self.mc_data.blocks_name.items():
                    if pattern in name.lower():
                        results.append(block_data)
            
            # Filter by hardness range if provided
            if 'min_hardness' in options or 'max_hardness' in options:
                min_h = options.get('min_hardness', 0)
                max_h = options.get('max_hardness', float('inf'))
                
                # If we already have results from name filter, filter those
                if results:
                    results = [b for b in results 
                              if min_h <= (b.get('hardness', 0)) <= max_h]
                else:
                    # Otherwise search all blocks
                    for block_data in self.mc_data.blocks_name.values():
                        if min_h <= (block_data.get('hardness', 0)) <= max_h:
                            results.append(block_data)
            
            return results
        except Exception as e:
            logger.error(f"Error finding blocks with options {options}: {e}")
            return []
    
    def get_recipes_for_item_id(self, item_id: int) -> List[Dict[str, Any]]:
        """Get all recipes that produce the specified item
        
        Args:
            item_id: Item ID to find recipes for
            
        Returns:
            List of recipe dicts
        """
        try:
            # Recipes are keyed by result item ID as string
            return self.mc_data.recipes.get(str(item_id), [])
        except Exception as e:
            logger.error(f"Error getting recipes for item id {item_id}: {e}")
            return []
    
    def get_recipes_for_item_name(self, item_name: str) -> List[Dict[str, Any]]:
        """Get all recipes that produce the specified item by name
        
        Args:
            item_name: Item name to find recipes for
            
        Returns:
            List of recipe dicts
        """
        item = self.get_item_by_name(item_name)
        if not item:
            return []
        return self.get_recipes_for_item_id(item['id'])
    
    def get_food_points(self, item_name: str) -> int:
        """Get food points for a food item
        
        Args:
            item_name: Name of the food item
            
        Returns:
            Food points value or 0 if not a food item
        """
        try:
            # Check if item is in foods_name
            food_data = self.mc_data.foods_name.get(item_name)
            if food_data:
                return food_data.get('foodPoints', 0)
            
            # Fallback to hardcoded values for common foods
            food_values = {
                'apple': 4,
                'bread': 5,
                'cooked_beef': 8,
                'cooked_chicken': 6,
                'cooked_porkchop': 8,
                'golden_apple': 4,
                'cookie': 2,
                'cake': 14,
                'cooked_mutton': 6,
                'cooked_rabbit': 5,
                'cooked_salmon': 6,
                'cooked_cod': 5,
                'baked_potato': 5,
                'carrot': 3,
                'potato': 1,
                'melon_slice': 2,
                'pumpkin_pie': 8,
                'steak': 8,
                'sweet_berries': 2,
                'glow_berries': 2
            }
            return food_values.get(item_name, 0)
        except Exception as e:
            logger.error(f"Error getting food points for '{item_name}': {e}")
            return 0
    
    def get_saturation(self, item_name: str) -> float:
        """Get saturation value for a food item
        
        Args:
            item_name: Name of the food item
            
        Returns:
            Saturation value or 0.0 if not a food item
        """
        try:
            # Check if item is in foods_name
            food_data = self.mc_data.foods_name.get(item_name)
            if food_data:
                return food_data.get('saturation', 0.0)
            
            # Fallback to hardcoded values
            saturation_values = {
                'apple': 2.4,
                'bread': 6.0,
                'cooked_beef': 12.8,
                'cooked_chicken': 7.2,
                'cooked_porkchop': 12.8,
                'golden_apple': 9.6,
                'cookie': 0.4,
                'cake': 0.4,
                'cooked_mutton': 9.6,
                'cooked_rabbit': 6.0,
                'cooked_salmon': 9.6,
                'cooked_cod': 6.0,
                'baked_potato': 6.0,
                'carrot': 3.6,
                'potato': 0.6,
                'melon_slice': 1.2,
                'pumpkin_pie': 4.8,
                'steak': 12.8,
                'sweet_berries': 0.4,
                'glow_berries': 0.4
            }
            return saturation_values.get(item_name, 0.0)
        except Exception as e:
            logger.error(f"Error getting saturation for '{item_name}': {e}")
            return 0.0
    
    def needs_crafting_table(self, item_name: str) -> bool:
        """Check if an item requires a crafting table to craft
        
        Args:
            item_name: Name of the item to craft
            
        Returns:
            True if crafting table required, False if can craft in inventory
        """
        # Get recipes for this item
        recipes = self.get_recipes_for_item_name(item_name)
        
        if not recipes:
            # No recipe found, assume it needs crafting table if craftable
            return True
            
        # Check if any recipe can fit in 2x2 grid
        for recipe in recipes:
            if 'inShape' in recipe:
                # Shaped recipe - check dimensions
                shape = recipe['inShape']
                if len(shape) <= 2 and all(len(row) <= 2 for row in shape):
                    return False  # Can craft in inventory
            elif 'ingredients' in recipe:
                # Shapeless recipe - check ingredient count
                if len(recipe['ingredients']) <= 4:
                    return False  # Can craft in inventory
        
        # Default to needing crafting table
        return True
    
    def normalize_item_name(self, item_name: str) -> str:
        """Normalize item names to handle common variations
        
        Args:
            item_name: Raw item name from user
            
        Returns:
            Normalized item name that matches minecraft-data
        """
        # Handle plurals
        if item_name == 'sticks':
            return 'stick'
        
        # Handle generic "planks" request
        if item_name == 'planks':
            return 'oak_planks'  # Default to oak
        
        # Handle other common variations
        name_map = {
            'wood': 'oak_log',
            'log': 'oak_log',
            'stone_brick': 'stone_bricks',
            'wooden_planks': 'oak_planks',
            'wood_planks': 'oak_planks'
        }
        
        return name_map.get(item_name, item_name)
    
    def get_material_for_tool(self, tool_name: str) -> Optional[str]:
        """Get the material type for a tool
        
        Args:
            tool_name: Name of the tool (e.g., "diamond_pickaxe")
            
        Returns:
            Material name or None
        """
        if '_' not in tool_name:
            return None
            
        material = tool_name.split('_')[0]
        valid_materials = {'wooden', 'stone', 'iron', 'golden', 'diamond', 'netherite'}
        
        return material if material in valid_materials else None
    
    def get_all_items(self) -> List[Dict[str, Any]]:
        """Get all items in the game
        
        Returns:
            List of all item data dicts
        """
        try:
            return list(self.mc_data.items_name.values())
        except Exception as e:
            logger.error(f"Error getting all items: {e}")
            return []
    
    def get_all_blocks(self) -> List[Dict[str, Any]]:
        """Get all blocks in the game
        
        Returns:
            List of all block data dicts
        """
        try:
            return list(self.mc_data.blocks_name.values())
        except Exception as e:
            logger.error(f"Error getting all blocks: {e}")
            return []