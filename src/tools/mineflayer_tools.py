"""
Mineflayer Tools for Google ADK - Wraps Minecraft bot commands as ADK tools
"""
from typing import Any, Dict, List

import structlog

logger = structlog.get_logger(__name__)

# Global bridge reference for tool functions
_bridge_manager = None

def _set_bridge_manager(bridge):
    """Set the global bridge manager for tool functions"""
    global _bridge_manager
    _bridge_manager = bridge


async def move_to(x: int, y: int, z: int) -> Dict[str, Any]:
    """Move bot to specified coordinates using pathfinding.

    Args:
        x: Target X coordinate
        y: Target Y coordinate  
        z: Target Z coordinate

    Returns:
        Dictionary with movement result including status and position
    """
    try:
        # Validate coordinates are reasonable
        if abs(x) > 30000 or abs(z) > 30000 or y < -64 or y > 320:
            return {
                "status": "error",
                "error": "Invalid coordinates - out of world bounds"
            }
        
        # Get current position for distance calculation
        current_pos = await _bridge_manager.get_position()
        if isinstance(current_pos, dict) and 'error' in current_pos:
            return {
                "status": "error",
                "error": "Cannot get current position - not connected to server"
            }
        
        distance = (
            (x - current_pos["x"]) ** 2
            + (y - current_pos["y"]) ** 2
            + (z - current_pos["z"]) ** 2
        ) ** 0.5

        logger.info(f"Moving to ({x}, {y}, {z}), distance: {distance:.1f}")

        # Execute movement
        result = await _bridge_manager.move_to(x, y, z)
        
        # Check if movement succeeded
        if isinstance(result, dict) and result.get('error'):
            return {
                "status": "error",
                "error": result['error']
            }

        return {
            "status": "success",
            "position": {"x": x, "y": y, "z": z},
            "distance_traveled": round(distance, 1),
            "message": f"Successfully moved {distance:.1f} blocks to ({x}, {y}, {z})"
        }

    except Exception as e:
        logger.error(f"Movement failed: {e}")
        return {
            "status": "error",
            "error": f"Movement failed: {str(e)}"
        }


async def dig_block(x: int, y: int, z: int) -> Dict[str, Any]:
    """Dig a block at specified coordinates.

    Args:
        x: Block X coordinate
        y: Block Y coordinate
        z: Block Z coordinate

    Returns:
        Dictionary with dig result including block type and position
    """
    try:
        # Validate coordinates
        if abs(x) > 30000 or abs(z) > 30000 or y < -64 or y > 320:
            return {
                "status": "error",
                "error": "Invalid coordinates - out of world bounds"
            }
        
        # Check what block is there first
        block_info = await _bridge_manager.execute_command("world.getBlock", x=x, y=y, z=z)
        
        if isinstance(block_info, dict) and 'error' in block_info:
            return {
                "status": "error",
                "error": "Cannot check block - not connected to server"
            }
        
        block_name = block_info.get("name", "unknown")

        if block_name == "air":
            return {
                "status": "error",
                "error": "No block to dig at this position - it's already air"
            }
        
        if block_name in ["bedrock", "barrier", "command_block"]:
            return {
                "status": "error",
                "error": f"Cannot dig {block_name} - it's unbreakable"
            }

        logger.info(f"Digging {block_name} at ({x}, {y}, {z})")

        # Dig the block
        result = await _bridge_manager.dig_block(x, y, z)
        
        if isinstance(result, dict) and result.get('error'):
            return {
                "status": "error",
                "error": result['error']
            }

        return {
            "status": "success",
            "block": block_name,
            "position": {"x": x, "y": y, "z": z},
            "message": f"Successfully dug {block_name} at ({x}, {y}, {z})"
        }

    except Exception as e:
        logger.error(f"Dig failed: {e}")
        return {
            "status": "error",
            "error": f"Failed to dig block: {str(e)}"
        }


