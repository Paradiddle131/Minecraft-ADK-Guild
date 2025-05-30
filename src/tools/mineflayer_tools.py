"""
Mineflayer Tools for Google ADK - Wraps Minecraft bot commands as ADK tools
"""
import asyncio
import math
from typing import Any, Dict, List, Optional

from google.adk.tools import ToolContext

from ..logging_config import get_logger
from ..minecraft_bot_controller import BotController
from ..minecraft_data_service import MinecraftDataService

logger = get_logger(__name__)

# Global references for tool functions
_bot_controller: Optional[BotController] = None
_mc_data_service: Optional[MinecraftDataService] = None


async def _send_movement_progress_updates(
    bot_controller: BotController, target: Dict[str, float], start_pos: Dict[str, float], start_distance: float
) -> None:
    """Send periodic progress updates during movement

    Args:
        bot_controller: The bot controller instance
        target: Target position dict with x, y, z
        start_pos: Starting position dict with x, y, z
        start_distance: Initial distance to target
    """
    last_distance = start_distance
    update_interval = 5.0  # 5 seconds between updates
    update_count = 0
    max_updates = 12  # Maximum 12 updates (60 seconds total)
    stuck_count = 0  # Track how many times we haven't moved
    stuck_threshold = 3  # Consider stuck after 3 updates with no progress

    try:
        logger.info(f"Progress update task starting for movement to ({target['x']}, {target['y']}, {target['z']})")

        # Send immediate test message to verify chat is working
        test_message = f"Progress tracking started for movement to ({target['x']}, {target['y']}, {target['z']})"
        logger.info(f"Sending test message: {test_message}")
        try:
            await bot_controller.chat(test_message)
            logger.info("Test message sent successfully")
        except Exception as e:
            logger.error(f"Failed to send test message: {e}")
            return

        # Send first progress update immediately
        logger.info("Sending first progress update immediately")
        try:
            current_pos = await bot_controller.get_position()
            distance_to_target = math.sqrt(
                (target["x"] - current_pos["x"]) ** 2
                + (target["y"] - current_pos["y"]) ** 2
                + (target["z"] - current_pos["z"]) ** 2
            )
            first_message = f"Navigation started - {distance_to_target:.1f} blocks to go"
            await bot_controller.chat(first_message)
            logger.info(f"First progress update sent: {first_message}")
        except Exception as e:
            logger.error(f"Failed to send first progress update: {e}")

        while update_count < max_updates:
            logger.info(f"Progress update loop iteration {update_count + 1}")
            await asyncio.sleep(update_interval)
            update_count += 1

            try:
                # Check if bot is still connected
                if not bot_controller.bridge_manager_instance.is_connected:
                    logger.warning("Bot disconnected, stopping progress updates")
                    break

                # Get current position
                current_pos = await bot_controller.get_position()
                logger.info(f"Progress update {update_count}: current position {current_pos}")

                # Calculate distance to target
                distance_to_target = math.sqrt(
                    (target["x"] - current_pos["x"]) ** 2
                    + (target["y"] - current_pos["y"]) ** 2
                    + (target["z"] - current_pos["z"]) ** 2
                )

                # Calculate progress
                progress_made = start_distance - distance_to_target
                progress_percent = (progress_made / start_distance) * 100 if start_distance > 0 else 0

                # Send progress update
                if abs(last_distance - distance_to_target) < 0.5 and last_distance != start_distance:
                    # Not making much progress, might be stuck
                    stuck_count += 1
                    if stuck_count >= stuck_threshold:
                        message = f"Navigation appears stuck at {distance_to_target:.1f} blocks - may need manual help"
                    else:
                        message = f"Navigation progress: {distance_to_target:.1f} blocks remaining (might be finding path around obstacles)"
                else:
                    # Normal progress update - reset stuck counter
                    stuck_count = 0
                    message = f"Moving... {distance_to_target:.1f} blocks remaining ({progress_percent:.0f}% complete)"

                logger.info(f"About to send progress update: {message}")
                await bot_controller.chat(message)
                logger.info(f"Progress update {update_count} sent successfully, stuck_count={stuck_count}")

                last_distance = distance_to_target

                # If we've been stuck too long, stop sending updates
                if stuck_count >= stuck_threshold + 2:
                    logger.warning(f"Bot appears stuck after {stuck_count} updates, stopping progress reporting")
                    break

                # Stop if we're very close to target (within 2 blocks)
                if distance_to_target < 2:
                    logger.info("Progress updates stopping - close to target")
                    break

            except Exception as e:
                # Don't let position errors stop progress updates
                logger.error(f"Error in progress update {update_count}: {e}", exc_info=True)
                message = f"Navigation in progress... (update {update_count})"
                logger.info(f"Sending fallback progress update: {message}")
                try:
                    await bot_controller.chat(message)
                    logger.info(f"Fallback progress update {update_count} sent successfully")
                except Exception as chat_error:
                    logger.error(f"Failed to send fallback message: {chat_error}")

    except asyncio.CancelledError:
        # Task was cancelled, this is expected when movement completes
        logger.info("Progress update task cancelled")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in progress update task: {e}", exc_info=True)
        raise


