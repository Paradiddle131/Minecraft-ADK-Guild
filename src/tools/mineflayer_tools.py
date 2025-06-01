"""
Mineflayer Tools for Google ADK - Wraps Minecraft bot commands as ADK tools
External layer that converts internal Pydantic models to ADK-compliant dictionaries
"""
import asyncio
import math
from typing import Any, Dict, List, Optional

from google.adk.tools import ToolContext

from ..config import get_config
from ..logging_config import get_logger
from ..minecraft_bot_controller import BotController
from ..minecraft_data_service import MinecraftDataService

logger = get_logger(__name__)

# Global references for tool functions
_bot_controller: Optional[BotController] = None
_mc_data_service: Optional[MinecraftDataService] = None


def set_bot_controller(controller: BotController):
    """Set the bot controller instance for all tools"""
    global _bot_controller
    _bot_controller = controller
    logger.info("Bot controller set for mineflayer tools")


def set_minecraft_data_service(service: MinecraftDataService):
    """Set the minecraft data service instance for all tools"""
    global _mc_data_service
    _mc_data_service = service
    logger.info("Minecraft data service set for mineflayer tools")


# Movement Commands
async def move_to(
    x: int, 
    y: int, 
    z: int, 
    timeout: Optional[int] = None,
    tool_context: Optional[ToolContext] = None
) -> Dict[str, Any]:
    """Move bot to coordinates.
    
    Returns:
        Dict with keys:
        - status: 'success', 'error', or 'timeout'
        - target: Target coordinates
        - actual_position: Final position (on success)
        - error: Error message (on failure)
    """
    if not _bot_controller:
        return {
            "status": "error",
            "error": "BotController not initialized"
        }
    
    try:
        # Store movement start in state
        if tool_context and hasattr(tool_context, "state"):
            tool_context.state["temp:movement_in_progress"] = {
                "target": {"x": x, "y": y, "z": z},
                "start_time": __import__("time").time()
            }
        
        # Call internal Pydantic method with progress tracking
        response = await _bot_controller.move_to_with_progress(x, y, z, timeout_ms=timeout)
        
        # Convert to ADK-compliant dictionary
        result = {
            "status": response.status,
            "target": {"x": x, "y": y, "z": z}
        }
        
        if response.status == "success":
            if response.actual_position:
                logger.debug(f"Converting actual_position to dict: {response.actual_position}")
                result["actual_position"] = response.actual_position.dict()
            if response.distance_traveled is not None:
                result["distance_traveled"] = response.distance_traveled
                
            # Send completion message
            logger.debug("Sending chat message 'Arrived'")
            await _bot_controller.chat("Arrived")
            
            # Update state
            if tool_context and response.actual_position:
                tool_context.state["minecraft.position"] = {
                    "x": response.actual_position.x,
                    "y": response.actual_position.y,
                    "z": response.actual_position.z
                }
                tool_context.state["temp:movement_in_progress"] = None
                
        elif response.error_details:
            result["error"] = response.error_details.message
            if response.error_details.suggestion:
                result["suggestion"] = response.error_details.suggestion
            
            # Clear movement in progress
            if tool_context:
                tool_context.state["temp:movement_in_progress"] = None
        
        return result
        
    except Exception as e:
        import traceback
        logger.error(f"Movement error: {e}")
        logger.error(f"Stack trace: {traceback.format_exc()}")
        if tool_context:
            tool_context.state["temp:movement_in_progress"] = None
        return {"status": "error", "error": str(e)}


async def dig_block(x: int, y: int, z: int, tool_context: Optional[ToolContext] = None) -> Dict[str, Any]:
    """Dig a block at specified coordinates.

    Args:
        x: X coordinate of block
        y: Y coordinate of block
        z: Z coordinate of block
        tool_context: Optional tool context for state management

    Returns:
        Dict with status and block information
    """
    if not _bot_controller:
        return {"status": "error", "error": "BotController not initialized"}

    try:
        # Call internal method
        response = await _bot_controller.dig_block(x, y, z)
        
        # Convert to ADK dictionary
        result = {
            "status": response.status,
            "position": {"x": x, "y": y, "z": z}
        }
        
        if response.status == "success":
            if response.block_type:
                result["block_type"] = response.block_type
            if response.drops:
                result["drops"] = response.drops
            if response.dig_time_ms:
                result["dig_time"] = response.dig_time_ms
                
        elif response.error_details:
            result["error"] = response.error_details.message
            if response.error_details.suggestion:
                result["suggestion"] = response.error_details.suggestion
        
        return result
        
    except Exception as e:
        logger.error(f"Dig block error: {e}")
        return {"status": "error", "error": str(e)}


