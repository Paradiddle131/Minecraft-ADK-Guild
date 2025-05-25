"""
Mineflayer Tools for Google ADK - Wraps Minecraft bot commands as ADK tools
"""
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)


def create_mineflayer_tools(bridge_manager):
    """Create all Mineflayer tools for ADK agents.

    Args:
        bridge_manager: BridgeManager instance

    Returns:
        List of tool functions
    """
    
    async def move_to(x: int, y: int, z: int) -> Dict[str, Any]:
        """Move bot to specified coordinates using pathfinding.
        
        Args:
            x: Target X coordinate
            y: Target Y coordinate
            z: Target Z coordinate
            
        Returns:
            Dictionary with movement result
        """
        try:
            # Get current position for distance calculation
            current_pos = await bridge_manager.get_position()
            distance = (
                (x - current_pos["x"]) ** 2
                + (y - current_pos["y"]) ** 2
                + (z - current_pos["z"]) ** 2
            ) ** 0.5

            logger.info(f"Moving to ({x}, {y}, {z}), distance: {distance:.1f}")

            # Execute movement
            await bridge_manager.move_to(x, y, z)

            return {
                "status": "success",
                "position": {"x": x, "y": y, "z": z},
                "distance_traveled": distance,
            }

        except Exception as e:
            logger.error(f"Movement failed: {e}")
            return {"status": "error", "error": str(e)}

    async def dig_block(x: int, y: int, z: int) -> Dict[str, Any]:
        """Dig a block at specified coordinates.

        Args:
            x: Block X coordinate
            y: Block Y coordinate
            z: Block Z coordinate

        Returns:
            Dictionary with dig result
        """
        try:
            # Check what block is there first
            block_info = await bridge_manager.execute_command("world.getBlock", x=x, y=y, z=z)
            block_name = block_info.get("name", "unknown")

            if block_name == "air":
                return {"status": "error", "error": "No block to dig at this position"}

            logger.info(f"Digging {block_name} at ({x}, {y}, {z})")

            # Dig the block
            await bridge_manager.dig_block(x, y, z)

            return {"status": "success", "block": block_name, "position": {"x": x, "y": y, "z": z}}

        except Exception as e:
            logger.error(f"Dig failed: {e}")
            return {"status": "error", "error": str(e)}

    async def place_block(
        x: int,
        y: int,
        z: int,
        block_type: str = "stone",
        face: str = "top"
    ) -> Dict[str, Any]:
        """Place a block at specified coordinates.

        Args:
            x: Reference block X coordinate
            y: Reference block Y coordinate
            z: Reference block Z coordinate
            block_type: Type of block to place
            face: Which face of the reference block to place against

        Returns:
            Dictionary with place result
        """
        try:
            # Check inventory for the block
            inventory = await bridge_manager.get_inventory()
            has_block = any(item["name"] == block_type for item in inventory)

            if not has_block:
                return {"status": "error", "error": f"No {block_type} in inventory"}

            # Equip the block
            await bridge_manager.execute_command(
                "inventory.equip", item=block_type, destination="hand"
            )

            # Place the block
            await bridge_manager.place_block(x, y, z, face)

            logger.info(f"Placed {block_type} at ({x}, {y}, {z})")

            return {
                "status": "success",
                "block": block_type,
                "position": {"x": x, "y": y, "z": z},
                "face": face,
            }

        except Exception as e:
            logger.error(f"Place failed: {e}")
            return {"status": "error", "error": str(e)}

    async def find_blocks(
        block_name: str,
        max_distance: int = 64,
        count: int = 10
    ) -> Dict[str, Any]:
        """Find blocks of a specific type near the bot.

        Args:
            block_name: Name of block to find (e.g. "oak_log", "stone")
            max_distance: Maximum search distance
            count: Maximum number of blocks to return

        Returns:
            Dictionary with found blocks
        """
        try:
            logger.info(f"Searching for {block_name} within {max_distance} blocks")

            blocks = await bridge_manager.execute_command(
                "world.findBlocks", name=block_name, maxDistance=max_distance, count=count
            )

            return {
                "status": "success",
                "block_type": block_name,
                "count": len(blocks),
                "positions": blocks,
            }

        except Exception as e:
            logger.error(f"Block search failed: {e}")
            return {"status": "error", "error": str(e)}

    async def get_inventory() -> Dict[str, Any]:
        """Get current inventory contents.

        Returns:
            Dictionary with inventory items
        """
        try:
            items = await bridge_manager.get_inventory()

            # Organize by item type
            inventory_summary = {}
            for item in items:
                name = item["name"]
                if name not in inventory_summary:
                    inventory_summary[name] = 0
                inventory_summary[name] += item["count"]

            return {
                "status": "success",
                "items": items,
                "summary": inventory_summary,
                "total_items": sum(item["count"] for item in items),
            }

        except Exception as e:
            logger.error(f"Inventory query failed: {e}")
            return {"status": "error", "error": str(e)}

    async def send_chat(message: str) -> Dict[str, Any]:
        """Send a chat message.

        Args:
            message: Message to send

        Returns:
            Dictionary with send result
        """
        try:
            await bridge_manager.chat(message)
            return {"status": "success", "message": message}

        except Exception as e:
            logger.error(f"Chat failed: {e}")
            return {"status": "error", "error": str(e)}
            
    async def get_position() -> Dict[str, Any]:
        """Get the bot's current position.
        
        Returns:
            Dictionary with position information
        """
        try:
            pos = await bridge_manager.get_position()
            return {
                "status": "success",
                "position": pos
            }
        except Exception as e:
            logger.error(f"Failed to get position: {e}")
            return {"status": "error", "error": str(e)}

    # Return the tool functions directly - ADK will wrap them
    return [
        move_to,
        dig_block,
        place_block,
        find_blocks,
        get_inventory,
        send_chat,
        get_position
    ]
