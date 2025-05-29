"""
BotController - Python class that encapsulates all bot actions
Provides a Python-centric interface for controlling the Minecraft bot
"""
import logging
from typing import Dict, List, Optional, Any, Union
from .bridge.bridge_manager import BridgeManager

logger = logging.getLogger(__name__)


class BotController:
    """Python controller for all Minecraft bot actions via BridgeManager"""
    
    def __init__(self, bridge_manager_instance: BridgeManager):
        """Initialize the BotController with a BridgeManager instance
        
        Args:
            bridge_manager_instance: An initialized BridgeManager instance
        """
        self.bridge_manager_instance = bridge_manager_instance
        logger.info("Initialized BotController")
    
    async def chat(self, message: str) -> Dict[str, Any]:
        """Send a chat message
        
        Args:
            message: Message to send in chat
            
        Returns:
            Dict with send status
        """
        try:
            result = await self.bridge_manager_instance.chat(message)
            return {"status": "success", "message": message}
        except Exception as e:
            logger.error(f"Chat failed: {e}")
            return {"status": "error", "error": str(e)}
    
    async def move_to(self, x: int, y: int, z: int) -> Dict[str, Any]:
        """Move bot to specific coordinates
        
        Args:
            x: Target X coordinate
            y: Target Y coordinate
            z: Target Z coordinate
            
        Returns:
            Dict with movement result
        """
        try:
            result = await self.bridge_manager_instance.move_to(x, y, z)
            return {
                "status": "success",
                "target": {"x": x, "y": y, "z": z},
                "result": result
            }
        except Exception as e:
            logger.error(f"Movement failed: {e}")
            return {"status": "error", "error": str(e)}
    
    async def look_at(self, x: int, y: int, z: int) -> Dict[str, Any]:
        """Make bot look at specific coordinates
        
        Args:
            x: X coordinate to look at
            y: Y coordinate to look at
            z: Z coordinate to look at
            
        Returns:
            Dict with result
        """
        try:
            result = await self.bridge_manager_instance.execute_command(
                "js_lookAt", x=x, y=y, z=z
            )
            return {"status": "success", "looking_at": {"x": x, "y": y, "z": z}}
        except Exception as e:
            logger.error(f"Look at failed: {e}")
            return {"status": "error", "error": str(e)}
    
    async def start_digging(self, block_position: List[int]) -> Dict[str, Any]:
        """Start digging a block
        
        Args:
            block_position: [x, y, z] position of block to dig
            
        Returns:
            Dict with dig result
        """
        try:
            x, y, z = block_position
            result = await self.bridge_manager_instance.dig_block(x, y, z)
            return {
                "status": "success",
                "position": {"x": x, "y": y, "z": z},
                "result": result
            }
        except Exception as e:
            logger.error(f"Start digging failed: {e}")
            return {"status": "error", "error": str(e)}
    
    async def stop_digging(self) -> Dict[str, Any]:
        """Stop current digging action
        
        Returns:
            Dict with result
        """
        try:
            result = await self.bridge_manager_instance.execute_command("js_stopDigging")
            return {"status": "success", "stopped": True}
        except Exception as e:
            logger.error(f"Stop digging failed: {e}")
            return {"status": "error", "error": str(e)}
    
    async def place_block(self, reference_block_position: List[int], face_vector: List[int]) -> Dict[str, Any]:
        """Place a block
        
        Args:
            reference_block_position: [x, y, z] position of reference block
            face_vector: [x, y, z] face vector for placement direction
            
        Returns:
            Dict with placement result
        """
        try:
            x, y, z = reference_block_position
            # Convert face vector to face name
            face_map = {
                (0, 1, 0): "top",
                (0, -1, 0): "bottom",
                (0, 0, -1): "north",
                (0, 0, 1): "south",
                (1, 0, 0): "east",
                (-1, 0, 0): "west"
            }
            face = face_map.get(tuple(face_vector), "top")
            
            result = await self.bridge_manager_instance.place_block(x, y, z, face)
            return {
                "status": "success",
                "position": {"x": x, "y": y, "z": z},
                "face": face,
                "result": result
            }
        except Exception as e:
            logger.error(f"Place block failed: {e}")
            return {"status": "error", "error": str(e)}
    
    async def equip_item(self, item_name_or_id: Union[str, int], destination: str) -> Dict[str, Any]:
        """Equip an item
        
        Args:
            item_name_or_id: Item name or numeric ID
            destination: Where to equip ('hand', 'head', 'torso', 'legs', 'feet', 'off-hand')
            
        Returns:
            Dict with equip result
        """
        try:
            result = await self.bridge_manager_instance.execute_command(
                "inventory.equip", item=item_name_or_id, destination=destination
            )
            return {
                "status": "success",
                "equipped": item_name_or_id,
                "destination": destination
            }
        except Exception as e:
            logger.error(f"Equip item failed: {e}")
            return {"status": "error", "error": str(e)}
    
    async def craft_item(self, recipe_id: int, count: int, crafting_table_block_or_None: Optional[Any]) -> Dict[str, Any]:
        """Craft an item using a recipe
        
        Args:
            recipe_id: Recipe ID to use
            count: Number of items to craft
            crafting_table_block_or_None: Crafting table block object or None for inventory crafting
            
        Returns:
            Dict with craft result
        """
        try:
            # For now, use the existing craft command which takes item name
            # This would need to be updated to use recipe_id in the future
            result = await self.bridge_manager_instance.execute_command(
                "craft", recipe="unknown", count=count
            )
            return result
        except Exception as e:
            logger.error(f"Craft item failed: {e}")
            return {"status": "error", "error": str(e)}
    
    async def get_inventory_items(self) -> List[Dict[str, Any]]:
        """Get current inventory items
        
        Returns:
            List of inventory item dicts
        """
        try:
            items = await self.bridge_manager_instance.get_inventory()
            return items if isinstance(items, list) else []
        except Exception as e:
            logger.error(f"Get inventory failed: {e}")
            return []
    
    async def get_position(self) -> Dict[str, float]:
        """Get current bot position
        
        Returns:
            Dict with x, y, z coordinates
        """
        try:
            return await self.bridge_manager_instance.get_position()
        except Exception as e:
            logger.error(f"Get position failed: {e}")
            return {"x": 0, "y": 0, "z": 0}
    
    async def get_health(self) -> Dict[str, float]:
        """Get bot health, food, and saturation
        
        Returns:
            Dict with health stats
        """
        try:
            result = await self.bridge_manager_instance.execute_command("entity.health")
            return result
        except Exception as e:
            logger.error(f"Get health failed: {e}")
            return {"health": 0, "food": 0, "saturation": 0}
    
    async def find_blocks(self, block_name: str, max_distance: int = 64, count: int = 1) -> List[Dict[str, int]]:
        """Find blocks of a specific type
        
        Args:
            block_name: Name of block to find
            max_distance: Maximum search distance
            count: Maximum number of blocks to return
            
        Returns:
            List of block positions
        """
        try:
            result = await self.bridge_manager_instance.execute_command(
                "world.findBlocks", name=block_name, maxDistance=max_distance, count=count
            )
            return result if isinstance(result, list) else []
        except Exception as e:
            logger.error(f"Find blocks failed: {e}")
            return []
    
    async def get_block_at(self, x: int, y: int, z: int) -> Dict[str, Any]:
        """Get block information at specific position
        
        Args:
            x: X coordinate
            y: Y coordinate
            z: Z coordinate
            
        Returns:
            Dict with block information
        """
        try:
            result = await self.bridge_manager_instance.execute_command(
                "world.getBlock", x=x, y=y, z=z
            )
            return result
        except Exception as e:
            logger.error(f"Get block failed: {e}")
            return {"name": "unknown", "type": -1}
    
    async def activate_item(self) -> Dict[str, Any]:
        """Activate/use the currently held item
        
        Returns:
            Dict with activation result
        """
        try:
            result = await self.bridge_manager_instance.execute_command("js_activateItem")
            return {"status": "success", "activated": True}
        except Exception as e:
            logger.error(f"Activate item failed: {e}")
            return {"status": "error", "error": str(e)}
    
    async def deactivate_item(self) -> Dict[str, Any]:
        """Deactivate the currently held item
        
        Returns:
            Dict with deactivation result
        """
        try:
            result = await self.bridge_manager_instance.execute_command("js_deactivateItem")
            return {"status": "success", "deactivated": True}
        except Exception as e:
            logger.error(f"Deactivate item failed: {e}")
            return {"status": "error", "error": str(e)}
    
    async def use_on_block(self, x: int, y: int, z: int) -> Dict[str, Any]:
        """Use held item on a block (right-click)
        
        Args:
            x: Block X coordinate
            y: Block Y coordinate
            z: Block Z coordinate
            
        Returns:
            Dict with use result
        """
        try:
            result = await self.bridge_manager_instance.execute_command(
                "js_useOnBlock", x=x, y=y, z=z
            )
            return {"status": "success", "used_on": {"x": x, "y": y, "z": z}}
        except Exception as e:
            logger.error(f"Use on block failed: {e}")
            return {"status": "error", "error": str(e)}
    
    async def attack_entity(self, entity_id: int) -> Dict[str, Any]:
        """Attack an entity
        
        Args:
            entity_id: ID of entity to attack
            
        Returns:
            Dict with attack result
        """
        try:
            result = await self.bridge_manager_instance.execute_command(
                "js_attackEntity", entity_id=entity_id
            )
            return {"status": "success", "attacked": entity_id}
        except Exception as e:
            logger.error(f"Attack entity failed: {e}")
            return {"status": "error", "error": str(e)}
    
    async def drop_item(self, item_name: str, count: Optional[int] = None) -> Dict[str, Any]:
        """Drop items from inventory
        
        Args:
            item_name: Name of item to drop
            count: Number to drop (None = all)
            
        Returns:
            Dict with drop result
        """
        try:
            result = await self.bridge_manager_instance.execute_command(
                "js_dropItem", item_name=item_name, count=count
            )
            return {"status": "success", "dropped": item_name, "count": count}
        except Exception as e:
            logger.error(f"Drop item failed: {e}")
            return {"status": "error", "error": str(e)}