async def place_block(
    x: int, y: int, z: int, item: str, face: str, 
    tool_context: Optional[ToolContext] = None
) -> Dict[str, Any]:
    """Place a block at a specific position.

    Args:
        x: X coordinate to place at
        y: Y coordinate to place at
        z: Z coordinate to place at
        item: Name of block/item to place
        face: Which face to place against
        tool_context: Optional tool context

    Returns:
        Dict with placement result
    """
    if not _bot_controller:
        return {"status": "error", "error": "BotController not initialized"}

    try:
        # Validate item exists
        if _mc_data_service:
            item_data = _mc_data_service.get_item_by_name(item)
            if not item_data:
                return {
                    "status": "error",
                    "error": f"Unknown item: {item}",
                    "suggestion": "Check item name spelling"
                }

        # Call internal method
        response = await _bot_controller.place_block(x, y, z, face, item)
        
        # Convert to ADK dictionary
        result = {
            "status": response.status,
            "position": {"x": x, "y": y, "z": z},
            "item": item
        }
        
        if response.status == "success":
            if response.block_placed:
                result["block_placed"] = response.block_placed
                
        elif response.error_details:
            result["error"] = response.error_details.message
            if response.error_details.suggestion:
                result["suggestion"] = response.error_details.suggestion
        
        return result
        
    except Exception as e:
        logger.error(f"Place block error: {e}")
        return {"status": "error", "error": str(e)}


async def get_inventory(tool_context: Optional[ToolContext] = None) -> Dict[str, Any]:
    """Get the bot's current inventory.
    
    Returns:
        Dict with inventory items and categories
    """
    if not _bot_controller:
        return {"status": "error", "error": "BotController not initialized"}

    try:
        # Call internal method
        response = await _bot_controller.get_inventory()
        
        # Convert to ADK dictionary
        result = {
            "status": response.status
        }
        
        if response.status == "success":
            # Format items for display
            items = []
            for item in response.items:
                items.append({
                    "name": item.name,
                    "count": item.count,
                    "slot": item.slot
                })
            
            result["items"] = items
            result["empty_slots"] = response.empty_slots
            result["total_items"] = sum(item.count for item in response.items)
            
            # Include categories if available
            if response.categories:
                result["categories"] = {
                    category: [{"name": item.name, "count": item.count} for item in items]
                    for category, items in response.categories.items()
                }
            
            # Update state
            if tool_context:
                tool_context.state["minecraft.inventory"] = {
                    "items": items,
                    "empty_slots": response.empty_slots,
                    "last_updated": __import__("time").time()
                }
                
        elif response.error_details:
            result["error"] = response.error_details.message
        
        return result
        
    except Exception as e:
        logger.error(f"Get inventory error: {e}")
        return {"status": "error", "error": str(e)}


async def check_inventory(tool_context: Optional[ToolContext] = None) -> Dict[str, Any]:
    """Check inventory and format output for agents.
    
    Alias for get_inventory with formatted output.
    """
    result = await get_inventory(tool_context)
    
    if result["status"] == "success":
        # Format inventory for display
        inventory_list = []
        for item in result["items"]:
            inventory_list.append(f"- {item['name']}: {item['count']}")
        
        formatted = "\n".join(inventory_list) if inventory_list else "Inventory is empty"
        
        return {
            "status": "success",
            "inventory": formatted,
            "total_items": result["total_items"],
            "empty_slots": result["empty_slots"]
        }
    
    return result


async def get_position(tool_context: Optional[ToolContext] = None) -> Dict[str, Any]:
    """Get the bot's current position.
    
    Returns:
        Dict with x, y, z coordinates
    """
    if not _bot_controller:
        return {"status": "error", "error": "BotController not initialized"}

    try:
        # Call internal method
        response = await _bot_controller.get_position()
        
        # Convert to ADK dictionary
        if response.status == "success" and response.position:
            result = {
                "status": "success",
                "x": response.position.x,
                "y": response.position.y,
                "z": response.position.z
            }
            
            # Update state
            if tool_context:
                tool_context.state["minecraft.position"] = {
                    "x": response.position.x,
                    "y": response.position.y,
                    "z": response.position.z
                }
            
            return result
        else:
            return {
                "status": "error",
                "error": response.error_details.message if response.error_details else "Unknown error"
            }
            
    except Exception as e:
        logger.error(f"Get position error: {e}")
        return {"status": "error", "error": str(e)}


