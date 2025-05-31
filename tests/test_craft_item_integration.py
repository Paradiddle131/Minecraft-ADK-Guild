#!/usr/bin/env python3
"""Test craft_item integration with python-minecraft-data."""

import asyncio
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.minecraft_data_service import MinecraftDataService


async def test_craft_scenarios():
    """Test various crafting scenarios."""

    # Initialize service
    service = MinecraftDataService("1.21.1")

    print("=== Testing Craft Item Scenarios ===\n")

    # Test scenarios
    scenarios = [
        {
            "name": "Craft sticks with oak planks",
            "item": "stick",
            "count": 16,
            "inventory": {"oak_planks": 10, "birch_log": 5},
        },
        {
            "name": "Craft sticks with insufficient materials",
            "item": "stick",
            "count": 32,
            "inventory": {"oak_planks": 4},
        },
        {
            "name": "Craft generic 'planks' request",
            "item": "planks",
            "count": 8,
            "inventory": {"birch_log": 3, "oak_log": 2},
        },
        {"name": "Craft with no materials", "item": "diamond_pickaxe", "count": 1, "inventory": {"stick": 2}},
        {"name": "Craft oak planks from logs", "item": "oak_planks", "count": 20, "inventory": {"oak_log": 6}},
    ]

    for scenario in scenarios:
        print(f"Scenario: {scenario['name']}")
        print(f"  Request: Craft {scenario['count']} {scenario['item']}")
        print(f"  Inventory: {scenario['inventory']}")

        # Handle generic requests
        item_name = scenario["item"]
        generic_result = service.handle_generic_item_request(item_name, scenario["inventory"])
        if generic_result:
            print(f"  Resolved '{item_name}' to '{generic_result}'")
            item_name = generic_result

        # Try to find best recipe
        best_recipe = service.select_best_recipe(item_name, scenario["inventory"])

        if best_recipe:
            materials = service.get_recipe_materials(best_recipe)
            result_count = best_recipe.get("result", {}).get("count", 1)
            batches_needed = (scenario["count"] + result_count - 1) // result_count

            print(f"  Selected recipe: {materials} -> {result_count} {item_name}")
            print(f"  Batches needed: {batches_needed}")

            # Check materials
            missing = {}
            for mat, qty in materials.items():
                total_needed = qty * batches_needed
                available = scenario["inventory"].get(mat, 0)
                if available < total_needed:
                    missing[mat] = total_needed - available

            if missing:
                print(f"  Missing materials: {missing}")
                print("  Result: CANNOT CRAFT")
            else:
                print("  Result: CAN CRAFT")
        else:
            # No craftable recipe, try to get any recipe for info
            recipes = service.get_recipes_for_item(item_name)
            if recipes:
                recipe = recipes[0]
                materials = service.get_recipe_materials(recipe)
                print(f"  Recipe exists: {materials} -> {recipe.get('result', {}).get('count', 1)} {item_name}")
                print("  Result: INSUFFICIENT MATERIALS")
            else:
                print("  Result: NO RECIPE FOUND")

        print()


if __name__ == "__main__":
    asyncio.run(test_craft_scenarios())
