"""
Mineflayer Tools for Google ADK - Wraps Minecraft bot commands as ADK tools
"""
from typing import Any, Dict, List, Optional

from google.adk.tools import ToolContext

from ..logging_config import get_logger

logger = get_logger(__name__)

# Global bridge reference for tool functions
_bridge_manager = None

def _set_bridge_manager(bridge):
    """Set the global bridge manager for tool functions"""
    global _bridge_manager
    _bridge_manager = bridge


async def move_to(x: int, y: int, z: int, tool_context: Optional[ToolContext] = None) -> Dict[str, Any]:
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
        current_pos = await _bridge_manager.get_position()
        distance = (
            (x - current_pos["x"]) ** 2
            + (y - current_pos["y"]) ** 2
            + (z - current_pos["z"]) ** 2
        ) ** 0.5

        logger.info(f"Moving to ({x}, {y}, {z}), distance: {distance:.1f}")

        # Execute movement
        await _bridge_manager.move_to(x, y, z)

        result = {
            "status": "success",
            "position": {"x": x, "y": y, "z": z},
            "distance_traveled": distance,
        }
        
        # Update position in session state if tool_context is provided
        if tool_context and hasattr(tool_context, 'state'):
            tool_context.state['minecraft_position'] = {
                'x': x,
                'y': y,
                'z': z,
                'timestamp': __import__('time').time()
            }
            logger.info("Updated position in session state")
        
        return result

    except Exception as e:
        logger.error(f"Movement failed: {e}")
        error_result = {"status": "error", "error": str(e)}
        
        # Save movement error if tool_context is provided
        if tool_context and hasattr(tool_context, 'state'):
            tool_context.state['minecraft_last_movement_error'] = {
                'error': str(e),
                'target': {'x': x, 'y': y, 'z': z},
                'timestamp': __import__('time').time()
            }
        
        return error_result


async def dig_block(x: int, y: int, z: int, tool_context: Optional[ToolContext] = None) -> Dict[str, Any]:
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
        block_info = await _bridge_manager.execute_command("world.getBlock", x=x, y=y, z=z)
        block_name = block_info.get("name", "unknown")

        if block_name == "air":
            return {"status": "error", "error": "No block to dig at this position"}

        logger.info(f"Digging {block_name} at ({x}, {y}, {z})")

        # Dig the block
        await _bridge_manager.dig_block(x, y, z)

        return {"status": "success", "block": block_name, "position": {"x": x, "y": y, "z": z}}

    except Exception as e:
        logger.error(f"Dig failed: {e}")
        return {"status": "error", "error": str(e)}


async def place_block(
    x: int,
    y: int,
    z: int,
    block_type: str,
    face: str,
    tool_context: Optional[ToolContext] = None,
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
        inventory = await _bridge_manager.get_inventory()
        has_block = any(item["name"] == block_type for item in inventory)

        if not has_block:
            return {"status": "error", "error": f"No {block_type} in inventory"}

        # Equip the block
        await _bridge_manager.execute_command(
            "inventory.equip", item=block_type, destination="hand"
        )

        # Place the block
        await _bridge_manager.place_block(x, y, z, face)

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


async def get_position() -> Dict[str, Any]:
    """Get the bot's current position in the world.
    
    Returns:
        Dictionary with bot's coordinates
    """
    try:
        position = await _bridge_manager.get_position()
        
        if position:
            return {
                'status': 'success',
                'position': position,
                'x': position.get('x'),
                'y': position.get('y'),
                'z': position.get('z')
            }
        else:
            return {
                'status': 'error',
                'error': 'Unable to get position'
            }
            
    except Exception as e:
        logger.error(f"Error getting position: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }


async def find_blocks(
    block_name: str,
    max_distance: int,
    count: int,
    tool_context: Optional[ToolContext] = None,
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

        blocks = await _bridge_manager.execute_command(
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


async def get_nearby_players(tool_context: Optional[ToolContext] = None) -> Dict[str, Any]:
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


async def get_inventory(tool_context: Optional[ToolContext] = None) -> Dict[str, Any]:
    """Get current inventory contents.

    Returns:
        Dictionary with inventory items
    """
    try:
        items = await _bridge_manager.get_inventory()

        # Organize by item type
        inventory_summary = {}
        for item in items:
            name = item["name"]
            if name not in inventory_summary:
                inventory_summary[name] = 0
            inventory_summary[name] += item["count"]

        result = {
            "status": "success",
            "items": items,
            "summary": inventory_summary,
            "total_items": sum(item["count"] for item in items),
        }
        
        # Save structured inventory data to session state if tool_context is provided
        if tool_context and hasattr(tool_context, 'state'):
            tool_context.state['minecraft_inventory'] = {
                'items': items,
                'summary': inventory_summary,
                'total_items': result['total_items'],
                'timestamp': __import__('time').time()
            }
            logger.info("Saved inventory data to session state")
        
        return result

    except Exception as e:
        logger.error(f"Inventory query failed: {e}")
        error_result = {"status": "error", "error": str(e)}
        
        # Save error state if tool_context is provided
        if tool_context and hasattr(tool_context, 'state'):
            tool_context.state['minecraft_inventory'] = {
                'error': str(e),
                'timestamp': __import__('time').time()
            }
        
        return error_result


async def craft_item(recipe: str, count: int, tool_context: Optional[ToolContext] = None) -> Dict[str, Any]:
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


async def send_chat(message: str, tool_context: Optional[ToolContext] = None) -> Dict[str, Any]:
    """Send a chat message.

    Args:
        message: Message to send

    Returns:
        Dictionary with send result
    """
    try:
        await _bridge_manager.chat(message)

        return {"status": "success", "message": message}

    except Exception as e:
        logger.error(f"Chat failed: {e}")
        return {"status": "error", "error": str(e)}


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
        get_position,
        find_blocks,
        get_nearby_players,
        get_inventory,
        craft_item,
        send_chat,
    ]
