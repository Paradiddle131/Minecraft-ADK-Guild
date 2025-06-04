"""
Minecraft Data Service - Centralized Python service for all Minecraft data lookups
"""
import logging
from typing import Any, Dict, List, Optional

import minecraft_data

logger = logging.getLogger(__name__)


class MinecraftDataService:
    """Service for handling all Minecraft data lookups using python-minecraft-data"""

    _instance = None
    _version = None

    def __new__(cls, mc_version: str = "1.21.1"):
        if cls._instance is None or cls._version != mc_version:
            cls._instance = super().__new__(cls)
            cls._version = mc_version
        return cls._instance

    def __init__(self, mc_version: str = "1.21.1"):
        """Initialize the MinecraftDataService with specified Minecraft version

        Args:
            mc_version: Minecraft version string (e.g., "1.21.1")
        """
        # Only initialize if not already initialized or version changed
        if not hasattr(self, "mc_data") or self.version != mc_version:
            try:
                # Initialize minecraft_data as shown in example.py
                self.mc_data = minecraft_data(mc_version)
                self.version = mc_version
                logger.info(f"Initialized MinecraftDataService for version {mc_version}")
            except Exception as e:
                logger.error(f"Failed to initialize minecraft-data for version {mc_version}: {e}")
                raise

    def get_block_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get block data by name

        Args:
            name: Block name (e.g., "stone", "oak_log")

        Returns:
            Block data dict or None if not found
        """
        try:
            # blocks_name directly contains the full block data
            return self.mc_data.blocks_name.get(name)
        except Exception as e:
            logger.error(f"Error getting block by name '{name}': {e}")
            return None

    def get_block_by_id(self, block_id: int) -> Optional[Dict[str, Any]]:
        """Get block data by ID

        Args:
            block_id: Block numeric ID

        Returns:
            Block data dict or None if not found
        """
        try:
            # Use blocks_list for ID lookup
            if 0 <= block_id < len(self.mc_data.blocks_list):
                return self.mc_data.blocks_list[block_id]
            return None
        except Exception as e:
            logger.error(f"Error getting block by id {block_id}: {e}")
            return None

    def get_item_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get item data by name

        Args:
            name: Item name (e.g., "diamond", "stick")

        Returns:
            Item data dict or None if not found
        """
        try:
            # items_name directly contains the full item data
            item = self.mc_data.items_name.get(name)
            if item:
                return item

            # If not found, try using find_item_or_block method
            result = self.mc_data.find_item_or_block(name)
            if result:
                return result

            return None
        except Exception as e:
            logger.error(f"Error getting item by name '{name}': {e}")
            return None

    def get_item_by_id(self, item_id: int) -> Optional[Dict[str, Any]]:
        """Get item data by ID

        Args:
            item_id: Item numeric ID

        Returns:
            Item data dict or None if not found
        """
        try:
            # Use items_list for ID lookup
            if 0 <= item_id < len(self.mc_data.items_list):
                return self.mc_data.items_list[item_id]
            return None
        except Exception as e:
            logger.error(f"Error getting item by id {item_id}: {e}")
            return None

    def find_blocks(self, options: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Find blocks matching specified criteria

        Args:
            options: Search options dict with filters

        Returns:
            List of matching blocks
        """
        try:
            results = []

            # Filter by name pattern if provided
            if "name_pattern" in options:
                pattern = options["name_pattern"].lower()
                for name, block_data in self.mc_data.blocks_name.items():
                    if pattern in name.lower():
                        results.append(block_data)

            # Filter by hardness range if provided
            if "min_hardness" in options or "max_hardness" in options:
                min_h = options.get("min_hardness", 0)
                max_h = options.get("max_hardness", float("inf"))

                # If we already have results from name filter, filter those
                if results:
                    results = [b for b in results if min_h <= (b.get("hardness", 0)) <= max_h]
                else:
                    # Otherwise search all blocks
                    for block_data in self.mc_data.blocks_name.values():
                        if min_h <= (block_data.get("hardness", 0)) <= max_h:
                            results.append(block_data)

            return results
        except Exception as e:
            logger.error(f"Error finding blocks with options {options}: {e}")
            return []

    def get_recipes_for_item_id(self, item_id: int) -> List[Dict[str, Any]]:
        """Get all recipes that produce the specified item

        Args:
            item_id: Item ID to find recipes for

        Returns:
            List of recipe dicts
        """
        try:
            # Recipes are keyed by result item ID as string
            return self.mc_data.recipes.get(str(item_id), [])
        except Exception as e:
            logger.error(f"Error getting recipes for item id {item_id}: {e}")
            return []

    def get_recipes_for_item_name(self, item_name: str) -> List[Dict[str, Any]]:
        """Get all recipes that produce the specified item by name

        Args:
            item_name: Item name to find recipes for

        Returns:
            List of recipe dicts
        """
        item = self.get_item_by_name(item_name)
        if not item:
            return []
        return self.get_recipes_for_item_id(item["id"])

    def get_food_points(self, item_name: str) -> int:
        """Get food points for a food item

        Args:
            item_name: Name of the food item

        Returns:
            Food points value or 0 if not a food item
        """
        try:
            # Handle special case: "steak" is called "cooked_beef" in minecraft
            if item_name == "steak":
                item_name = "cooked_beef"

            # Check if item is in foods_name
            food_data = self.mc_data.foods_name.get(item_name)
            if food_data:
                return food_data.get("foodPoints", 0)

            # Special case: cake must be placed as a block to be eaten (7 slices × 2 points each)
            if item_name == "cake":
                logger.info("Cake must be placed as a block to be eaten (provides 14 total food points)")
                return 14  # Total food points from all 7 slices

            return 0
        except Exception as e:
            logger.error(f"Error getting food points for '{item_name}': {e}")
            return 0

    def get_saturation(self, item_name: str) -> float:
        """Get saturation value for a food item

        Args:
            item_name: Name of the food item

        Returns:
            Saturation value or 0.0 if not a food item
        """
        try:
            # Handle special case: "steak" is called "cooked_beef" in minecraft
            if item_name == "steak":
                item_name = "cooked_beef"

            # Check if item is in foods_name
            food_data = self.mc_data.foods_name.get(item_name)
            if food_data:
                return food_data.get("saturation", 0.0)

            # Special case: cake must be placed as a block to be eaten
            if item_name == "cake":
                return 0.4  # Saturation per slice (2.8 total for all slices)

            return 0.0
        except Exception as e:
            logger.error(f"Error getting saturation for '{item_name}': {e}")
            return 0.0

    def needs_crafting_table(self, item_name: str) -> bool:
        """Check if an item requires a crafting table to craft

        Args:
            item_name: Name of the item to craft

        Returns:
            True if crafting table required, False if can craft in inventory
        """
        # Get recipes for this item
        recipes = self.get_recipes_for_item_name(item_name)

        if not recipes:
            # No recipe found, assume it needs crafting table if craftable
            return True

        # Check if any recipe can fit in 2x2 grid
        for recipe in recipes:
            if "inShape" in recipe:
                # Shaped recipe - check dimensions
                shape = recipe["inShape"]
                if len(shape) <= 2 and all(len(row) <= 2 for row in shape):
                    return False  # Can craft in inventory
            elif "ingredients" in recipe:
                # Shapeless recipe - check ingredient count
                if len(recipe["ingredients"]) <= 4:
                    return False  # Can craft in inventory

        # Default to needing crafting table
        return True

    def normalize_item_name(self, item_name: str) -> str:
        """Normalize item names using generic fuzzy matching

        Args:
            item_name: Raw item name from user

        Returns:
            Normalized item name that matches minecraft-data
        """
        # Basic normalization: lowercase and remove extra spaces
        normalized = item_name.lower().strip()

        # Remove common plural suffixes generically
        if normalized.endswith("s") and len(normalized) > 2:
            singular = normalized[:-1]
            # Check if singular form exists
            if self.get_item_by_name(singular):
                return singular

        # Try exact match first
        if self.get_item_by_name(normalized):
            return normalized

        # Fuzzy match against all items
        best_match = self.fuzzy_match_item_name(normalized)
        if best_match:
            return best_match

        return item_name

    def fuzzy_match_item_name(self, query: str, threshold: float = 0.6) -> Optional[str]:
        """Find best matching item name using fuzzy string matching

        Args:
            query: Search query
            threshold: Minimum similarity score (0-1)

        Returns:
            Best matching item name or None
        """
        try:
            all_items = self.get_all_items()
            best_match = None
            best_score = 0

            query_lower = query.lower()
            query_words = set(query_lower.split())

            for item in all_items:
                item_name = item["name"].lower()
                item_words = set(item_name.replace("_", " ").split())

                # Calculate similarity score
                score = 0

                # Exact match
                if query_lower == item_name:
                    return item["name"]

                # Substring match
                if query_lower in item_name:
                    score += 0.8
                elif item_name in query_lower:
                    score += 0.7

                # Word overlap
                common_words = query_words & item_words
                if common_words:
                    score += len(common_words) / max(len(query_words), len(item_words)) * 0.6

                # Character similarity (enhanced for typos)
                # Check character-by-character similarity
                common_chars = 0
                for i, char in enumerate(query_lower[: min(len(query_lower), len(item_name))]):
                    if i < len(item_name) and char == item_name[i]:
                        common_chars += 1

                # Check for character transpositions and typos
                if abs(len(query_lower) - len(item_name)) <= 2:  # Similar length
                    # Count matching characters regardless of position
                    query_chars = {}
                    item_chars = {}
                    for c in query_lower:
                        query_chars[c] = query_chars.get(c, 0) + 1
                    for c in item_name:
                        item_chars[c] = item_chars.get(c, 0) + 1

                    matching_chars = 0
                    for c, count in query_chars.items():
                        matching_chars += min(count, item_chars.get(c, 0))

                    char_overlap_ratio = matching_chars / max(len(query_lower), len(item_name))
                    if char_overlap_ratio > 0.8:  # High character overlap
                        score += char_overlap_ratio * 0.6

                if query_lower and common_chars > 0:
                    score += (common_chars / len(query_lower)) * 0.4

                # Bonus for matching important suffixes/prefixes
                if query_lower.endswith(item_name.split("_")[-1]) or item_name.endswith(query_lower.split()[-1]):
                    score += 0.2

                if score > best_score and score >= threshold:
                    best_score = score
                    best_match = item["name"]

            return best_match

        except Exception as e:
            logger.error(f"Error in fuzzy matching: {e}")
            return None

    def get_material_for_tool(self, tool_name: str) -> Optional[str]:
        """Get the material type for a tool

        Args:
            tool_name: Name of the tool (e.g., "diamond_pickaxe")

        Returns:
            Material name or None
        """
        if "_" not in tool_name:
            return None

        material = tool_name.split("_")[0]
        valid_materials = {"wooden", "stone", "iron", "golden", "diamond", "netherite"}

        return material if material in valid_materials else None

    def get_all_items(self) -> List[Dict[str, Any]]:
        """Get all items in the game

        Returns:
            List of all item data dicts
        """
        try:
            return list(self.mc_data.items_name.values())
        except Exception as e:
            logger.error(f"Error getting all items: {e}")
            return []

    def get_all_blocks(self) -> List[Dict[str, Any]]:
        """Get all blocks in the game

        Returns:
            List of all block data dicts
        """
        try:
            return list(self.mc_data.blocks_name.values())
        except Exception as e:
            logger.error(f"Error getting all blocks: {e}")
            return []

    def get_blocks_by_pattern(self, pattern: str) -> List[Dict[str, Any]]:
        """Get blocks matching a pattern (e.g., '*_log', 'log', 'logs')

        Args:
            pattern: Pattern to match against block names

        Returns:
            List of matching block data dicts with their IDs
        """
        try:
            matching_blocks = []
            pattern_lower = pattern.lower().strip()

            # Handle wildcard patterns
            if pattern_lower.endswith("*_log") or pattern_lower in ["log", "logs"]:
                # Get all log type blocks
                suffix = "_log"
                for name, block_data in self.mc_data.blocks_name.items():
                    if name.endswith(suffix):
                        matching_blocks.append(block_data)

            elif pattern_lower.endswith("*_planks") or pattern_lower in ["plank", "planks"]:
                # Get all plank type blocks
                suffix = "_planks"
                for name, block_data in self.mc_data.blocks_name.items():
                    if name.endswith(suffix):
                        matching_blocks.append(block_data)

            elif "*_" in pattern_lower:
                # Generic wildcard pattern
                suffix = pattern_lower.split("*_")[1]
                for name, block_data in self.mc_data.blocks_name.items():
                    if name.endswith(suffix):
                        matching_blocks.append(block_data)

            elif "_*" in pattern_lower:
                # Prefix pattern
                prefix = pattern_lower.split("_*")[0]
                for name, block_data in self.mc_data.blocks_name.items():
                    if name.startswith(prefix + "_"):
                        matching_blocks.append(block_data)

            else:
                # Exact match or contains
                for name, block_data in self.mc_data.blocks_name.items():
                    if pattern_lower == name.lower() or pattern_lower in name.lower():
                        matching_blocks.append(block_data)

            logger.info(f"Found {len(matching_blocks)} blocks matching pattern '{pattern}'")
            return matching_blocks

        except Exception as e:
            logger.error(f"Error getting blocks by pattern '{pattern}': {e}")
            return []

    def get_recipes_for_item(self, item_name: str) -> List[Dict[str, Any]]:
        """Get all recipes that produce the specified item.

        This is an alias for get_recipes_for_item_name for compatibility.

        Args:
            item_name: Item name to find recipes for

        Returns:
            List of recipe dicts
        """
        return self.get_recipes_for_item_name(item_name)

    def get_all_recipes(self) -> List[Dict[str, Any]]:
        """Get all recipes in the game.

        Returns:
            List of all recipes with their result items
        """
        try:
            all_recipes = []

            # Iterate through all recipe entries
            for item_id_str, recipes in self.mc_data.recipes.items():
                item_id = int(item_id_str)
                item = self.get_item_by_id(item_id)

                if item:
                    for recipe in recipes:
                        # Add result item name to recipe for convenience
                        enriched_recipe = recipe.copy()
                        enriched_recipe["result"]["name"] = item["name"]
                        enriched_recipe["result"]["displayName"] = item.get("displayName", item["name"])
                        all_recipes.append(enriched_recipe)

            return all_recipes
        except Exception as e:
            logger.error(f"Error getting all recipes: {e}")
            return []

    def select_best_recipe(self, item_name: str, inventory: Dict[str, int]) -> Optional[Dict[str, Any]]:
        """Select the best recipe using a generic scoring algorithm

        Args:
            item_name: Name of item to craft
            inventory: Dict mapping item names to counts

        Returns:
            Best recipe dict or None if no craftable recipe found
        """
        recipes = self.get_recipes_for_item_name(item_name)

        if not recipes:
            return None

        # Score each recipe based on generic criteria
        scored_recipes = []

        for recipe in recipes:
            materials = self.get_recipe_materials(recipe)

            # Calculate generic scores
            score_components = {
                "craftability": 0,  # Can we craft it?
                "efficiency": 0,  # How many can we craft?
                "material_usage": 0,  # How well does it use available materials?
                "output_value": 0,  # How much does it produce?
                "simplicity": 0,  # How simple is the recipe?
            }

            # Check craftability and calculate efficiency
            can_craft = True
            max_crafts = float("inf")
            total_materials_needed = 0
            total_materials_available = 0

            for material, needed in materials.items():
                available = inventory.get(material, 0)
                total_materials_needed += needed
                total_materials_available += min(available, needed * 100)  # Cap to avoid overflow

                if available < needed:
                    can_craft = False
                    score_components["craftability"] = -1000  # Heavy penalty
                    break
                else:
                    crafts_possible = available // needed
                    max_crafts = min(max_crafts, crafts_possible)

            if can_craft:
                score_components["craftability"] = 100
                score_components["efficiency"] = min(max_crafts, 100)  # Cap at 100 to normalize

                # Material usage efficiency (0-100)
                if total_materials_needed > 0:
                    usage_ratio = total_materials_available / (total_materials_needed * max(max_crafts, 1))
                    score_components["material_usage"] = min(usage_ratio * 50, 100)

                # Output value (favor recipes that produce more)
                result_count = recipe.get("result", {}).get("count", 1)
                score_components["output_value"] = result_count * 10

                # Simplicity (fewer different materials is simpler)
                score_components["simplicity"] = max(0, 50 - len(materials) * 10)

            # Calculate total score with generic weights
            weights = {
                "craftability": 10.0,  # Most important - can we make it?
                "efficiency": 3.0,  # How many can we make?
                "material_usage": 2.0,  # How well do we use materials?
                "output_value": 1.5,  # Prefer recipes with more output
                "simplicity": 0.5,  # Slight preference for simpler recipes
            }

            total_score = sum(score_components[key] * weights[key] for key in score_components)

            scored_recipes.append({"recipe": recipe, "score": total_score, "components": score_components})

        # Sort by score and return best
        scored_recipes.sort(key=lambda x: x["score"], reverse=True)

        if scored_recipes and scored_recipes[0]["score"] > 0:
            logger.debug(
                f"Selected recipe with score {scored_recipes[0]['score']:.2f}, components: {scored_recipes[0]['components']}"
            )
            return scored_recipes[0]["recipe"]

        return None

    def get_recipe_materials(self, recipe: Dict[str, Any]) -> Dict[str, int]:
        """Extract materials from any recipe format generically

        Args:
            recipe: Recipe dict

        Returns:
            Dict mapping material names to counts needed
        """
        materials = {}

        # Generic recipe format handlers
        def process_ingredient(ingredient):
            """Process any ingredient format generically"""
            if ingredient is None:
                return

            # Handle numeric IDs
            if isinstance(ingredient, (int, float)):
                item = self.get_item_by_id(int(ingredient))
                if item:
                    materials[item["name"]] = materials.get(item["name"], 0) + 1

            # Handle string names
            elif isinstance(ingredient, str):
                materials[ingredient] = materials.get(ingredient, 0) + 1

            # Handle dict formats
            elif isinstance(ingredient, dict):
                # Try various possible keys for item identification
                item_ref = None
                for key in ["item", "id", "name", "type"]:
                    if key in ingredient:
                        item_ref = ingredient[key]
                        break

                if item_ref is not None:
                    # Get count from various possible keys
                    count = 1
                    for count_key in ["count", "amount", "quantity", "num"]:
                        if count_key in ingredient:
                            count = ingredient[count_key]
                            break

                    # Process the item reference
                    if isinstance(item_ref, (int, float)):
                        item = self.get_item_by_id(int(item_ref))
                        if item:
                            materials[item["name"]] = materials.get(item["name"], 0) + count
                    else:
                        materials[str(item_ref)] = materials.get(str(item_ref), 0) + count

            # Handle list formats (alternative ingredients)
            elif isinstance(ingredient, list):
                # For alternative ingredients, just process the first one
                if ingredient:
                    process_ingredient(ingredient[0])

        # Process shaped recipes
        if "inShape" in recipe:
            for row in recipe["inShape"]:
                if isinstance(row, list):
                    for item in row:
                        process_ingredient(item)
                else:
                    process_ingredient(row)

        # Process shapeless recipes
        elif "ingredients" in recipe:
            ingredients = recipe["ingredients"]
            if isinstance(ingredients, list):
                for ingredient in ingredients:
                    process_ingredient(ingredient)
            else:
                process_ingredient(ingredients)

        # Handle other possible recipe formats
        else:
            # Check for other common keys
            for key in ["items", "materials", "input", "inputs", "requires"]:
                if key in recipe:
                    value = recipe[key]
                    if isinstance(value, list):
                        for item in value:
                            process_ingredient(item)
                    elif isinstance(value, dict):
                        for item_name, count in value.items():
                            materials[item_name] = materials.get(item_name, 0) + count
                    else:
                        process_ingredient(value)

        return materials

    def handle_generic_item_request(self, item_type: str, inventory: Dict[str, int]) -> Optional[str]:
        """Handle generic item requests by finding best matching variant

        Args:
            item_type: Generic item type
            inventory: Current inventory

        Returns:
            Specific item name or None
        """
        # Normalize the request
        normalized_type = item_type.lower().strip()

        # Check for exact match first
        exact_item = self.get_item_by_name(normalized_type)
        if exact_item:
            return normalized_type

        # Find all items that could match this generic type
        all_items = self.get_all_items()
        matching_items = []

        for item in all_items:
            item_name = item["name"].lower()

            # Score how well this item matches the generic type
            score = 0

            # Check if the type is in the item name
            if normalized_type in item_name:
                score += 10

            # Check if item name ends with the type (e.g., "oak_planks" ends with "planks")
            if item_name.endswith(normalized_type):
                score += 5

            # Check if type is a substring after underscore (common pattern)
            parts = item_name.split("_")
            if normalized_type in parts:
                score += 8

            # Fuzzy match for similar words
            if any(
                part.startswith(normalized_type[:3]) for part in parts if len(part) >= 3 and len(normalized_type) >= 3
            ):
                score += 3

            if score > 0:
                # Check inventory availability
                available = inventory.get(item["name"], 0)

                matching_items.append(
                    {
                        "name": item["name"],
                        "score": score,
                        "available": available,
                        "has_recipe": len(self.get_recipes_for_item_name(item["name"])) > 0,
                    }
                )

        if not matching_items:
            return None

        # Sort by score, then by availability, then by whether it has recipes
        matching_items.sort(key=lambda x: (x["score"], x["available"], x["has_recipe"]), reverse=True)

        # Try to find items we already have
        for match in matching_items:
            if match["available"] > 0:
                return match["name"]

        # If we don't have any, check what we can craft
        for match in matching_items:
            if match["has_recipe"]:
                # Check if we can craft it
                best_recipe = self.select_best_recipe(match["name"], inventory)
                if best_recipe:
                    return match["name"]

        # Return the best match even if we can't craft it
        return matching_items[0]["name"] if matching_items else None
