#!/usr/bin/env python3
"""Test MinecraftDataService functionality"""
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.minecraft_data_service import MinecraftDataService


def test_basic_lookups():
    """Test basic item and block lookups"""
    service = MinecraftDataService("1.21.1")
    
    print("=== Testing basic lookups ===")
    
    # Test block lookup
    stone = service.get_block_by_name('stone')
    assert stone is not None, "Stone block should exist"
    assert stone['name'] == 'stone', "Stone block name should match"
    assert stone['id'] == 1, "Stone block ID should be 1"
    print(f"✓ Stone block: ID={stone['id']}, hardness={stone.get('hardness', 'N/A')}")
    
    # Test item lookup
    stick = service.get_item_by_name('stick')
    assert stick is not None, "Stick item should exist"
    assert stick['name'] == 'stick', "Stick item name should match"
    print(f"✓ Stick item: ID={stick['id']}, stackSize={stick.get('stackSize', 64)}")
    
    # Test non-existent item
    fake_item = service.get_item_by_name('fake_item_that_does_not_exist')
    assert fake_item is None, "Non-existent item should return None"
    print("✓ Non-existent item returns None")


def test_recipes():
    """Test recipe lookups"""
    service = MinecraftDataService("1.21.1")
    
    print("\n=== Testing recipes ===")
    
    # Test stick recipes
    stick_recipes = service.get_recipes_for_item_name('stick')
    assert len(stick_recipes) > 0, "Stick should have recipes"
    print(f"✓ Stick has {len(stick_recipes)} recipes")
    
    # Check first recipe structure
    first_recipe = stick_recipes[0]
    assert 'result' in first_recipe, "Recipe should have result"
    assert first_recipe['result']['count'] > 0, "Recipe should produce items"
    print(f"✓ First recipe produces {first_recipe['result']['count']} sticks")
    
    # Test item with no recipes
    stone_recipes = service.get_recipes_for_item_name('bedrock')
    assert len(stone_recipes) == 0, "Bedrock should have no recipes"
    print("✓ Bedrock has no recipes (as expected)")


def test_food_data():
    """Test food data lookups"""
    service = MinecraftDataService("1.21.1")
    
    print("\n=== Testing food data ===")
    
    # Test apple
    apple_food = service.get_food_points('apple')
    apple_sat = service.get_saturation('apple')
    assert apple_food == 4, "Apple should restore 4 food points"
    assert apple_sat == 2.4, "Apple should have 2.4 saturation"
    print(f"✓ Apple: {apple_food} food points, {apple_sat} saturation")
    
    # Test non-food item
    stone_food = service.get_food_points('stone')
    assert stone_food == 0, "Non-food items should return 0 food points"
    print("✓ Non-food items return 0 food points")


def test_crafting_table_requirement():
    """Test crafting table requirement checks"""
    service = MinecraftDataService("1.21.1")
    
    print("\n=== Testing crafting table requirement ===")
    
    # Items that can be crafted in inventory (2x2)
    assert service.needs_crafting_table('stick') == False, "Stick should be craftable in inventory"
    assert service.needs_crafting_table('oak_planks') == False, "Planks should be craftable in inventory"
    print("✓ Stick and planks can be crafted in inventory")
    
    # Items that need crafting table (3x3)
    assert service.needs_crafting_table('wooden_pickaxe') == True, "Pickaxe needs crafting table"
    assert service.needs_crafting_table('chest') == True, "Chest needs crafting table"
    print("✓ Pickaxe and chest need crafting table")


def test_normalization():
    """Test item name normalization"""
    service = MinecraftDataService("1.21.1")
    
    print("\n=== Testing normalization ===")
    
    # Test plural handling
    assert service.normalize_item_name('sticks') == 'stick', "Should normalize 'sticks' to 'stick'"
    print("✓ 'sticks' → 'stick'")
    
    # Test generic names
    assert service.normalize_item_name('planks') == 'oak_planks', "Should normalize 'planks' to 'oak_planks'"
    assert service.normalize_item_name('wood') == 'oak_log', "Should normalize 'wood' to 'oak_log'"
    print("✓ 'planks' → 'oak_planks', 'wood' → 'oak_log'")
    
    # Test unchanged names
    assert service.normalize_item_name('diamond') == 'diamond', "Should not change valid names"
    print("✓ Valid names remain unchanged")


def test_block_finding():
    """Test block finding functionality"""
    service = MinecraftDataService("1.21.1")
    
    print("\n=== Testing block finding ===")
    
    # Find blocks by name pattern
    log_blocks = service.find_blocks({'name_pattern': 'log'})
    assert len(log_blocks) > 0, "Should find blocks with 'log' in name"
    print(f"✓ Found {len(log_blocks)} blocks with 'log' in name")
    
    # Find blocks by hardness
    hard_blocks = service.find_blocks({'min_hardness': 50})
    assert all(b.get('hardness', 0) >= 50 for b in hard_blocks), "All blocks should have hardness >= 50"
    print(f"✓ Found {len(hard_blocks)} blocks with hardness >= 50")


def test_id_lookups():
    """Test lookups by numeric ID"""
    service = MinecraftDataService("1.21.1")
    
    print("\n=== Testing ID lookups ===")
    
    # Test block by ID
    stone_by_id = service.get_block_by_id(1)
    assert stone_by_id is not None, "Should find stone by ID 1"
    assert stone_by_id['name'] == 'stone', "Block ID 1 should be stone"
    print("✓ Block ID 1 is stone")
    
    # Test item by ID
    item_848 = service.get_item_by_id(848)
    assert item_848 is not None, "Should find item by ID 848"
    assert item_848['name'] == 'stick', "Item ID 848 should be stick"
    print("✓ Item ID 848 is stick")


def run_all_tests():
    """Run all tests"""
    print("Running MinecraftDataService Tests\n")
    
    try:
        test_basic_lookups()
        test_recipes()
        test_food_data()
        test_crafting_table_requirement()
        test_normalization()
        test_block_finding()
        test_id_lookups()
        
        print("\n✅ All tests passed!")
        return True
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        return False
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)