def _set_bot_controller(controller: BotController):
    """Set the global bot controller for tool functions"""
    global _bot_controller
    _bot_controller = controller


def _set_minecraft_data_service(mc_data: MinecraftDataService):
    """Set the global minecraft data service for tool functions"""
    global _mc_data_service
    _mc_data_service = mc_data


async def move_to(
    x: int, y: int, z: int, timeout: Optional[int] = None, tool_context: Optional[ToolContext] = None
) -> Dict[str, Any]:
    """Move bot to specified coordinates using pathfinding.

    Enhanced version that uses BotController and provides additional context.

    Args:
        x: Target X coordinate
        y: Target Y coordinate
        z: Target Z coordinate
        timeout: Maximum time in milliseconds to wait for movement (default from env var)

    Returns:
        Dictionary with movement result including actual final position
    """
    if not _bot_controller:
        return {"status": "error", "error": "BotController not initialized"}

    # Use config for default timeout
    if timeout is None:
        # Get timeout from config if available
        try:
            from ..config import get_config

            config = get_config()
            timeout = config.pathfinder_timeout_ms
        except Exception:
            # Fallback to 30 seconds if config fails
            timeout = 30000

    try:
        # Get current position for distance calculation
        current_pos = await _bot_controller.get_position()
        start_distance = (
            (x - current_pos["x"]) ** 2 + (y - current_pos["y"]) ** 2 + (z - current_pos["z"]) ** 2
        ) ** 0.5

        logger.info(f"Starting movement to ({x}, {y}, {z}), distance: {start_distance:.1f}")

        # Send initial position report to chat
        initial_message = (
            f"I'm at ({int(current_pos['x'])}, {int(current_pos['y'])}, {int(current_pos['z'])}) "
            f"and I'm on my way to ({x}, {y}, {z}). Distance: {start_distance:.1f} blocks"
        )
        await _bot_controller.chat(initial_message)

        # Store movement start in state
        if tool_context and hasattr(tool_context, "state"):
            tool_context.state["temp:movement_in_progress"] = {
                "target": {"x": x, "y": y, "z": z},
                "start_position": current_pos,
                "start_time": __import__("time").time(),
                "start_distance": start_distance,
            }

        # Start progress updates immediately for distances > 5 blocks
        progress_task = None
        if start_distance > 5:  # Only create progress updates for distances > 5 blocks
            # Send confirmation message
            await asyncio.sleep(0.1)  # Small delay to ensure initial message is sent
            await _bot_controller.chat(f"Starting navigation to ({x}, {y}, {z}) - will update every 5 seconds...")

            # Create progress update task
            try:
                progress_task = asyncio.create_task(
                    _send_movement_progress_updates(
                        _bot_controller, {"x": x, "y": y, "z": z}, current_pos, start_distance
                    )
                )
                logger.info(f"Created progress update task for movement to ({x}, {y}, {z})")
            except Exception as e:
                logger.error(f"Failed to create progress update task: {e}")
                progress_task = None

        try:
            # Use BotController for movement, passing the timeout
            result = await _bot_controller.move_to(x, y, z, timeout=timeout)

            # Cancel progress updates once movement is complete
            if progress_task and not progress_task.done():
                logger.info("Cancelling progress update task - movement completed")
                progress_task.cancel()
                try:
                    await progress_task
                except asyncio.CancelledError:
                    logger.debug("Progress update task cancelled successfully")
                    pass

            # Update state based on result
            if result.get("status") == "success":
                # Get actual position after movement
                actual_pos = await _bot_controller.get_position()

                # Send completion message
                await _bot_controller.chat(
                    f"Arrived at ({int(actual_pos['x'])}, {int(actual_pos['y'])}, {int(actual_pos['z'])})"
                )

                # Update position in state
                if tool_context and hasattr(tool_context, "state"):
                    tool_context.state["minecraft_position"] = {
                        "x": actual_pos["x"],
                        "y": actual_pos["y"],
                        "z": actual_pos["z"],
                        "timestamp": __import__("time").time(),
                    }
                    tool_context.state["temp:movement_in_progress"] = None

                return {
                    "status": "success",
                    "target_position": {"x": x, "y": y, "z": z},
                    "actual_position": actual_pos,
                    "distance_traveled": start_distance,
                }
            else:
                # Movement failed
                if progress_task and not progress_task.done():
                    logger.info("Cancelling progress update task - movement failed")
                    progress_task.cancel()
                    try:
                        await progress_task
                    except asyncio.CancelledError:
                        logger.debug("Progress update task cancelled after movement failure")
                        pass

                # Check if it's a timeout error
                error_msg = result.get("error", "")
                if "timeout" in error_msg.lower():
                    # It's a timeout - get current position for reporting
                    try:
                        actual_pos = await _bot_controller.get_position()
                    except Exception:
                        actual_pos = {"x": 0, "y": 0, "z": 0}

                    # Send specific timeout message
                    await _bot_controller.chat(
                        f"Movement timed out after {timeout}ms. Try again or increase the timeout."
                    )

                    return {
                        "status": "error",
                        "error": f"Movement command timed out after {timeout}ms",
                        "target_position": {"x": x, "y": y, "z": z},
                        "actual_position": actual_pos,
                        "timeout_ms": timeout,
                        "suggestion": "Either call the movement command again or increase MINECRAFT_AGENT_PATHFINDER_TIMEOUT_MS",
                    }
                else:
                    # Other failure
                    await _bot_controller.chat("Movement failed - couldn't reach destination")
                    return result

        except Exception:
            # Cancel progress task on any error
            if progress_task and not progress_task.done():
                logger.info("Cancelling progress update task - exception occurred")
                progress_task.cancel()
                try:
                    await progress_task
                except asyncio.CancelledError:
                    logger.debug("Progress update task cancelled after exception")
                    pass
            raise

    except Exception as e:
        logger.error(f"Movement failed: {e}")
        return {"status": "error", "error": str(e)}


