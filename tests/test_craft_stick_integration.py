#!/usr/bin/env python3
"""Test the complete flow of crafting a stick with empty inventory"""

import asyncio
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.logging_config import get_logger

logger = get_logger(__name__)


async def test_craft_stick_flow():
    """Test the complete multi-agent flow for crafting a stick"""

    logger.info("Testing craft stick flow with multi-agent system")

    # Use subprocess to run the command
    import subprocess

    # Test command
    test_command = ["python", "main.py", "craft 1 stick"]

    try:
        # Run the main function
        logger.info(f"Executing command: {' '.join(test_command)}")
        result = subprocess.run(test_command, capture_output=True, text=True, timeout=60)

        logger.info("Command execution completed")
        logger.info(f"STDOUT:\n{result.stdout}")
        if result.stderr:
            logger.info(f"STDERR:\n{result.stderr}")

        # The result should show the coordination flow
        # 1. Coordinator → CrafterAgent (attempt to craft)
        # 2. CrafterAgent reports missing planks
        # 3. Coordinator → GathererAgent (gather logs)
        # 4. GathererAgent gathers logs
        # 5. Coordinator → CrafterAgent (craft planks)
        # 6. CrafterAgent crafts planks
        # 7. Coordinator → CrafterAgent (craft sticks)
        # 8. CrafterAgent crafts sticks

        return result.stdout

    except Exception as e:
        logger.error(f"Test failed with error: {e}", exc_info=True)
        raise


async def test_check_inventory_first():
    """Test that we check inventory before attempting to craft"""

    logger.info("Testing inventory check flow")

    import subprocess

    try:
        # First check inventory
        logger.info("Checking initial inventory...")
        result1 = subprocess.run(["python", "main.py", "check inventory"], capture_output=True, text=True, timeout=30)
        logger.info(f"Inventory check output:\n{result1.stdout}")

        # Now try to craft
        logger.info("Attempting to craft stick...")
        result2 = subprocess.run(["python", "main.py", "craft 1 stick"], capture_output=True, text=True, timeout=60)
        logger.info(f"Craft stick output:\n{result2.stdout}")

        return result1.stdout, result2.stdout

    except Exception as e:
        logger.error(f"Test failed with error: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    # Run tests
    logger.info("=" * 60)
    logger.info("Starting craft stick integration tests")
    logger.info("=" * 60)

    # Test 1: Check inventory first
    asyncio.run(test_check_inventory_first())

    logger.info("\n" + "=" * 60)

    # Test 2: Full craft flow
    asyncio.run(test_craft_stick_flow())

    logger.info("\n" + "=" * 60)
    logger.info("Tests completed")