async def place_block(
    x: int,
    y: int,
    z: int,
    block_type: str,
    face: str,
) -> Dict[str, Any]:
    """Place a block at specified coordinates.

    Args:
        x: Reference block X coordinate
        y: Reference block Y coordinate
        z: Reference block Z coordinate
        block_type: Type of block to place
        face: Which face of the reference block to place against (top, bottom, north, south, east, west)

    Returns:
        Dictionary with place result
    """
    try:
        # Validate face
        valid_faces = ["top", "bottom", "north", "south", "east", "west"]
        if face.lower() not in valid_faces:
            return {
                "status": "error",
                "error": f"Invalid face '{face}'. Must be one of: {', '.join(valid_faces)}"
            }
        
        # Validate coordinates
        if abs(x) > 30000 or abs(z) > 30000 or y < -64 or y > 320:
            return {
                "status": "error",
                "error": "Invalid coordinates - out of world bounds"
            }
        
        # Check inventory for the block
        inventory = await _bridge_manager.get_inventory()
        
        if isinstance(inventory, dict) and 'error' in inventory:
            return {
                "status": "error",
                "error": "Cannot check inventory - not connected to server"
            }
        
        if not isinstance(inventory, list):
            return {
                "status": "error",
                "error": "Invalid inventory response"
            }
        
        has_block = any(
            item.get("name") == block_type 
            for item in inventory 
            if isinstance(item, dict)
        )

        if not has_block:
            return {
                "status": "error",
                "error": f"No {block_type} in inventory to place"
            }

        # Equip the block
        equip_result = await _bridge_manager.execute_command(
            "inventory.equip", item=block_type, destination="hand"
        )
        
        if isinstance(equip_result, dict) and equip_result.get('error'):
            return {
                "status": "error",
                "error": f"Failed to equip {block_type}: {equip_result['error']}"
            }

        # Place the block
        result = await _bridge_manager.place_block(x, y, z, face)
        
        if isinstance(result, dict) and result.get('error'):
            return {
                "status": "error",
                "error": result['error']
            }

        logger.info(f"Placed {block_type} at ({x}, {y}, {z}) on {face} face")

        return {
            "status": "success",
            "block": block_type,
            "position": {"x": x, "y": y, "z": z},
            "face": face,
            "message": f"Successfully placed {block_type} at ({x}, {y}, {z}) on {face} face"
        }

    except Exception as e:
        logger.error(f"Place failed: {e}")
        return {
            "status": "error",
            "error": f"Failed to place block: {str(e)}"
        }


async def find_blocks(
    block_name: str,
    max_distance: int,
    count: int,
) -> Dict[str, Any]:
    """Find blocks of a specific type near the bot.

    Args:
        block_name: Name of block to find (e.g. "oak_log", "stone")
        max_distance: Maximum search distance
        count: Maximum number of blocks to return

    Returns:
        Dictionary with found blocks and their positions
    """
    try:
        # Validate inputs
        if max_distance <= 0 or max_distance > 256:
            return {
                "status": "error",
                "error": "Max distance must be between 1 and 256 blocks"
            }
        
        if count <= 0:
            return {
                "status": "error",
                "error": "Count must be at least 1"
            }
        
        logger.info(f"Searching for {block_name} within {max_distance} blocks")

        blocks = await _bridge_manager.execute_command(
            "world.findBlocks", name=block_name, maxDistance=max_distance, count=count
        )
        
        # Check for error response
        if isinstance(blocks, dict) and 'error' in blocks:
            return {
                "status": "error",
                "error": blocks['error']
            }

        # Handle no blocks found
        if not blocks or not isinstance(blocks, list):
            return {
                "status": "success",
                "block_type": block_name,
                "count": 0,
                "positions": [],
                "message": f"No {block_name} blocks found within {max_distance} blocks"
            }

        return {
            "status": "success",
            "block_type": block_name,
            "count": len(blocks),
            "positions": blocks,
            "message": f"Found {len(blocks)} {block_name} blocks within {max_distance} blocks"
        }

    except Exception as e:
        logger.error(f"Block search failed: {e}")
        return {
            "status": "error",
            "error": f"Failed to search for blocks: {str(e)}"
        }


