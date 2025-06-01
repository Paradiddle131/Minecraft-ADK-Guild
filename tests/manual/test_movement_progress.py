#!/usr/bin/env python
"""Test script to verify movement progress updates work entirely in JavaScript"""

import asyncio
import sys

from src.bridge.bridge_manager import BridgeManager
from src.config import get_config
from src.minecraft_bot_controller import BotController


async def test_movement_with_progress():
    """Test movement with progress updates handled in JavaScript"""
    config = get_config()
    bridge_manager = BridgeManager(config)
    bot_controller = BotController(bridge_manager, config)

    print("Initializing bot...")
    await bot_controller.initialize()
    print("Bot initialized and spawned!")

    # Wait a moment for bot to stabilize
    await asyncio.sleep(2)

    # Get current position
    pos = await bot_controller.get_position()
    print(f"Current position: ({pos['x']:.1f}, {pos['y']:.1f}, {pos['z']:.1f})")

    # Move to a location 30 blocks away (should trigger progress updates)
    target_x = int(pos["x"]) + 30
    target_y = int(pos["y"])
    target_z = int(pos["z"])

    print(f"\nMoving to ({target_x}, {target_y}, {target_z})...")
    print("Progress updates should appear in chat every 5 seconds...")

    try:
        result = await bot_controller.move_to(target_x, target_y, target_z, timeout=60000)
        if result.get("status") == "success":
            print("\nMovement completed successfully!")
            final_pos = await bot_controller.get_position()
            print(f"Final position: ({final_pos['x']:.1f}, {final_pos['y']:.1f}, {final_pos['z']:.1f})")
        else:
            print(f"\nMovement failed: {result.get('error')}")
    except Exception as e:
        print(f"\nError during movement: {e}")

    # Cleanup
    await bridge_manager.disconnect()
    print("\nTest completed!")


if __name__ == "__main__":
    try:
        asyncio.run(test_movement_with_progress())
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
        sys.exit(0)
