"""
BotController - Python class that encapsulates all bot actions
Provides a Python-centric interface for controlling the Minecraft bot
"""
import logging
from typing import Any, Dict, List, Optional, Union

from .bridge.bridge_manager import BridgeManager

logger = logging.getLogger(__name__)


class BotController:
    """Python controller for all Minecraft bot actions via BridgeManager"""

    _instance = None
    _bridge_manager = None

    def __new__(cls, bridge_manager_instance: BridgeManager):
        if cls._instance is None or cls._bridge_manager is not bridge_manager_instance:
            cls._instance = super().__new__(cls)
            cls._bridge_manager = bridge_manager_instance
        return cls._instance

    def __init__(self, bridge_manager_instance: BridgeManager):
        """Initialize the BotController with a BridgeManager instance

        Args:
            bridge_manager_instance: An initialized BridgeManager instance
        """
        # Only initialize if not already initialized or bridge manager changed
        if not hasattr(self, "bridge_manager_instance") or self.bridge_manager_instance is not bridge_manager_instance:
            self.bridge_manager_instance = bridge_manager_instance
            logger.info("Initialized BotController")

    def _check_connection(self) -> Dict[str, Any]:
        """Check if bridge is connected and return error message if not

        Returns:
            None if connected, error dict if not connected
        """
        if not self.bridge_manager_instance.is_connected:
            return {
                "status": "error",
                "error": "Not connected to server",
                "message": "I am not currently connected to a Minecraft server. I am running in a simulated environment. If you connect me to a Minecraft server, I can check the inventory.",
            }
        return None

    async def chat(self, message: str) -> Dict[str, Any]:
        """Send a chat message

        Args:
            message: Message to send in chat

        Returns:
            Dict with send status
        """
        conn_error = self._check_connection()
        if conn_error:
            return conn_error

        try:
            await self.bridge_manager_instance.chat(message)
            return {"status": "success", "message": message}
        except Exception as e:
            logger.error(f"Chat failed: {e}")
            return {"status": "error", "error": str(e)}

    async def move_to(self, x: int, y: int, z: int, timeout: Optional[int] = None) -> Dict[str, Any]:
        """Move bot to specific coordinates

        Args:
            x: Target X coordinate
            y: Target Y coordinate
            z: Target Z coordinate
            timeout: Optional timeout in milliseconds

        Returns:
            Dict with movement result
        """
        conn_error = self._check_connection()
        if conn_error:
            return conn_error

        try:
            result = await self.bridge_manager_instance.move_to(x, y, z, timeout)

            # Check if the result indicates an error
            if isinstance(result, dict):
                # First check if it's an error dict from bridge callback ({"error": "..."})
                if "error" in result and not result.get("status"):
                    error_msg = str(result["error"])
                    # Return error with proper status
                    return {"status": "error", "error": error_msg}
                # Check for other error formats
                elif result.get("status") == "error":
                    return {"status": "error", "error": result.get("error", "Unknown error")}
                elif "timeout" in str(result.get("message", "")).lower():
                    return {"status": "error", "error": result.get("message")}
                elif "timeout" in str(result.get("error", "")).lower():
                    return {"status": "error", "error": result.get("error")}

            return {"status": "success", "target": {"x": x, "y": y, "z": z}, "result": result}
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Movement failed: {error_msg}")

            # Check if it's a timeout error
            if "timeout" in error_msg.lower():
                return {"status": "error", "error": f"Movement timed out after {timeout}ms: {error_msg}"}
            else:
                return {"status": "error", "error": error_msg}

    async def look_at(self, x: int, y: int, z: int) -> Dict[str, Any]:
        """Make bot look at specific coordinates

        Args:
            x: X coordinate to look at
            y: Y coordinate to look at
            z: Z coordinate to look at

        Returns:
            Dict with result
        """
        conn_error = self._check_connection()
        if conn_error:
            return conn_error

        try:
            await self.bridge_manager_instance.execute_command("js_lookAt", x=x, y=y, z=z)
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
            return {"status": "success", "position": {"x": x, "y": y, "z": z}, "result": result}
        except Exception as e:
            logger.error(f"Start digging failed: {e}")
            return {"status": "error", "error": str(e)}

    async def dig_block(self, x: int, y: int, z: int) -> Dict[str, Any]:
        """Dig a block at specific coordinates

        Args:
            x: X coordinate
            y: Y coordinate
            z: Z coordinate

        Returns:
            Dict with dig result
        """
        return await self.start_digging([x, y, z])

    async def stop_digging(self) -> Dict[str, Any]:
        """Stop current digging action

        Returns:
            Dict with result
        """
        conn_error = self._check_connection()
        if conn_error:
            return conn_error

        try:
            await self.bridge_manager_instance.execute_command("js_stopDigging")
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
        conn_error = self._check_connection()
        if conn_error:
            return conn_error

        try:
            x, y, z = reference_block_position
            # Convert face vector to face name
            face_map = {
                (0, 1, 0): "top",
                (0, -1, 0): "bottom",
                (0, 0, -1): "north",
                (0, 0, 1): "south",
                (1, 0, 0): "east",
                (-1, 0, 0): "west",
            }
            face = face_map.get(tuple(face_vector), "top")

            result = await self.bridge_manager_instance.place_block(x, y, z, face)
            return {"status": "success", "position": {"x": x, "y": y, "z": z}, "face": face, "result": result}
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
        conn_error = self._check_connection()
        if conn_error:
            return conn_error

        try:
            await self.bridge_manager_instance.execute_command(
                "inventory.equip", item=item_name_or_id, destination=destination
            )
            return {"status": "success", "equipped": item_name_or_id, "destination": destination}
        except Exception as e:
            logger.error(f"Equip item failed: {e}")
            return {"status": "error", "error": str(e)}

    async def craft_item(
        self, recipe_id: int, count: int, crafting_table_block_or_none: Optional[Any]
    ) -> Dict[str, Any]:
        """Craft an item using a recipe

        Args:
            recipe_id: Recipe ID to use
            count: Number of items to craft
            crafting_table_block_or_none: Crafting table block object or None for inventory crafting

        Returns:
            Dict with craft result
        """
        conn_error = self._check_connection()
        if conn_error:
            return conn_error

        try:
            # For now, use the existing craft command which takes item name
            # This would need to be updated to use recipe_id in the future
            result = await self.bridge_manager_instance.execute_command("craft", recipe="unknown", count=count)
            return result
        except Exception as e:
            logger.error(f"Craft item failed: {e}")
            return {"status": "error", "error": str(e)}

    async def get_inventory_items(self) -> List[Dict[str, Any]]:
        """Get current inventory items

        Returns:
            List of inventory item dicts
        """
        # Check connection but don't return error dict since this method returns a list
        if not self.bridge_manager_instance.is_connected:
            logger.info("Get inventory called in web UI mode - returning empty inventory")
            return []

        try:
            items = await self.bridge_manager_instance.get_inventory()
            return items if isinstance(items, list) else []
        except Exception as e:
            logger.error(f"Get inventory failed: {e}")
            return []

    async def get_position(self) -> Dict[str, Any]:
        """Get current bot position

        Returns:
            Dict with x, y, z coordinates or error
        """
        conn_error = self._check_connection()
        if conn_error:
            return conn_error

        try:
            return await self.bridge_manager_instance.get_position()
        except Exception as e:
            logger.error(f"Get position failed: {e}")
            return {"status": "error", "error": str(e)}

    async def get_health(self) -> Dict[str, Any]:
        """Get bot health, food, and saturation

        Returns:
            Dict with health stats or error
        """
        conn_error = self._check_connection()
        if conn_error:
            return conn_error

        try:
            result = await self.bridge_manager_instance.execute_command("entity.health")
            return result
        except Exception as e:
            logger.error(f"Get health failed: {e}")
            return {"status": "error", "error": str(e)}

    async def find_blocks(
        self, block_identifiers: Union[int, str, List[Union[int, str]]], max_distance: int = 64, count: int = 1
    ) -> List[Dict[str, int]]:
        """Find blocks by ID(s) or name(s)

        Args:
            block_identifiers: Single block ID/name or list of block IDs/names to find
            max_distance: Maximum search distance
            count: Maximum number of blocks to return

        Returns:
            List of block positions
        """
        # Check connection but return empty list since this method returns a list
        if not self.bridge_manager_instance.is_connected:
            logger.info("Find blocks called in web UI mode - returning empty list")
            return []

        try:
            result = await self.bridge_manager_instance.execute_command(
                "world.findBlocks", matching=block_identifiers, maxDistance=max_distance, count=count
            )
            # Handle JavaScript proxy objects that behave like lists
            if isinstance(result, list):
                return result
            elif hasattr(result, "__len__") and hasattr(result, "__iter__"):
                # Convert proxy object to Python list
                python_list = []
                for item in result:
                    # Try to extract x, y, z coordinates from proxy objects
                    try:
                        # Access coordinates directly from the proxy object
                        x = getattr(item, "x", None)
                        y = getattr(item, "y", None)
                        z = getattr(item, "z", None)
                        if x is not None and y is not None and z is not None:
                            python_list.append({"x": x, "y": y, "z": z})
                        else:
                            # Fallback - try to convert to dict
                            python_list.append({"error": f"Could not extract coordinates from {type(item)}"})
                    except Exception as e:
                        # If we can't extract coordinates, create a placeholder
                        python_list.append({"error": f"Coordinate extraction failed: {str(e)}"})
                return python_list
            else:
                return []
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
        conn_error = self._check_connection()
        if conn_error:
            return conn_error

        try:
            result = await self.bridge_manager_instance.execute_command("world.getBlock", x=x, y=y, z=z)
            return result
        except Exception as e:
            logger.error(f"Get block failed: {e}")
            return {"status": "error", "error": str(e)}

    async def activate_item(self) -> Dict[str, Any]:
        """Activate/use the currently held item

        Returns:
            Dict with activation result
        """
        conn_error = self._check_connection()
        if conn_error:
            return conn_error

        try:
            await self.bridge_manager_instance.execute_command("js_activateItem")
            return {"status": "success", "activated": True}
        except Exception as e:
            logger.error(f"Activate item failed: {e}")
            return {"status": "error", "error": str(e)}

    async def deactivate_item(self) -> Dict[str, Any]:
        """Deactivate the currently held item

        Returns:
            Dict with deactivation result
        """
        conn_error = self._check_connection()
        if conn_error:
            return conn_error

        try:
            await self.bridge_manager_instance.execute_command("js_deactivateItem")
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
        conn_error = self._check_connection()
        if conn_error:
            return conn_error

        try:
            await self.bridge_manager_instance.execute_command("js_useOnBlock", x=x, y=y, z=z)
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
        conn_error = self._check_connection()
        if conn_error:
            return conn_error

        try:
            await self.bridge_manager_instance.execute_command("js_attackEntity", entity_id=entity_id)
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
        conn_error = self._check_connection()
        if conn_error:
            return conn_error

        try:
            await self.bridge_manager_instance.execute_command("js_dropItem", item_name=item_name, count=count)
            return {"status": "success", "dropped": item_name, "count": count}
        except Exception as e:
            logger.error(f"Drop item failed: {e}")
            return {"status": "error", "error": str(e)}

    async def toss_item(self, item_type: str, count: int = 1, metadata: Optional[int] = None) -> Dict[str, Any]:
        """Toss specific amount of an item type from inventory

        Args:
            item_type: Name or ID of item to toss
            count: Number of items to toss (default 1)
            metadata: Optional metadata for the item

        Returns:
            Dict with toss result
        """
        conn_error = self._check_connection()
        if conn_error:
            return conn_error

        try:
            result = await self.bridge_manager_instance.execute_command(
                "toss", itemType=item_type, count=count, metadata=metadata
            )

            if result and hasattr(result, "success") and getattr(result, "success"):
                # JSPyBridge proxy object with nested result
                if hasattr(result, "result"):
                    nested_result = getattr(result, "result")
                    return {
                        "status": "success",
                        "tossed": getattr(nested_result, "tossed", count),
                        "item": getattr(nested_result, "item", item_type),
                    }
                else:
                    return {
                        "status": "success",
                        "tossed": getattr(result, "tossed", count),
                        "item": getattr(result, "item", item_type),
                    }
            elif result and hasattr(result, "get") and result.get("success"):
                # Dictionary-style result
                return {
                    "status": "success",
                    "tossed": result.get("tossed", count),
                    "item": result.get("item", item_type),
                }
            else:
                error_msg = (
                    result.get("error", "Unknown toss error")
                    if result and hasattr(result, "get")
                    else "No response from bot"
                )
                return {"status": "error", "error": error_msg}

        except Exception as e:
            logger.error(f"Toss item failed: {e}")
            return {"status": "error", "error": str(e)}

    async def toss_stack(self, slot_index: int) -> Dict[str, Any]:
        """Toss entire stack from specific inventory slot

        Args:
            slot_index: Inventory slot index (0-based)

        Returns:
            Dict with toss result
        """
        conn_error = self._check_connection()
        if conn_error:
            return conn_error

        try:
            result = await self.bridge_manager_instance.execute_command("tossStack", slotIndex=slot_index)

            if result and hasattr(result, "success") and getattr(result, "success"):
                # JSPyBridge proxy object with nested result
                if hasattr(result, "result"):
                    nested_result = getattr(result, "result")
                    return {
                        "status": "success",
                        "tossed": getattr(nested_result, "tossed", 0),
                        "item": getattr(nested_result, "item", "unknown"),
                        "slot": getattr(nested_result, "slot", slot_index),
                    }
                else:
                    return {
                        "status": "success",
                        "tossed": getattr(result, "tossed", 0),
                        "item": getattr(result, "item", "unknown"),
                        "slot": getattr(result, "slot", slot_index),
                    }
            elif result and hasattr(result, "get") and result.get("success"):
                # Dictionary-style result
                return {
                    "status": "success",
                    "tossed": result.get("tossed", 0),
                    "item": result.get("item", "unknown"),
                    "slot": result.get("slot", slot_index),
                }
            else:
                error_msg = (
                    result.get("error", "Unknown toss stack error")
                    if result and hasattr(result, "get")
                    else "No response from bot"
                )
                return {"status": "error", "error": error_msg}

        except Exception as e:
            logger.error(f"Toss stack failed: {e}")
            return {"status": "error", "error": str(e)}