async def dig_block(x: int, y: int, z: int, tool_context: Optional[ToolContext] = None) -> Dict[str, Any]:
    """Dig a block at specified coordinates.

    Enhanced version that provides block information from MinecraftDataService.

    Args:
        x: Block X coordinate
        y: Block Y coordinate
        z: Block Z coordinate

    Returns:
        Dictionary with dig result and block information
    """
    if not _bot_controller:
        return {"status": "error", "error": "BotController not initialized"}

    try:
        # Get block information first
        block_info = await _bot_controller.get_block_at(x, y, z)
        block_name = block_info.get("name", "unknown")

        if block_name == "air":
            return {"status": "error", "error": "No block to dig at this position"}

        # Get additional block data from MinecraftDataService
        block_data = None
        if _mc_data_service and block_name != "unknown":
            block_data = _mc_data_service.get_block_by_name(block_name)

        logger.info(f"Digging {block_name} at ({x}, {y}, {z})")

        # Start digging
        result = await _bot_controller.start_digging([x, y, z])

        if result.get("status") == "success":
            response = {"status": "success", "block": block_name, "position": {"x": x, "y": y, "z": z}}

            # Add enriched block data if available
            if block_data:
                response["block_data"] = {
                    "hardness": block_data.get("hardness", 0),
                    "material": block_data.get("material", "unknown"),
                    "drops": block_data.get("drops", []),
                }

            return response
        else:
            return result

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

    Enhanced version that validates blocks using MinecraftDataService and uses BotController.

    Args:
        x: Reference block X coordinate
        y: Reference block Y coordinate
        z: Reference block Z coordinate
        block_type: Type of block to place
        face: Which face of the reference block to place against

    Returns:
        Dictionary with place result and block information
    """
    if not _bot_controller:
        return {"status": "error", "error": "BotController not initialized"}

    try:
        # Normalize and validate block type using MinecraftDataService
        normalized_block = block_type
        block_data = None
        if _mc_data_service:
            block_data = _mc_data_service.get_block_by_name(block_type)
            if not block_data:
                # Try to find similar block names
                all_blocks = _mc_data_service.get_all_blocks()
                similar_blocks = [b for b in all_blocks if block_type.lower() in b.get("name", "").lower()]
                if similar_blocks:
                    return {
                        "status": "error",
                        "error": f"Block '{block_type}' not found. Similar blocks: {[b['name'] for b in similar_blocks[:3]]}",
                    }
                else:
                    return {"status": "error", "error": f"Unknown block type: {block_type}"}
            else:
                normalized_block = block_data.get("name", block_type)

        # Check inventory for the block
        inventory = await _bot_controller.get_inventory_items()
        has_block = any(item["name"] == normalized_block for item in inventory)

        if not has_block:
            # Check for alternative block names in inventory
            inventory_names = [item["name"] for item in inventory]
            return {
                "status": "error",
                "error": f"No {normalized_block} in inventory. Available blocks: {[name for name in inventory_names if 'block' in name.lower() or any(material in name for material in ['wood', 'stone', 'dirt', 'sand'])]}",
                "inventory_blocks": [name for name in inventory_names if "block" in name.lower()],
            }

        # Convert face string to face vector for BotController
        face_vectors = {
            "top": [0, 1, 0],
            "bottom": [0, -1, 0],
            "north": [0, 0, -1],
            "south": [0, 0, 1],
            "east": [1, 0, 0],
            "west": [-1, 0, 0],
        }
        face_vector = face_vectors.get(face.lower(), [0, 1, 0])  # Default to top

        # Equip the block
        equip_result = await _bot_controller.equip_item(normalized_block, "hand")
        if equip_result.get("status") != "success":
            return {
                "status": "error",
                "error": f"Failed to equip {normalized_block}: {equip_result.get('error', 'Unknown error')}",
            }

        # Place the block using BotController
        place_result = await _bot_controller.place_block([x, y, z], face_vector)

        if place_result.get("status") == "success":
            logger.info(f"Placed {normalized_block} at ({x}, {y}, {z}) on {face} face")

            response = {
                "status": "success",
                "block": normalized_block,
                "position": {"x": x, "y": y, "z": z},
                "face": face,
                "face_vector": face_vector,
            }

            # Add enriched block data if available
            if block_data:
                response["block_data"] = {
                    "hardness": block_data.get("hardness", 0),
                    "material": block_data.get("material", "unknown"),
                    "stack_size": block_data.get("stackSize", 64),
                    "transparent": block_data.get("transparent", False),
                }

            return response
        else:
            return place_result

    except Exception as e:
        logger.error(f"Place failed: {e}")
        return {"status": "error", "error": str(e)}


async def get_position(tool_context=None) -> Dict[str, Any]:
    """Get the bot's current position in the world.

    Enhanced version that uses BotController.

    Args:
        tool_context: Optional ADK tool context for state management

    Returns:
        Dictionary with bot's coordinates
    """
    if not _bot_controller:
        return {"status": "error", "error": "BotController not initialized"}

    try:
        position = await _bot_controller.get_position()

        if position:
            return {
                "status": "success",
                "position": position,
                "x": position.get("x"),
                "y": position.get("y"),
                "z": position.get("z"),
            }
        else:
            return {"status": "error", "error": "Unable to get position"}

    except Exception as e:
        logger.error(f"Error getting position: {e}")
        return {"status": "error", "error": str(e)}


async def get_movement_status(tool_context: Optional[ToolContext] = None) -> Dict[str, Any]:
    """Check if the bot is currently moving and get movement details.

    Enhanced version that works with BotController and session state.

    Returns:
        Dictionary with movement status and details
    """
    if not _bot_controller:
        return {"status": "error", "error": "BotController not initialized"}

    try:
        # Get current position for movement detection
        current_pos = await _bot_controller.get_position()

        result = {"status": "success", "current_position": current_pos, "is_moving": False, "has_goal": False}

        # Check session state for movement tracking
        if tool_context and hasattr(tool_context, "state"):
            movement_progress = tool_context.state.get("temp:movement_in_progress")
            if movement_progress:
                # Calculate if we're still moving based on session state
                current_time = __import__("time").time()
                movement_duration = current_time - movement_progress["start_time"]
                start_position = movement_progress["start_position"]
                target = movement_progress["target"]

                # Calculate distance from start and to target
                distance_from_start = (
                    (current_pos["x"] - start_position["x"]) ** 2
                    + (current_pos["y"] - start_position["y"]) ** 2
                    + (current_pos["z"] - start_position["z"]) ** 2
                ) ** 0.5

                distance_to_target = (
                    (current_pos["x"] - target["x"]) ** 2
                    + (current_pos["y"] - target["y"]) ** 2
                    + (current_pos["z"] - target["z"]) ** 2
                ) ** 0.5

                # Consider moving if we haven't reached target and it's been recent
                result["is_moving"] = distance_to_target > 1.0 and movement_duration < 60  # 60 second timeout
                result["has_goal"] = True
                result["session_movement"] = {
                    "target": target,
                    "distance_to_target": distance_to_target,
                    "distance_from_start": distance_from_start,
                    "movement_duration": movement_duration,
                    "start_distance": movement_progress.get("start_distance", 0),
                }

                # Calculate movement progress
                if movement_progress.get("start_distance", 0) > 0:
                    progress_percent = min(100, (distance_from_start / movement_progress["start_distance"]) * 100)
                    result["session_movement"]["progress_percent"] = progress_percent

        # Try to get pathfinder status if available (fallback to bridge)
        try:
            bridge_manager = _bot_controller.bridge_manager_instance
            pathfinder_info = await bridge_manager.execute_command("pathfinder.isMoving")
            if pathfinder_info:
                result["pathfinder_status"] = {
                    "is_moving": pathfinder_info.get("isMoving", False),
                    "has_goal": pathfinder_info.get("goal") is not None,
                }
                # Override our detection with pathfinder if available
                result["is_moving"] = pathfinder_info.get("isMoving", result["is_moving"])
                result["has_goal"] = pathfinder_info.get("goal") is not None or result["has_goal"]

                if pathfinder_info.get("goal"):
                    result["pathfinder_goal"] = pathfinder_info["goal"]
        except Exception as pathfinder_error:
            logger.debug(f"Could not get pathfinder status: {pathfinder_error}")
            # Not a critical error, continue with session-based detection

        return result

    except Exception as e:
        logger.error(f"Error getting movement status: {e}")
        return {"status": "error", "error": str(e)}


async def find_blocks(
    block_name: str,
    max_distance: int,
    count: int,
    tool_context: Optional[ToolContext] = None,
) -> Dict[str, Any]:
    """Find blocks of a specific type near the bot.

    Enhanced version that validates blocks using MinecraftDataService and uses BotController.

    Args:
        block_name: Name of block to find (e.g. "oak_log", "stone")
        max_distance: Maximum search distance
        count: Maximum number of blocks to return

    Returns:
        Dictionary with found blocks and block information
    """
    if not _bot_controller:
        return {"status": "error", "error": "BotController not initialized"}

    try:
        # Normalize and validate block name using MinecraftDataService
        normalized_block = block_name
        block_data = None
        if _mc_data_service:
            block_data = _mc_data_service.get_block_by_name(block_name)
            if not block_data:
                # Try to find similar block names
                all_blocks = _mc_data_service.get_all_blocks()
                similar_blocks = [b for b in all_blocks if block_name.lower() in b.get("name", "").lower()]
                if similar_blocks:
                    logger.warning(
                        f"Block '{block_name}' not found, searching anyway. Similar blocks: {[b['name'] for b in similar_blocks[:3]]}"
                    )
                else:
                    logger.warning(f"Unknown block type '{block_name}', searching anyway")
            else:
                normalized_block = block_data.get("name", block_name)
                logger.info(f"Searching for {normalized_block} within {max_distance} blocks")

        # Use BotController to find blocks
        block_list = await _bot_controller.find_blocks(normalized_block, max_distance, count)

        # Convert JSPyBridge Proxy object to Python list if needed
        if not isinstance(block_list, list):
            if hasattr(block_list, "__len__"):
                # Already a Python object with len()
                block_list = list(block_list)
            else:
                # Proxy object - convert to list by iterating
                converted_list = []
                try:
                    # Try to iterate over the proxy object
                    for block in block_list:
                        converted_list.append(block)
                    block_list = converted_list
                except TypeError:
                    # If it's not iterable, it might be a single object or empty
                    if block_list:
                        block_list = [block_list]
                    else:
                        block_list = []

        response = {
            "status": "success",
            "block_type": normalized_block,
            "original_query": block_name,
            "count": len(block_list),
            "positions": block_list,
            "search_radius": max_distance,
        }

        # Add enriched block data if available
        if block_data:
            response["block_data"] = {
                "hardness": block_data.get("hardness", 0),
                "material": block_data.get("material", "unknown"),
                "drops": block_data.get("drops", []),
                "transparent": block_data.get("transparent", False),
            }

        logger.info(f"Found {len(block_list)} {normalized_block} blocks within {max_distance} blocks")
        return response

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

    Enhanced version that provides rich item information from MinecraftDataService.

    Returns:
        Dictionary with inventory items and enriched data
    """
    if not _bot_controller:
        return {"status": "error", "error": "BotController not initialized"}

    try:
        items = await _bot_controller.get_inventory_items()

        # Organize by item type with enhanced data
        inventory_summary = {}
        enriched_items = []
        item_categories = {
            "tools": [],
            "weapons": [],
            "armor": [],
            "blocks": [],
            "food": [],
            "materials": [],
            "other": [],
        }
        craftable_items = []

        for item in items:
            name = item["name"]
            count = item["count"]

            # Basic summary
            if name not in inventory_summary:
                inventory_summary[name] = 0
            inventory_summary[name] += count

            # Enrich with MinecraftDataService data
            enriched_item = item.copy()
            if _mc_data_service:
                item_data = _mc_data_service.get_item_by_name(name)
                if item_data:
                    enriched_item["item_data"] = {
                        "stack_size": item_data.get("stackSize", 64),
                        "max_durability": item_data.get("maxDurability", None),
                        "creative_tab": item_data.get("creative_tab", "misc"),
                        "material": item_data.get("material", "unknown"),
                    }

                    # Categorize items
                    if "sword" in name or "bow" in name or "crossbow" in name or "trident" in name:
                        item_categories["weapons"].append({"name": name, "count": count})
                    elif any(tool in name for tool in ["pickaxe", "axe", "shovel", "hoe", "shears"]):
                        item_categories["tools"].append({"name": name, "count": count})
                    elif any(armor in name for armor in ["helmet", "chestplate", "leggings", "boots"]):
                        item_categories["armor"].append({"name": name, "count": count})
                    elif any(
                        food in name for food in ["bread", "apple", "meat", "fish", "stew", "cake"]
                    ) or "food" in item_data.get("category", ""):
                        item_categories["food"].append({"name": name, "count": count})
                    elif "block" in item_data.get("type", "") or name.endswith("_block"):
                        item_categories["blocks"].append({"name": name, "count": count})
                    elif any(
                        material in name
                        for material in ["ingot", "gem", "dust", "nugget", "stick", "string", "leather"]
                    ):
                        item_categories["materials"].append({"name": name, "count": count})
                    else:
                        item_categories["other"].append({"name": name, "count": count})

                # Check what can be crafted with this item
                recipes = _mc_data_service.get_recipes_for_item_name(name)
                if recipes:
                    for recipe in recipes[:3]:  # Limit to first 3 recipes
                        result_item = recipe.get("result", {}).get("name", "unknown")
                        if result_item not in [c["result"] for c in craftable_items]:
                            craftable_items.append(
                                {
                                    "ingredient": name,
                                    "result": result_item,
                                    "result_count": recipe.get("result", {}).get("count", 1),
                                }
                            )

            enriched_items.append(enriched_item)

        # Calculate inventory statistics
        total_items = sum(item["count"] for item in items)
        unique_items = len(inventory_summary)

        # Identify valuable items
        valuable_items = []
        if _mc_data_service:
            for name, count in inventory_summary.items():
                item_data = _mc_data_service.get_item_by_name(name)
                if item_data:
                    # Consider items valuable if they're rare materials or tools
                    if any(valuable in name for valuable in ["diamond", "netherite", "gold", "emerald", "enchanted"]):
                        valuable_items.append({"name": name, "count": count, "type": "precious_material"})
                    elif item_data.get("maxDurability", 0) > 100:  # Durable tools/weapons
                        valuable_items.append({"name": name, "count": count, "type": "durable_tool"})

        result = {
            "status": "success",
            "items": enriched_items,
            "summary": inventory_summary,
            "statistics": {
                "total_items": total_items,
                "unique_items": unique_items,
                "inventory_slots_used": len(items),
            },
            "categories": {k: v for k, v in item_categories.items() if v},  # Only include non-empty categories
            "valuable_items": valuable_items,
            "craftable_with_inventory": craftable_items[:10],  # Limit to 10 most relevant
        }

        # Save structured inventory data to session state if tool_context is provided
        if tool_context and hasattr(tool_context, "state"):
            tool_context.state["minecraft_inventory"] = {
                "items": enriched_items,
                "summary": inventory_summary,
                "statistics": result["statistics"],
                "categories": result["categories"],
                "timestamp": __import__("time").time(),
            }
            logger.info("Saved enriched inventory data to session state")

        return result

    except Exception as e:
        logger.error(f"Inventory query failed: {e}")
        error_result = {"status": "error", "error": str(e)}

        # Save error state if tool_context is provided
        if tool_context and hasattr(tool_context, "state"):
            tool_context.state["minecraft_inventory"] = {"error": str(e), "timestamp": __import__("time").time()}

        return error_result


