"""
State Manager - Persistent state storage for agents and world model
"""
import asyncio
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import redis.asyncio as redis
import structlog
from sqlalchemy import JSON, Column, DateTime, Float, Integer, String
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

logger = structlog.get_logger(__name__)

Base = declarative_base()


class WorldState(Base):
    """SQLAlchemy model for world state snapshots"""

    __tablename__ = "world_states"

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    bot_position_x = Column(Float)
    bot_position_y = Column(Float)
    bot_position_z = Column(Float)
    dimension = Column(String, default="overworld")
    nearby_players = Column(JSON)
    inventory = Column(JSON)
    metadata = Column(JSON)


class TaskState(Base):
    """SQLAlchemy model for task persistence"""

    __tablename__ = "task_states"

    id = Column(String, primary_key=True)
    agent_name = Column(String)
    task_type = Column(String)
    status = Column(String)  # pending, in_progress, completed, failed
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    parameters = Column(JSON)
    result = Column(JSON)
    checkpoint_data = Column(JSON)


class StateManager:
    """Manages persistent state across agents and sessions"""

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        sqlite_url: str = "sqlite+aiosqlite:///minecraft_state.db",
    ):
        self.redis_url = redis_url
        self.sqlite_url = sqlite_url
        self.redis_client = None
        self.db_engine = None
        self.db_session_maker = None
        self._initialized = False

    async def initialize(self):
        """Initialize database connections"""
        if self._initialized:
            return

        logger.info("Initializing state manager")

        # Initialize Redis
        try:
            self.redis_client = await redis.from_url(self.redis_url)
            await self.redis_client.ping()
            logger.info("Redis connection established")
        except Exception as e:
            logger.warning(f"Redis connection failed, using memory-only mode: {e}")
            self.redis_client = None

        # Initialize SQLite
        self.db_engine = create_async_engine(self.sqlite_url, echo=False)
        self.db_session_maker = sessionmaker(
            self.db_engine, class_=AsyncSession, expire_on_commit=False
        )

        # Create tables
        async with self.db_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        self._initialized = True
        logger.info("State manager initialized")

    async def save_world_snapshot(self, world_data: Dict[str, Any]):
        """Save a snapshot of the world state"""
        async with self.db_session_maker() as session:
            snapshot = WorldState(
                bot_position_x=world_data.get("bot_position", {}).get("x", 0),
                bot_position_y=world_data.get("bot_position", {}).get("y", 0),
                bot_position_z=world_data.get("bot_position", {}).get("z", 0),
                dimension=world_data.get("dimension", "overworld"),
                nearby_players=world_data.get("players", []),
                inventory=world_data.get("inventory", {}),
                metadata=world_data.get("metadata", {}),
            )
            session.add(snapshot)
            await session.commit()

        # Also cache in Redis for fast access
        if self.redis_client:
            await self.redis_client.setex(
                "world:latest", 300, json.dumps(world_data)  # 5 minute TTL
            )

    async def get_latest_world_state(self) -> Optional[Dict[str, Any]]:
        """Get the most recent world state"""
        # Try Redis first
        if self.redis_client:
            cached = await self.redis_client.get("world:latest")
            if cached:
                return json.loads(cached)

        # Fall back to database
        async with self.db_session_maker() as session:
            result = await session.execute(
                "SELECT * FROM world_states ORDER BY timestamp DESC LIMIT 1"
            )
            row = result.first()

            if row:
                return {
                    "bot_position": {
                        "x": row.bot_position_x,
                        "y": row.bot_position_y,
                        "z": row.bot_position_z,
                    },
                    "dimension": row.dimension,
                    "players": row.nearby_players,
                    "inventory": row.inventory,
                    "metadata": row.metadata,
                    "timestamp": row.timestamp.isoformat(),
                }

        return None

    async def create_task(self, agent_name: str, task_type: str, parameters: Dict[str, Any]) -> str:
        """Create a new persistent task"""
        task_id = f"{agent_name}_{task_type}_{datetime.now().timestamp()}"

        async with self.db_session_maker() as session:
            task = TaskState(
                id=task_id,
                agent_name=agent_name,
                task_type=task_type,
                status="pending",
                parameters=parameters,
                checkpoint_data={},
            )
            session.add(task)
            await session.commit()

        # Cache in Redis
        if self.redis_client:
            await self.redis_client.hset(
                f"task:{task_id}",
                mapping={
                    "agent_name": agent_name,
                    "task_type": task_type,
                    "status": "pending",
                    "parameters": json.dumps(parameters),
                },
            )

        logger.info(f"Created task {task_id}")
        return task_id

    async def update_task_status(
        self, task_id: str, status: str, result: Optional[Dict[str, Any]] = None
    ):
        """Update task status"""
        async with self.db_session_maker() as session:
            task = await session.get(TaskState, task_id)
            if task:
                task.status = status
                if result:
                    task.result = result
                await session.commit()

        # Update Redis
        if self.redis_client:
            await self.redis_client.hset(
                f"task:{task_id}",
                mapping={"status": status, "result": json.dumps(result) if result else "{}"},
            )

    async def checkpoint_task(self, task_id: str, checkpoint_data: Dict[str, Any]):
        """Save task checkpoint for recovery"""
        async with self.db_session_maker() as session:
            task = await session.get(TaskState, task_id)
            if task:
                task.checkpoint_data = checkpoint_data
                await session.commit()

        # Cache checkpoint
        if self.redis_client:
            await self.redis_client.setex(
                f"checkpoint:{task_id}", 3600, json.dumps(checkpoint_data)  # 1 hour TTL
            )

        logger.debug(f"Checkpointed task {task_id}")

    async def get_task_checkpoint(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve task checkpoint"""
        # Try Redis first
        if self.redis_client:
            cached = await self.redis_client.get(f"checkpoint:{task_id}")
            if cached:
                return json.loads(cached)

        # Fall back to database
        async with self.db_session_maker() as session:
            task = await session.get(TaskState, task_id)
            if task and task.checkpoint_data:
                return task.checkpoint_data

        return None

    async def get_pending_tasks(self, agent_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all pending tasks, optionally filtered by agent"""
        async with self.db_session_maker() as session:
            query = "SELECT * FROM task_states WHERE status IN ('pending', 'in_progress')"
            if agent_name:
                query += f" AND agent_name = '{agent_name}'"

            result = await session.execute(query)

            tasks = []
            for row in result:
                tasks.append(
                    {
                        "id": row.id,
                        "agent_name": row.agent_name,
                        "task_type": row.task_type,
                        "status": row.status,
                        "parameters": row.parameters,
                        "created_at": row.created_at.isoformat(),
                    }
                )

            return tasks

    async def store_agent_memory(
        self, agent_name: str, memory_key: str, memory_data: Any, ttl: int = 3600
    ):
        """Store agent-specific memory with TTL"""
        key = f"agent:{agent_name}:memory:{memory_key}"

        if self.redis_client:
            if isinstance(memory_data, (dict, list)):
                memory_data = json.dumps(memory_data)

            await self.redis_client.setex(key, ttl, memory_data)
        else:
            # Fallback to in-memory storage
            logger.warning("Redis not available, memory storage is temporary")

    async def get_agent_memory(self, agent_name: str, memory_key: str) -> Optional[Any]:
        """Retrieve agent-specific memory"""
        if self.redis_client:
            key = f"agent:{agent_name}:memory:{memory_key}"
            data = await self.redis_client.get(key)

            if data:
                try:
                    return json.loads(data)
                except json.JSONDecodeError:
                    return data.decode("utf-8") if isinstance(data, bytes) else data

        return None

    async def cleanup_old_data(self, days: int = 7):
        """Clean up old data from database"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        async with self.db_session_maker() as session:
            # Delete old world snapshots
            await session.execute(
                f"DELETE FROM world_states WHERE timestamp < '{cutoff_date.isoformat()}'"
            )

            # Delete completed tasks older than cutoff
            await session.execute(
                f"DELETE FROM task_states WHERE status IN ('completed', 'failed') "
                f"AND updated_at < '{cutoff_date.isoformat()}'"
            )

            await session.commit()

        logger.info(f"Cleaned up data older than {days} days")

    async def close(self):
        """Close database connections"""
        if self.redis_client:
            await self.redis_client.close()

        if self.db_engine:
            await self.db_engine.dispose()

        logger.info("State manager closed")


# Session recovery helper
class SessionRecovery:
    """Helper for recovering agent sessions after failures"""

    def __init__(self, state_manager: StateManager):
        self.state_manager = state_manager

    async def save_session_checkpoint(
        self, session_id: str, agent_name: str, session_data: Dict[str, Any]
    ):
        """Save session checkpoint"""
        checkpoint = {
            "session_id": session_id,
            "agent_name": agent_name,
            "timestamp": datetime.utcnow().isoformat(),
            "state": session_data.get("state", {}),
            "current_task": session_data.get("current_task"),
            "completed_tasks": session_data.get("completed_tasks", []),
        }

        await self.state_manager.store_agent_memory(
            agent_name, f"session_{session_id}", checkpoint, ttl=7200  # 2 hours
        )

    async def recover_session(self, session_id: str, agent_name: str) -> Optional[Dict[str, Any]]:
        """Recover session from checkpoint"""
        checkpoint = await self.state_manager.get_agent_memory(agent_name, f"session_{session_id}")

        if checkpoint:
            logger.info(f"Recovered session {session_id} for {agent_name}")
            return checkpoint

        return None
