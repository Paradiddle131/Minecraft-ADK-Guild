"""
State Synchronization Service - Manages ADK state consistency with Minecraft world
"""
import asyncio
import json
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple
from copy import deepcopy
from pathlib import Path

import structlog
from google.cloud import adk

logger = structlog.get_logger(__name__)


@dataclass
class StateChange:
    """Represents a single state change"""
    key: str
    old_value: Any
    new_value: Any
    timestamp: float
    event_id: Optional[str] = None
    source: str = "unknown"


@dataclass 
class StateSnapshot:
    """Complete state snapshot at a point in time"""
    timestamp: float
    state: Dict[str, Any]
    event_count: int
    snapshot_id: str


@dataclass
class SyncConfig:
    """Configuration for state synchronization"""
    enable_history: bool = True
    max_history_size: int = 1000
    enable_snapshots: bool = True
    snapshot_interval: int = 300  # seconds
    max_snapshots: int = 24
    enable_persistence: bool = False
    persistence_path: Optional[str] = None
    conflict_resolution: str = "latest_wins"  # latest_wins, merge, custom
    
    def __post_init__(self):
        if self.enable_persistence and not self.persistence_path:
            self.persistence_path = "minecraft_state"


class StateDiffer:
    """Compares state objects and identifies differences"""
    
    @staticmethod
    def compute_diff(old_state: Dict[str, Any], new_state: Dict[str, Any]) -> List[StateChange]:
        """Compute differences between two state objects"""
        changes = []
        timestamp = time.time()
        
        # Find all keys that exist in either state
        all_keys = set(old_state.keys()) | set(new_state.keys())
        
        for key in all_keys:
            old_value = old_state.get(key)
            new_value = new_state.get(key)
            
            if old_value != new_value:
                changes.append(StateChange(
                    key=key,
                    old_value=old_value,
                    new_value=new_value,
                    timestamp=timestamp,
                    source="diff"
                ))
        
        return changes
    
    @staticmethod
    def apply_changes(state: Dict[str, Any], changes: List[StateChange]) -> Dict[str, Any]:
        """Apply state changes to a state object"""
        new_state = deepcopy(state)
        
        for change in changes:
            if change.new_value is None:
                # Remove key if new value is None
                new_state.pop(change.key, None)
            else:
                # Set new value
                StateDiffer._set_nested_key(new_state, change.key, change.new_value)
        
        return new_state
    
    @staticmethod
    def _set_nested_key(obj: Dict[str, Any], key: str, value: Any):
        """Set a nested key in a dictionary using dot notation"""
        if '.' not in key:
            obj[key] = value
            return
        
        parts = key.split('.')
        current = obj
        
        # Navigate to the parent of the target key
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            elif not isinstance(current[part], dict):
                # Convert non-dict values to dict to allow nesting
                current[part] = {}
            current = current[part]
        
        # Set the final value
        current[parts[-1]] = value