async def get_nearby_players() -> Dict[str, Any]:
    """Get information about nearby players.

    Returns:
        Dictionary with player information
    """
    try:
        # This would come from event stream in full implementation
        # For now, return empty list as placeholder
        players = []

        return {"status": "success", "count": len(players), "players": players}

    except Exception as e:
        logger.error(f"Player query failed: {e}")
        return {"status": "error", "error": str(e)}


async def get_inventory() -> Dict[str, Any]:
    """Get current inventory contents.

    Returns:
        Dictionary with inventory items and summary
    """
    try:
        items = await _bridge_manager.get_inventory()
        
        # Check for error response
        if isinstance(items, dict) and 'error' in items:
            return {
                "status": "error",
                "error": "Cannot access inventory - not connected to server"
            }
        
        # Handle empty inventory
        if not items or not isinstance(items, list):
            return {
                "status": "success",
                "items": [],
                "summary": {},
                "total_items": 0,
                "message": "Inventory is empty"
            }

        # Organize by item type
        inventory_summary = {}
        total_count = 0
        for item in items:
            if isinstance(item, dict) and "name" in item and "count" in item:
                name = item["name"]
                count = item["count"]
                inventory_summary[name] = inventory_summary.get(name, 0) + count
                total_count += count

        return {
            "status": "success",
            "items": items,
            "summary": inventory_summary,
            "total_items": total_count,
            "message": f"Found {len(inventory_summary)} different items, {total_count} total"
        }

    except Exception as e:
        logger.error(f"Inventory query failed: {e}")
        return {
            "status": "error",
            "error": f"Failed to get inventory: {str(e)}"
        }


async def craft_item(recipe: str, count: int) -> Dict[str, Any]:
    """Craft an item using available materials.

    Args:
        recipe: Name of item to craft
        count: Number to craft

    Returns:
        Dictionary with craft result
    """
    # Simplified for POC - full implementation would check recipes
    try:
        logger.info(f"Crafting {count} {recipe}")

        # This would use actual Mineflayer crafting API
        await _bridge_manager.execute_command("craft", recipe=recipe, count=count)

        return {"status": "success", "crafted": recipe, "count": count}

    except Exception as e:
        logger.error(f"Crafting failed: {e}")
        return {"status": "error", "error": str(e)}


async def send_chat(message: str) -> Dict[str, Any]:
    """Send a chat message.

    Args:
        message: Message to send

    Returns:
        Dictionary with send result
    """
    try:
        # Validate message
        if not message or not message.strip():
            return {
                "status": "error",
                "error": "Cannot send empty message"
            }
        
        if len(message) > 256:
            return {
                "status": "error",
                "error": "Message too long - maximum 256 characters"
            }
        
        result = await _bridge_manager.chat(message)
        
        if isinstance(result, dict) and result.get('error'):
            return {
                "status": "error",
                "error": result['error']
            }

        return {
            "status": "success",
            "message": message,
            "length": len(message)
        }

    except Exception as e:
        logger.error(f"Chat failed: {e}")
        return {
            "status": "error",
            "error": f"Failed to send chat: {str(e)}"
        }


def create_mineflayer_tools(bridge_manager) -> List:
    """Create all Mineflayer tools for ADK agents.

    Args:
        bridge_manager: BridgeManager instance

    Returns:
        List of tool functions (ADK will automatically wrap them)
    """
    # Set the global bridge manager
    _set_bridge_manager(bridge_manager)
    
    # Return list of tool functions - ADK automatically creates FunctionTool objects
    return [
        move_to,
        dig_block,
        place_block,
        find_blocks,
        get_nearby_players,
        get_inventory,
        craft_item,
        send_chat,
    ]