async def craft_item(recipe: str, count: int, tool_context: Optional[ToolContext] = None) -> Dict[str, Any]:
    """Craft an item using available materials with fully generic logic.

    Uses generic fuzzy matching and recipe selection without any hardcoded item handling.

    Args:
        recipe: Name of item to craft
        count: Number to craft

    Returns:
        Dictionary with craft result and recipe information
    """
    if not _bot_controller:
        return {"status": "error", "error": "BotController not initialized"}

    try:
        logger.info(f"Attempting to craft {count} {recipe}")

        # Get current inventory
        inventory = await _bot_controller.get_inventory_items()
        inventory_summary = {}
        for item in inventory:
            name = item["name"]
            inventory_summary[name] = inventory_summary.get(name, 0) + item["count"]

        # Generic item resolution
        normalized_recipe = recipe
        if _mc_data_service:
            # First try generic item request handler
            generic_result = _mc_data_service.handle_generic_item_request(recipe, inventory_summary)
            if generic_result:
                normalized_recipe = generic_result
                logger.info(f"Resolved generic '{recipe}' to specific '{normalized_recipe}'")
            else:
                # Use generic normalization and fuzzy matching
                normalized_recipe = _mc_data_service.normalize_item_name(recipe)
                if normalized_recipe == recipe:
                    # If normalization didn't change it, try fuzzy matching
                    fuzzy_match = _mc_data_service.fuzzy_match_item_name(recipe)
                    if fuzzy_match:
                        normalized_recipe = fuzzy_match
                        logger.info(f"Fuzzy matched '{recipe}' to '{normalized_recipe}'")

        # Generic recipe selection and validation
        recipe_data = None
        selected_recipe = None
        if _mc_data_service:
            # Use generic recipe selection algorithm
            selected_recipe = _mc_data_service.select_best_recipe(normalized_recipe, inventory_summary)

            if not selected_recipe:
                # No craftable recipe, get recipes for information
                recipes = _mc_data_service.get_recipes_for_item(normalized_recipe)
                if recipes:
                    recipe_data = recipes[0]
                else:
                    # Generic recipe suggestion using fuzzy matching
                    all_recipes = _mc_data_service.get_all_recipes()
                    suggestions = []

                    # Score all recipes by similarity to request
                    for r in all_recipes:
                        result_name = r.get("result", {}).get("name", "")
                        # Generic similarity check
                        similarity_score = 0

                        # Substring matching
                        if recipe.lower() in result_name.lower():
                            similarity_score += 0.5
                        if result_name.lower() in recipe.lower():
                            similarity_score += 0.3

                        # Word overlap
                        recipe_words = set(recipe.lower().split())
                        result_words = set(result_name.lower().replace("_", " ").split())
                        common_words = recipe_words & result_words
                        if common_words:
                            similarity_score += len(common_words) / max(len(recipe_words), len(result_words))

                        if similarity_score > 0.3:
                            suggestions.append((result_name, similarity_score))

                    if suggestions:
                        # Sort by score and take top suggestions
                        suggestions.sort(key=lambda x: x[1], reverse=True)
                        similar_recipes = [s[0] for s in suggestions[:10]]
                        return {
                            "status": "error",
                            "error": f"Recipe '{recipe}' not found. Similar recipes: {similar_recipes}",
                        }
                    else:
                        logger.warning(f"No recipe found for '{normalized_recipe}', attempting to craft anyway")
            else:
                recipe_data = selected_recipe
                logger.info(f"Selected best recipe for {normalized_recipe}")

        # Generic material validation
        missing_materials = {}
        if recipe_data and _mc_data_service:
            # Use generic recipe material extraction
            materials_needed = _mc_data_service.get_recipe_materials(recipe_data)
            result_count = recipe_data.get("result", {}).get("count", 1)
            batches_needed = (count + result_count - 1) // result_count

            # Generic material availability check
            for material, qty_per_batch in materials_needed.items():
                total_needed = qty_per_batch * batches_needed
                available = inventory_summary.get(material, 0)
                if available < total_needed:
                    missing_materials[material] = total_needed - available

            if missing_materials:
                response = {
                    "status": "error",
                    "error": f"Insufficient materials to craft {count} {normalized_recipe}",
                    "missing_materials": missing_materials,
                    "current_inventory": inventory_summary,
                    "recipe_info": {
                        "materials_per_craft": materials_needed,
                        "result_count": result_count,
                        "batches_needed": batches_needed,
                        "requires_crafting_table": _mc_data_service.needs_crafting_table(normalized_recipe),
                    },
                }
                return response

        # Execute craft command

        bridge_manager = _bot_controller.bridge_manager_instance
        result = await bridge_manager.execute_command("craft", recipe=normalized_recipe, count=count)

        # Generic result handling
        if result is None:
            logger.error("Craft command returned None")
            return {
                "status": "error",
                "error": "Craft command failed - no response from bot",
                "recipe_attempted": normalized_recipe,
            }

        # Generic proxy/dict result extraction
        success = False
        crafted_count = 0
        error_msg = None

        # Try to extract result generically
        if hasattr(result, "__dict__"):
            # Object with attributes
            for success_key in ["success", "successful", "ok", "done"]:
                if hasattr(result, success_key):
                    success = getattr(result, success_key)
                    break
            for count_key in ["crafted", "count", "amount", "quantity"]:
                if hasattr(result, count_key):
                    crafted_count = getattr(result, count_key)
                    break
            for error_key in ["error", "message", "msg", "reason"]:
                if hasattr(result, error_key):
                    error_msg = getattr(result, error_key)
                    break
        elif isinstance(result, dict):
            # Dictionary result
            for success_key in ["success", "successful", "ok", "done"]:
                if success_key in result:
                    success = result[success_key]
                    break
            for count_key in ["crafted", "count", "amount", "quantity"]:
                if count_key in result:
                    crafted_count = result[count_key]
                    break
            for error_key in ["error", "message", "msg", "reason"]:
                if error_key in result:
                    error_msg = result[error_key]
                    break

        if success:
            logger.info(f"Successfully crafted {crafted_count} {normalized_recipe}")
            response = {
                "status": "success",
                "crafted": normalized_recipe,
                "count": crafted_count,
                "original_request": recipe,
            }

            # Add generic recipe data if available
            if recipe_data and _mc_data_service:
                materials = _mc_data_service.get_recipe_materials(recipe_data)
                response["recipe_data"] = {
                    "materials": materials,
                    "result_count": recipe_data.get("result", {}).get("count", 1),
                    "requires_crafting_table": _mc_data_service.needs_crafting_table(normalized_recipe),
                }

            return response
        else:
            # Crafting failed
            if not error_msg:
                error_msg = f"Failed to craft {normalized_recipe}"

            response = {
                "status": "error",
                "error": error_msg,
                "recipe_attempted": normalized_recipe,
                "current_inventory": inventory_summary,
            }

            # Add generic recipe info for debugging
            if recipe_data and _mc_data_service:
                materials = _mc_data_service.get_recipe_materials(recipe_data)
                response["recipe_info"] = {
                    "required_materials": materials,
                    "result_count": recipe_data.get("result", {}).get("count", 1),
                    "requires_crafting_table": _mc_data_service.needs_crafting_table(normalized_recipe),
                }
                # Generic material shortage calculation
                missing = {}
                for mat, qty in materials.items():
                    if inventory_summary.get(mat, 0) < qty:
                        missing[mat] = qty - inventory_summary.get(mat, 0)
                if missing:
                    response["missing_materials"] = missing

            return response

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Crafting exception: {error_msg}", exc_info=True)

        response = {"status": "error", "error": f"Crafting failed: {error_msg}", "recipe_attempted": recipe}

        # Generic recipe suggestions on error
        if _mc_data_service:
            try:
                all_recipes = _mc_data_service.get_all_recipes()
                suggestions = []

                # Generic word-based suggestion algorithm
                recipe_words = set(recipe.lower().replace("_", " ").split())
                for r in all_recipes:
                    result_name = r.get("result", {}).get("name", "")
                    result_words = set(result_name.lower().replace("_", " ").split())

                    # Calculate word overlap score
                    common_words = recipe_words & result_words
                    if common_words:
                        score = len(common_words) / max(len(recipe_words), len(result_words))
                        if score > 0.2:
                            suggestions.append((result_name, score))

                if suggestions:
                    suggestions.sort(key=lambda x: x[1], reverse=True)
                    response["suggested_recipes"] = [s[0] for s in suggestions[:10]]
            except Exception as suggest_error:
                logger.debug(f"Could not get recipe suggestions: {suggest_error}")

        return response