class StateValidator:
    """Validates state consistency and integrity"""
    
    def __init__(self):
        self.validation_rules = {}
        self.required_keys = set()
        self.type_constraints = {}
    
    def add_validation_rule(self, key_pattern: str, validator_func):
        """Add a validation rule for keys matching pattern"""
        self.validation_rules[key_pattern] = validator_func
    
    def add_required_key(self, key: str):
        """Mark a key as required"""
        self.required_keys.add(key)
    
    def add_type_constraint(self, key: str, expected_type: type):
        """Add type constraint for a key"""
        self.type_constraints[key] = expected_type
    
    def validate_state(self, state: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate state against all rules"""
        errors = []
        
        # Check required keys
        for required_key in self.required_keys:
            if not self._has_nested_key(state, required_key):
                errors.append(f"Missing required key: {required_key}")
        
        # Check type constraints
        for key, expected_type in self.type_constraints.items():
            value = self._get_nested_key(state, key)
            if value is not None and not isinstance(value, expected_type):
                errors.append(f"Type mismatch for {key}: expected {expected_type}, got {type(value)}")
        
        # Apply custom validation rules
        for pattern, validator in self.validation_rules.items():
            try:
                validator(state)
            except Exception as e:
                errors.append(f"Validation rule '{pattern}' failed: {e}")
        
        return len(errors) == 0, errors
    
    def _has_nested_key(self, obj: Dict[str, Any], key: str) -> bool:
        """Check if nested key exists using dot notation"""
        if '.' not in key:
            return key in obj
        
        parts = key.split('.')
        current = obj
        
        for part in parts:
            if not isinstance(current, dict) or part not in current:
                return False
            current = current[part]
        
        return True
    
    def _get_nested_key(self, obj: Dict[str, Any], key: str) -> Any:
        """Get nested key value using dot notation"""
        if '.' not in key:
            return obj.get(key)
        
        parts = key.split('.')
        current = obj
        
        for part in parts:
            if not isinstance(current, dict) or part not in current:
                return None
            current = current[part]
        
        return current


class StateSynchronizer:
    """Main state synchronization service"""
    
    def __init__(self, session_service=None, config: SyncConfig = None):
        self.session_service = session_service
        self.config = config or SyncConfig()
        
        # State management
        self.current_state: Dict[str, Any] = {}
        self.state_history: deque = deque(maxlen=self.config.max_history_size)
        self.snapshots: deque = deque(maxlen=self.config.max_snapshots)
        
        # Synchronization tracking
        self.pending_changes: Dict[str, StateChange] = {}
        self.sync_lock = asyncio.Lock()
        self.last_sync_time = 0
        self.sync_errors = []
        
        # Components
        self.differ = StateDiffer()
        self.validator = StateValidator()
        
        # Statistics
        self.stats = {
            "total_changes": 0,
            "successful_syncs": 0,
            "failed_syncs": 0,
            "state_size": 0,
            "last_snapshot_time": 0
        }
        
        # Background tasks
        self._snapshot_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        
        # Initialize Minecraft state validation rules
        self._setup_minecraft_validation()
        
        logger.info("StateSynchronizer initialized", config=config)
    
    def _setup_minecraft_validation(self):
        """Set up validation rules for Minecraft state"""
        # Required top-level keys
        self.validator.add_required_key("minecraft.spawned")
        
        # Type constraints
        self.validator.add_type_constraint("minecraft.spawned", bool)
        self.validator.add_type_constraint("minecraft.bot.health", (int, float))
        self.validator.add_type_constraint("minecraft.bot.food", (int, float))
        
        # Custom validation rules
        def validate_position(state):
            pos = self.validator._get_nested_key(state, "minecraft.bot.position")
            if pos and isinstance(pos, dict):
                for coord in ["x", "y", "z"]:
                    if coord in pos and not isinstance(pos[coord], (int, float)):
                        raise ValueError(f"Position {coord} must be numeric")
        
        def validate_health(state):
            health = self.validator._get_nested_key(state, "minecraft.bot.health")
            if health is not None and (health < 0 or health > 20):
                raise ValueError("Health must be between 0 and 20")
        
        self.validator.add_validation_rule("position", validate_position)
        self.validator.add_validation_rule("health", validate_health)
    
    async def start(self):
        """Start the synchronization service"""
        if self.config.enable_snapshots:
            self._snapshot_task = asyncio.create_task(self._periodic_snapshots())
        
        self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
        
        # Load persisted state if enabled
        if self.config.enable_persistence:
            await self._load_persisted_state()
        
        logger.info("StateSynchronizer started")
    
    async def stop(self):
        """Stop the synchronization service"""
        if self._snapshot_task:
            self._snapshot_task.cancel()
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
        
        # Persist state if enabled
        if self.config.enable_persistence:
            await self._persist_state()
        
        logger.info("StateSynchronizer stopped")
    
    async def apply_state_delta(self, state_delta: Dict[str, Any], 
                              event_id: Optional[str] = None,
                              source: str = "event") -> bool:
        """Apply a state delta from an event"""
        async with self.sync_lock:
            try:
                # Create state changes from delta
                changes = []
                timestamp = time.time()
                
                for key, value in state_delta.items():
                    old_value = self._get_nested_key(self.current_state, key)
                    if old_value != value:
                        changes.append(StateChange(
                            key=key,
                            old_value=old_value,
                            new_value=value,
                            timestamp=timestamp,
                            event_id=event_id,
                            source=source
                        ))
                
                if not changes:
                    return True  # No changes to apply
                
                # Apply changes to current state
                new_state = self.differ.apply_changes(self.current_state, changes)
                
                # Validate new state
                is_valid, validation_errors = self.validator.validate_state(new_state)
                if not is_valid:
                    logger.error("State validation failed after applying delta",
                               errors=validation_errors, event_id=event_id)
                    self.stats["failed_syncs"] += 1
                    return False
                
                # Update current state
                old_state = self.current_state
                self.current_state = new_state
                
                # Track changes in history
                if self.config.enable_history:
                    for change in changes:
                        self.state_history.append(change)
                
                # Update statistics
                self.stats["total_changes"] += len(changes)
                self.stats["successful_syncs"] += 1
                self.stats["state_size"] = len(json.dumps(self.current_state))
                self.last_sync_time = timestamp
                
                # Sync with ADK session if available
                if self.session_service:
                    try:
                        await self._sync_with_adk_session(state_delta)
                    except Exception as e:
                        logger.error("Failed to sync with ADK session",
                                   error=str(e), event_id=event_id)
                
                logger.debug("Applied state delta",
                           changes_count=len(changes),
                           event_id=event_id,
                           source=source)
                
                return True
                
            except Exception as e:
                logger.error("Failed to apply state delta",
                           error=str(e), event_id=event_id)
                self.stats["failed_syncs"] += 1
                self.sync_errors.append({
                    "timestamp": time.time(),
                    "error": str(e),
                    "event_id": event_id
                })
                return False
    
    async def _sync_with_adk_session(self, state_delta: Dict[str, Any]):
        """Synchronize state changes with ADK session"""
        if not self.session_service:
            return
        
        # Create ADK-compatible state update
        # This would depend on the actual ADK session API
        try:
            # Example implementation - adjust based on actual ADK API
            for key, value in state_delta.items():
                # Set session state
                pass  # await self.session_service.set_state(key, value)
            
            logger.debug("Synced state with ADK session",
                       keys=list(state_delta.keys()))
        except Exception as e:
            logger.error("ADK session sync failed", error=str(e))
            raise
    
    def _get_nested_key(self, obj: Dict[str, Any], key: str) -> Any:
        """Get nested key value using dot notation"""
        return self.validator._get_nested_key(obj, key)
    
    async def get_state_snapshot(self) -> StateSnapshot:
        """Get current state snapshot"""
        async with self.sync_lock:
            snapshot = StateSnapshot(
                timestamp=time.time(),
                state=deepcopy(self.current_state),
                event_count=len(self.state_history),
                snapshot_id=f"snapshot_{int(time.time())}"
            )
            return snapshot
    
    async def restore_from_snapshot(self, snapshot: StateSnapshot) -> bool:
        """Restore state from a snapshot"""
        async with self.sync_lock:
            try:
                # Validate snapshot state
                is_valid, errors = self.validator.validate_state(snapshot.state)
                if not is_valid:
                    logger.error("Cannot restore from invalid snapshot",
                               errors=errors, snapshot_id=snapshot.snapshot_id)
                    return False
                
                self.current_state = deepcopy(snapshot.state)
                self.last_sync_time = snapshot.timestamp
                
                logger.info("Restored state from snapshot",
                          snapshot_id=snapshot.snapshot_id,
                          timestamp=snapshot.timestamp)
                
                return True
                
            except Exception as e:
                logger.error("Failed to restore from snapshot",
                           error=str(e), snapshot_id=snapshot.snapshot_id)
                return False
    
    async def _periodic_snapshots(self):
        """Periodically create state snapshots"""
        while True:
            try:
                await asyncio.sleep(self.config.snapshot_interval)
                
                snapshot = await self.get_state_snapshot()
                self.snapshots.append(snapshot)
                
                self.stats["last_snapshot_time"] = snapshot.timestamp
                
                logger.debug("Created state snapshot",
                           snapshot_id=snapshot.snapshot_id,
                           state_size=len(snapshot.state))
                
            except Exception as e:
                logger.error("Snapshot creation failed", error=str(e))
    
    async def _periodic_cleanup(self):
        """Periodically clean up old data"""
        while True:
            try:
                await asyncio.sleep(3600)  # Every hour
                
                # Clean up old errors
                cutoff_time = time.time() - 86400  # 24 hours
                self.sync_errors = [
                    error for error in self.sync_errors
                    if error["timestamp"] > cutoff_time
                ]
                
                logger.debug("Performed periodic cleanup",
                           remaining_errors=len(self.sync_errors))
                
            except Exception as e:
                logger.error("Cleanup task failed", error=str(e))
    
    async def _persist_state(self):
        """Persist current state to disk"""
        if not self.config.persistence_path:
            return
        
        try:
            path = Path(self.config.persistence_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            
            snapshot = await self.get_state_snapshot()
            
            with open(f"{path}_state.json", 'w') as f:
                json.dump({
                    "snapshot": {
                        "timestamp": snapshot.timestamp,
                        "state": snapshot.state,
                        "event_count": snapshot.event_count,
                        "snapshot_id": snapshot.snapshot_id
                    },
                    "stats": self.stats
                }, f, indent=2)
            
            logger.info("Persisted state to disk", path=path)
            
        except Exception as e:
            logger.error("Failed to persist state", error=str(e))
    
    async def _load_persisted_state(self):
        """Load persisted state from disk"""
        if not self.config.persistence_path:
            return
        
        try:
            path = Path(f"{self.config.persistence_path}_state.json")
            if not path.exists():
                logger.info("No persisted state found")
                return
            
            with open(path, 'r') as f:
                data = json.load(f)
            
            snapshot_data = data.get("snapshot", {})
            if snapshot_data:
                snapshot = StateSnapshot(
                    timestamp=snapshot_data["timestamp"],
                    state=snapshot_data["state"],
                    event_count=snapshot_data["event_count"],
                    snapshot_id=snapshot_data["snapshot_id"]
                )
                
                if await self.restore_from_snapshot(snapshot):
                    logger.info("Loaded persisted state", 
                              snapshot_id=snapshot.snapshot_id)
                else:
                    logger.error("Failed to restore persisted state")
            
            # Restore stats
            if "stats" in data:
                self.stats.update(data["stats"])
            
        except Exception as e:
            logger.error("Failed to load persisted state", error=str(e))
    
    def get_sync_stats(self) -> Dict[str, Any]:
        """Get synchronization statistics"""
        return {
            "current_state_size": len(self.current_state),
            "history_size": len(self.state_history),
            "snapshots_count": len(self.snapshots),
            "sync_stats": self.stats.copy(),
            "last_sync_time": self.last_sync_time,
            "recent_errors": self.sync_errors[-10:],  # Last 10 errors
            "validation_rules": len(self.validator.validation_rules),
            "required_keys": len(self.validator.required_keys)
        }
    
    def get_current_state(self) -> Dict[str, Any]:
        """Get current state (read-only copy)"""
        return deepcopy(self.current_state)
    
    def get_state_history(self, limit: int = 100) -> List[StateChange]:
        """Get recent state change history"""
        return list(self.state_history)[-limit:]


# Global synchronizer instance
state_synchronizer = StateSynchronizer()