#!/usr/bin/env python
"""Debug movement between specific coordinates to test progress updates"""

import asyncio
import sys

from src.bridge.bridge_manager import BridgeManager
from src.config import get_config
from src.minecraft_bot_controller import BotController


async def test_movement_debug():
    """Test movement between specific coordinates with debug logging"""
    config = get_config()
    bridge_manager = BridgeManager(agent_config=config)
    bot_controller = BotController(bridge_manager)

    print("Initializing bridge manager...")
    await bridge_manager.initialize()
    print("Bridge manager initialized!")

    print("Bot connected and spawned!")

    # Wait a moment for bot to stabilize
    await asyncio.sleep(2)

    # Test coordinates from user
    start_pos = (-104, 64, -117)
    end_pos = (-156, 65, -198)

    print(f"Moving from {start_pos} to {end_pos}...")
    print("Should see progress updates in chat every 5 seconds...")

    try:
        # First move to start position
        print(f"Moving to start position {start_pos}...")
        result1 = await bot_controller.move_to(start_pos[0], start_pos[1], start_pos[2], timeout=30000)
        if result1.get("status") == "success":
            print("Reached start position!")

            # Wait a moment
            await asyncio.sleep(2)

            # Now move to end position (this should show progress updates)
            print(f"Moving to end position {end_pos}...")
            result2 = await bot_controller.move_to(end_pos[0], end_pos[1], end_pos[2], timeout=60000)

            if result2.get("status") == "success":
                print("Movement completed successfully!")
                final_pos = await bot_controller.get_position()
                print(f"Final position: ({final_pos['x']:.1f}, {final_pos['y']:.1f}, {final_pos['z']:.1f})")
            else:
                print(f"Movement failed: {result2.get('error')}")
        else:
            print(f"Failed to reach start position: {result1.get('error')}")

    except Exception as e:
        print(f"Error during movement: {e}")
        import traceback

        traceback.print_exc()

    # Cleanup
    await bridge_manager.close()
    print("Test completed!")


if __name__ == "__main__":
    try:
        asyncio.run(test_movement_debug())
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
        sys.exit(0)
