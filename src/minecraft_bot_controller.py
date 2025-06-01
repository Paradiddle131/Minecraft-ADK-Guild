"""
BotController - Hybrid architecture with internal Pydantic validation
Provides a Python-centric interface for controlling the Minecraft bot
"""
import asyncio
import math
from collections import defaultdict
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Union

from pydantic import BaseModel, ValidationError

from .bridge.bridge_manager import BridgeManager
from .config import get_config
from .logging_config import get_logger
from .minecraft_data_service import MinecraftDataService
from .schemas.bot_commands import *
from .schemas.bot_responses import *
from .schemas.progress import *

logger = get_logger(__name__)

T = TypeVar('T', bound=BaseModel)


class BotController:
    """Enhanced bot controller with schema validation and consistent error handling"""

    _instance = None
    _bridge_manager = None

    def __new__(cls, bridge_manager_instance: BridgeManager):
        if cls._instance is None or cls._bridge_manager is not bridge_manager_instance:
            cls._instance = super().__new__(cls)
            cls._bridge_manager = bridge_manager_instance
        return cls._instance

    def __init__(self, bridge_manager_instance: BridgeManager):
        """Initialize the BotController with a BridgeManager instance"""
        if not hasattr(self, "bridge") or self.bridge is not bridge_manager_instance:
            self.bridge = bridge_manager_instance
            self.config = get_config()
            self.mc_data_service = MinecraftDataService()
            self.active_operations: Dict[str, asyncio.Task] = {}
            logger.info("Initialized BotController with hybrid architecture")

    async def _execute_command(
        self,
        command_schema: Type[BaseModel],
        response_schema: Type[T],
        method: str,
        **kwargs
    ) -> T:
        """Generic command execution with schema validation and error handling"""
        start_time = datetime.now()
        
        try:
            # Validate input
            command = command_schema(**kwargs)
            command_dict = command.dict(exclude_none=True)
            
            # Determine timeout
            timeout_ms = self._get_timeout_for_method(method, command_dict.get('timeout_ms'))
            
            # Execute command
            result = await self.bridge.execute_command(method, **command_dict)
            
            # Handle response
            response_data = self._process_bridge_response(result, response_schema)
            
            # Add execution time
            execution_time = int((datetime.now() - start_time).total_seconds() * 1000)
            response_data['execution_time_ms'] = execution_time
            
            return response_schema(**response_data)
            
        except ValidationError as e:
            return response_schema(
                status="error",
                error_details=ErrorDetails(
                    error_type="validation",
                    message=f"Invalid command parameters: {e}",
                    suggestion="Check command parameters match expected types"
                )
            )
        except asyncio.TimeoutError:
            elapsed_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            return response_schema(
                status="timeout",
                error_details=TimeoutError(
                    message=f"Command '{method}' timed out",
                    timeout_ms=timeout_ms,
                    elapsed_ms=elapsed_ms,
                    suggestion=f"Retry with longer timeout or check if bot is stuck"
                )
            )
        except Exception as e:
            error_type = type(e).__name__
            return response_schema(
                status="error",
                error_details=ErrorDetails(
                    error_type=error_type,
                    message=str(e),
                    suggestion=self._get_error_suggestion(error_type, str(e))
                )
            )
    
    def _get_timeout_for_method(self, method: str, override_timeout: Optional[int]) -> int:
        """Get appropriate timeout for method"""
        if override_timeout:
            return override_timeout
            
        timeout_config = self.config.timeouts
        
        # Method-specific timeouts
        timeout_map = {
            'pathfinder.goto': timeout_config.pathfinder_default_ms,
            'move_to': timeout_config.pathfinder_default_ms,
            'craft': timeout_config.long_command_ms,
            'dig': timeout_config.long_command_ms,
            'place_block': timeout_config.standard_command_ms,
            'chat': timeout_config.quick_command_ms,
            'get_inventory': timeout_config.quick_command_ms,
            'get_position': timeout_config.quick_command_ms,
        }
        
        return timeout_map.get(method, timeout_config.standard_command_ms)
    
    def _process_bridge_response(self, result: Any, response_schema: Type[BaseModel]) -> dict:
        """Process response from bridge into schema-compatible format"""
        if isinstance(result, dict):
            # Check for error responses
            if 'error' in result and not result.get('status'):
                # Bridge error format
                error_msg = str(result['error'])
                error_data = {
                    'status': 'error',
                    'error_details': {
                        'error_type': 'bridge_error',
                        'message': error_msg
                    }
                }
                
                # Check for timeout
                if 'timeout' in error_msg.lower():
                    error_data['status'] = 'timeout'
                    error_data['error_details']['error_type'] = 'timeout'
                    # Extract timeout duration if possible
                    import re
                    timeout_match = re.search(r'(\d+)ms', error_msg)
                    if timeout_match:
                        error_data['error_details']['timeout_ms'] = int(timeout_match.group(1))
                        
                return error_data
                
            # Success or already formatted response
            return result
        else:
            # Non-dict response, wrap it
            return {'status': 'success', 'result': result}
    
    def _get_error_suggestion(self, error_type: str, error_msg: str) -> Optional[str]:
        """Get helpful suggestion based on error type"""
        suggestions = {
            'ConnectionError': "Check if Minecraft server is running and accessible",
            'ValueError': "Verify the command parameters are correct",
            'KeyError': "The requested item or block may not exist",
            'TimeoutError': "Increase timeout or check if bot is stuck",
        }
        
        # Check error message for specific issues
        if 'inventory full' in error_msg.lower():
            return "Drop some items to make space in inventory"
        elif 'too far' in error_msg.lower():
            return "Move closer to the target location"
        elif 'no path' in error_msg.lower():
            return "Target may be unreachable, try a different location"
            
        return suggestions.get(error_type)
    
    def _is_valid_position(self, x: float, y: float, z: float) -> bool:
        """Validate if position is within world bounds"""
        return -30000000 <= x <= 30000000 and -64 <= y <= 320 and -30000000 <= z <= 30000000
    
    def _calculate_distance(self, pos1: Dict[str, float], pos2: Dict[str, float]) -> float:
        """Calculate 3D distance between two positions"""
        return math.sqrt(
            (pos2['x'] - pos1['x'])**2 +
            (pos2['y'] - pos1['y'])**2 +
            (pos2['z'] - pos1['z'])**2
        )
    
    # Public methods with Pydantic validation
    async def chat(self, message: str) -> Dict[str, Any]:
        """Send a chat message - returns simple dict for ADK compatibility"""
        try:
            await self.bridge.chat(message)
            return {"status": "success", "message": message}
        except Exception as e:
            logger.error(f"Chat failed: {e}")
            return {"status": "error", "error": str(e)}
    
    async def move_to(self, x: float, y: float, z: float, 
                     timeout_ms: Optional[int] = None,
                     sprint: bool = False) -> MoveToResponse:
        """Internal method returning Pydantic model"""
        command = MoveToCommand(
            position=Position3D(x=x, y=y, z=z),
            timeout_ms=timeout_ms,
            sprint=sprint
        )
        
        # Validate position
        if not self._is_valid_position(x, y, z):
            return MoveToResponse(
                status="error",
                target_position=command.position,
                error_details=ErrorDetails(
                    error_type="invalid_position",
                    message="Position is outside world bounds"
                )
            )
        
        # Get current position for distance calculation
        try:
            current_pos_response = await self.get_position()
            start_pos = None
            if current_pos_response.status == "success" and current_pos_response.position:
                start_pos = current_pos_response.position.dict()
        except:
            start_pos = None
        
        # Execute movement
        try:
            timeout = timeout_ms or self.config.timeouts.pathfinder_default_ms
            result = await self.bridge.move_to(int(x), int(y), int(z), timeout=timeout)
            
            if result.get('status') == 'completed':
                # JavaScript returns 'actual_position' not 'position'
                final_pos = result.get('actual_position', {'x': x, 'y': y, 'z': z})
                distance = None
                if start_pos:
                    distance = self._calculate_distance(start_pos, final_pos)
                
                return MoveToResponse(
                    status="success",
                    target_position=command.position,
                    actual_position=Position3D(**final_pos),
                    distance_traveled=distance
                )
            else:
                return MoveToResponse(
                    status="error",
                    target_position=command.position,
                    error_details=ErrorDetails(
                        error_type="movement_failed",
                        message=result.get('error', 'Unknown movement error')
                    )
                )
        except Exception as e:
            return MoveToResponse(
                status="error",
                target_position=command.position,
                error_details=ErrorDetails(
                    error_type=type(e).__name__,
                    message=str(e)
                )
            )
    
    async def dig_block(self, x: float, y: float, z: float,
                       force_look: bool = True,
                       dig_face: Optional[str] = None) -> DigBlockResponse:
        """Dig a block with consistent error handling"""
        return await self._execute_command(
            DigBlockCommand,
            DigBlockResponse,
            'dig',
            position={'x': x, 'y': y, 'z': z},
            force_look=force_look,
            dig_face=dig_face
        )
    
    async def place_block(self, x: float, y: float, z: float,
                         face: str, item_name: str) -> PlaceBlockResponse:
        """Place a block"""
        return await self._execute_command(
            PlaceBlockCommand,
            PlaceBlockResponse,
            'place_block',
            reference_position={'x': x, 'y': y, 'z': z},
            face=face,
            item_name=item_name
        )
    
    async def craft_item(self, recipe_name: str, count: int = 1,
                        crafting_table: Optional[Dict[str, float]] = None) -> CraftItemResponse:
        """Craft items"""
        ct_pos = None
        if crafting_table:
            ct_pos = Position3D(**crafting_table)
            
        return await self._execute_command(
            CraftItemCommand,
            CraftItemResponse,
            'craft',
            recipe_name=recipe_name,
            count=count,
            crafting_table=ct_pos
        )
    
    async def get_inventory(self) -> GetInventoryResponse:
        """Get inventory with rich categorization"""
        try:
            result = await self.bridge.execute_command('inventory.items')
            
            if isinstance(result, list):
                # Process inventory items
                items = []
                for item in result:
                    try:
                        items.append(InventoryItem(
                            name=item.get('name', 'unknown'),
                            count=item.get('count', 0),
                            slot=item.get('slot', -1),
                            metadata=item.get('metadata')
                        ))
                    except Exception as e:
                        logger.error(f"Failed to parse inventory item: {e}")
                
                # Categorize items
                categories = self._categorize_items(items)
                empty_slots = 36 - len(items)  # Standard inventory size
                
                return GetInventoryResponse(
                    status='success',
                    items=items,
                    empty_slots=empty_slots,
                    categories=categories
                )
            else:
                return GetInventoryResponse(
                    status='error',
                    items=[],
                    empty_slots=0,
                    error_details=ErrorDetails(
                        error_type='invalid_response',
                        message='Invalid inventory response format'
                    )
                )
                
        except Exception as e:
            return GetInventoryResponse(
                status='error',
                items=[],
                empty_slots=0,
                error_details=ErrorDetails(
                    error_type=type(e).__name__,
                    message=str(e)
                )
            )
    
    async def get_position(self) -> GetPositionResponse:
        """Get bot's current position"""
        try:
            result = await self.bridge.execute_command('entity.position')
            
            if isinstance(result, dict) and all(k in result for k in ['x', 'y', 'z']):
                return GetPositionResponse(
                    status='success',
                    position=Position3D(**result)
                )
            else:
                return GetPositionResponse(
                    status='error',
                    error_details=ErrorDetails(
                        error_type='invalid_response',
                        message='Invalid position response format'
                    )
                )
        except Exception as e:
            return GetPositionResponse(
                status='error',
                error_details=ErrorDetails(
                    error_type=type(e).__name__,
                    message=str(e)
                )
            )
    
    def _categorize_items(self, items: List[InventoryItem]) -> Dict[str, List[InventoryItem]]:
        """Categorize items using minecraft_data service"""
        categories = defaultdict(list)
        
        for item in items:
            # Use minecraft_data service for categorization
            item_data = self.mc_data_service.get_item_by_name(item.name)
            if item_data:
                # Derive category from minecraft_data properties
                if item_data.get('stackSize') == 1 and 'durability' in item_data:
                    if any(tool in item.name.lower() for tool in ['axe', 'pickaxe', 'shovel', 'hoe']):
                        categories['tools'].append(item)
                    elif any(weapon in item.name.lower() for weapon in ['sword', 'bow', 'crossbow']):
                        categories['weapons'].append(item)
                    elif any(armor in item.name.lower() for armor in ['helmet', 'chestplate', 'leggings', 'boots']):
                        categories['armor'].append(item)
                elif self.mc_data_service.is_block(item.name):
                    categories['blocks'].append(item)
                elif self.mc_data_service.is_food(item.name):
                    categories['food'].append(item)
                else:
                    categories['materials'].append(item)
            else:
                categories['other'].append(item)
        
        return dict(categories)
    
    # Progress tracking methods
    async def move_to_with_progress(
        self, 
        x: float, 
        y: float, 
        z: float,
        timeout_ms: Optional[int] = None,
        progress_callback: Optional[Callable[[ProgressUpdate], None]] = None
    ) -> MoveToResponse:
        """Move with progress tracking"""
        operation_id = f"move_{datetime.now().timestamp()}"
        start_pos_response = await self.get_position()
        
        if start_pos_response.status != "success" or not start_pos_response.position:
            return MoveToResponse(
                status="error",
                target_position=Position3D(x=x, y=y, z=z),
                error_details=ErrorDetails(
                    error_type="position_error",
                    message="Could not get current position"
                )
            )
        
        start_pos = start_pos_response.position
        start_time = datetime.now()
        
        # Calculate total distance
        total_distance = math.sqrt(
            (x - start_pos.x)**2 + 
            (y - start_pos.y)**2 + 
            (z - start_pos.z)**2
        )
        
        async def track_progress():
            """Background task to track movement progress"""
            while operation_id in self.active_operations:
                try:
                    current_pos_response = await self.get_position()
                    if current_pos_response.status != "success":
                        continue
                        
                    current_pos = current_pos_response.position
                    elapsed_ms = int((datetime.now() - start_time).total_seconds() * 1000)
                    
                    # Calculate progress
                    distance_remaining = math.sqrt(
                        (x - current_pos.x)**2 +
                        (y - current_pos.y)**2 +
                        (z - current_pos.z)**2
                    )
                    progress_percent = ((total_distance - distance_remaining) / total_distance) * 100 if total_distance > 0 else 100
                    # Ensure progress_percent is within 0-100 range
                    progress_percent = max(0, min(progress_percent, 100))
                    
                    # Create progress update
                    progress = PathfindingProgress(
                        operation_id=operation_id,
                        progress_percent=progress_percent,
                        status_message=f"{distance_remaining:.0f} blocks left",
                        elapsed_ms=elapsed_ms,
                        current_position=current_pos,
                        target_position=Position3D(x=x, y=y, z=z),
                        distance_remaining=distance_remaining
                    )
                    
                    # Send progress update
                    if progress_callback:
                        progress_callback(progress)
                    
                    # Also send to chat for visibility (concise message)
                    await self.chat(progress.status_message)
                    
                    await asyncio.sleep(5)  # Update every 5 seconds
                    
                except Exception as e:
                    logger.error(f"Progress tracking error: {e}")
                    break
        
        # Start progress tracking
        progress_task = asyncio.create_task(track_progress())
        self.active_operations[operation_id] = progress_task
        
        try:
            # Execute movement
            response = await self.move_to(x, y, z, timeout_ms)
            
            # Stop progress tracking
            if operation_id in self.active_operations:
                self.active_operations[operation_id].cancel()
                del self.active_operations[operation_id]
                
            return response
            
        except Exception as e:
            # Ensure progress tracking stops on error
            if operation_id in self.active_operations:
                self.active_operations[operation_id].cancel()
                del self.active_operations[operation_id]
            raise