async def craft_item(
    name: str,
    count: Optional[int] = 1,
    tool_context: Optional[ToolContext] = None
) -> Dict[str, Any]:
    """Craft items using available materials.

    Args:
        name: Name of item to craft
        count: Number to craft (default 1)
        tool_context: Optional tool context

    Returns:
        Dict with crafting result
    """
    if not _bot_controller:
        return {"status": "error", "error": "BotController not initialized"}

    try:
        # Send crafting start message
        await _bot_controller.chat(f"Crafting {count} {name}")
        
        # Call internal method
        response = await _bot_controller.craft_item(name, count)
        
        # Convert to ADK dictionary
        result = {
            "status": response.status,
            "item": name,
            "requested": count
        }
        
        if response.status == "success":
            result["crafted"] = response.count_crafted or count
            
            # Send completion message
            await _bot_controller.chat(f"Crafted {result['crafted']} {name}")
            
            # Update state
            if tool_context:
                tool_context.state["task.craft.result"] = {
                    "item": name,
                    "count": result["crafted"],
                    "success": True
                }
                
        elif response.error_details:
            result["error"] = response.error_details.message
            if response.error_details.suggestion:
                result["suggestion"] = response.error_details.suggestion
                
            # Update state
            if tool_context:
                tool_context.state["task.craft.result"] = {
                    "item": name,
                    "count": 0,
                    "success": False,
                    "error": response.error_details.message
                }
        
        return result
        
    except Exception as e:
        logger.error(f"Craft item error: {e}")
        return {"status": "error", "error": str(e)}


async def find_blocks(
    block_type: str,
    max_distance: Optional[int] = 32,
    count: Optional[int] = 10,
    tool_context: Optional[ToolContext] = None
) -> Dict[str, Any]:
    """Find blocks of a specific type near the bot.

    Args:
        block_type: Type of block to find
        max_distance: Maximum search distance
        count: Maximum number of blocks to return
        tool_context: Optional tool context

    Returns:
        Dict with found blocks
    """
    if not _bot_controller:
        return {"status": "error", "error": "BotController not initialized"}

    try:
        # Validate block type
        if _mc_data_service:
            block_data = _mc_data_service.get_block_by_name(block_type)
            if not block_data:
                # Try fuzzy matching
                all_blocks = [b['name'] for b in _mc_data_service.mc_data.blocks_list]
                similar = [b for b in all_blocks if block_type.lower() in b.lower()]
                
                if similar:
                    return {
                        "status": "error",
                        "error": f"Unknown block type: {block_type}",
                        "suggestion": f"Did you mean: {', '.join(similar[:5])}"
                    }
                else:
                    return {
                        "status": "error",
                        "error": f"Unknown block type: {block_type}"
                    }

        # Execute find blocks command
        result = await _bot_controller.bridge.execute_command(
            "findBlocks",
            block_type=block_type,
            max_distance=max_distance,
            count=count
        )
        
        if isinstance(result, list):
            # Format blocks for return
            blocks = []
            for block in result:
                blocks.append({
                    "x": block["x"],
                    "y": block["y"],
                    "z": block["z"],
                    "distance": block.get("distance", 0)
                })
            
            # Update state
            if tool_context:
                tool_context.state["minecraft.nearby_blocks"] = {
                    block_type: blocks,
                    "last_updated": __import__("time").time()
                }
            
            return {
                "status": "success",
                "block_type": block_type,
                "blocks": blocks,
                "count": len(blocks)
            }
        else:
            return {
                "status": "error",
                "error": f"Failed to find blocks: {result}"
            }
            
    except Exception as e:
        logger.error(f"Find blocks error: {e}")
        return {"status": "error", "error": str(e)}


async def send_chat(message: str, tool_context: Optional[ToolContext] = None) -> Dict[str, Any]:
    """Send a chat message.

    Args:
        message: Message to send
        tool_context: Optional tool context

    Returns:
        Dict with send result
    """
    if not _bot_controller:
        return {"status": "error", "error": "BotController not initialized"}

    try:
        result = await _bot_controller.chat(message)
        
        # Update state
        if tool_context:
            if "minecraft.chat_history" not in tool_context.state:
                tool_context.state["minecraft.chat_history"] = []
            
            tool_context.state["minecraft.chat_history"].append({
                "message": message,
                "timestamp": __import__("time").time(),
                "type": "sent"
            })
        
        return result
        
    except Exception as e:
        logger.error(f"Send chat error: {e}")
        return {"status": "error", "error": str(e)}


# Tool registration helpers
def get_all_tools():
    """Get all available mineflayer tools for registration"""
    return {
        "move_to": move_to,
        "dig_block": dig_block,
        "place_block": place_block,
        "get_inventory": get_inventory,
        "check_inventory": check_inventory,
        "get_position": get_position,
        "craft_item": craft_item,
        "find_blocks": find_blocks,
        "send_chat": send_chat
    }


def create_mineflayer_tools(bot_controller: BotController, mc_data_service: MinecraftDataService):
    """Create mineflayer tools with initialized services"""
    # Set global references
    set_bot_controller(bot_controller)
    set_minecraft_data_service(mc_data_service)
    
    # Return tool functions
    return [
        move_to,
        dig_block,
        place_block,
        get_inventory,
        check_inventory,
        get_position,
        craft_item,
        find_blocks,
        send_chat
    ]