async def send_chat(message: str, tool_context: Optional[ToolContext] = None) -> Dict[str, Any]:
    """Send a chat message.

    Enhanced version that uses BotController.

    Args:
        message: Message to send

    Returns:
        Dictionary with send result
    """
    if not _bot_controller:
        return {"status": "error", "error": "BotController not initialized"}

    try:
        result = await _bot_controller.chat(message)

        if result.get("status") == "success":
            return {"status": "success", "message": message}
        else:
            return result

    except Exception as e:
        logger.error(f"Chat failed: {e}")
        return {"status": "error", "error": str(e)}


def create_mineflayer_tools(bot_controller: BotController, mc_data_service: MinecraftDataService) -> List:
    """Create enhanced Mineflayer tools with BotController and MinecraftDataService integration.

    Args:
        bot_controller: BotController instance
        mc_data_service: MinecraftDataService instance

    Returns:
        List of tool functions (ADK will automatically wrap them)
    """
    # Set the global references
    _set_bot_controller(bot_controller)
    _set_minecraft_data_service(mc_data_service)

    # Return list of tool functions - ADK automatically creates FunctionTool objects
    return [
        move_to,
        dig_block,
        place_block,
        get_position,
        get_movement_status,
        find_blocks,
        get_nearby_players,
        get_inventory,
        craft_item,
        send_chat,
    ]
