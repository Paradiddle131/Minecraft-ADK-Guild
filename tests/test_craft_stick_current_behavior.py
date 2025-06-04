#!/usr/bin/env python3
"""Test current behavior of craft stick command to establish baseline"""

import asyncio
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.logging_config import get_logger

logger = get_logger(__name__)


async def test_current_craft_stick_behavior():
    """Document the current behavior when attempting to craft a stick"""

    import subprocess

    logger.info("Testing current behavior: craft 1 stick with empty inventory")

    # Run the command and capture output
    result = subprocess.run(["python", "main.py", "craft 1 stick"], capture_output=True, text=True, timeout=30)

    # Parse the output to understand the flow
    output_lines = result.stdout.split("\n")

    # Look for key events
    events = {
        "coordinator_starts": False,
        "transfers_to_crafter": False,
        "crafter_checks_inventory": False,
        "crafter_attempts_craft": False,
        "crafter_reports_missing": False,
        "coordinator_completes": False,
        "final_message": None,
    }

    for line in output_lines:
        if "AGENT STARTING: CoordinatorAgent" in line:
            events["coordinator_starts"] = True
        elif ("CrafterAgent" in line and "Tool:" in line) or "AGENT STARTING: CrafterAgent" in line:
            events["transfers_to_crafter"] = True
        elif "AGENT STARTING: CrafterAgent" in line:
            events["crafter_starts"] = True
        elif "Tool: get_inventory" in line:
            events["crafter_checks_inventory"] = True
        elif "Tool: craft_item" in line:
            events["crafter_attempts_craft"] = True
        elif "Need" in line and "to craft stick" in line:
            events["crafter_reports_missing"] = True
            # Extract the final message
            events["final_message"] = line.strip()
        elif "AGENT COMPLETE: CoordinatorAgent" in line:
            events["coordinator_completes"] = True

    # Report findings
    logger.info("\n=== CURRENT BEHAVIOR ANALYSIS ===")
    logger.info(f"1. Coordinator starts: {events['coordinator_starts']}")
    logger.info(f"2. Transfers to CrafterAgent: {events['transfers_to_crafter']}")
    logger.info(f"3. Crafter checks inventory: {events['crafter_checks_inventory']}")
    logger.info(f"4. Crafter attempts craft: {events['crafter_attempts_craft']}")
    logger.info(f"5. Crafter reports missing materials: {events['crafter_reports_missing']}")
    logger.info(f"6. Coordinator completes: {events['coordinator_completes']}")
    logger.info(f"7. Final message: {events['final_message']}")

    # Current behavior observations
    logger.info("\n=== OBSERVATIONS ===")
    logger.info("Current behavior:")
    logger.info("- Coordinator correctly uses CrafterAgent tool")
    logger.info("- CrafterAgent checks inventory and attempts to craft")
    logger.info("- CrafterAgent reports missing materials")
    logger.info("- Coordinator does NOT continue after receiving missing materials report")
    logger.info("- System ends with 'Need bamboo to craft stick' message")

    logger.info("\n=== DESIRED BEHAVIOR ===")
    logger.info("What should happen:")
    logger.info("1. Coordinator uses CrafterAgent tool")
    logger.info("2. CrafterAgent reports missing materials (e.g., planks)")
    logger.info("3. Coordinator recognizes this and uses GathererAgent tool")
    logger.info("4. GathererAgent gathers logs")
    logger.info("5. Coordinator uses CrafterAgent tool again")
    logger.info("6. CrafterAgent crafts planks from logs")
    logger.info("7. CrafterAgent crafts sticks from planks")
    logger.info("8. Coordinator reports success to user")

    return events


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("Testing Current Craft Stick Behavior")
    logger.info("=" * 60)

    events = asyncio.run(test_current_craft_stick_behavior())

    logger.info("\n" + "=" * 60)
    logger.info("Test completed")

    # Assert current behavior
    assert events["coordinator_starts"], "Coordinator should start"
    assert events["transfers_to_crafter"], "Should use CrafterAgent tool"
    assert events["crafter_checks_inventory"], "Crafter should check inventory"
    assert events["crafter_attempts_craft"], "Crafter should attempt to craft"
    assert events["crafter_reports_missing"], "Crafter should report missing materials"
    assert events["coordinator_completes"], "Coordinator should complete"

    # The issue: Coordinator doesn't continue after missing materials
    logger.info("\nCURRENT ISSUE: Coordinator ends after CrafterAgent reports missing materials")
    logger.info("NEEDED: Multi-step coordination to gather materials and retry crafting")
