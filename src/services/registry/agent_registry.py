"""Agent registry implementation using Redis for persistence."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from src.infrastructure.cache import get_cache
from src.infrastructure.logging.logging_config import get_logger
from src.shared.common.singleton_meta import SingletonMeta

logger = get_logger("agent_registry")


class AgentInfo(BaseModel):
    """Model representing agent information in the registry."""

    agent_id: str
    name: str
    description: str
    endpoint: str
    health_endpoint: str
    version: str
    status: str = "active"
    last_heartbeat: datetime
    metadata: Dict[str, Any] = {}

    class Config:
        """Pydantic configuration for AgentInfo model."""

        json_encoders = {datetime: lambda v: v.isoformat()}


class AgentRegistry(metaclass=SingletonMeta):
    """Singleton Agent Registry using enhanced Redis cache."""

    def __init__(self):
        """Initialize registry with Redis cache"""
        if hasattr(self, "_initialized"):
            return

        self._initialized = True
        try:
            self.cache = get_cache()
            # Set TTL to 10 minutes to match cleanup interval
            self.agent_ttl = 600  # 10 minutes TTL
            # Test Redis connection
            self.cache.redis_client.ping()
            logger.info("Agent Registry initialized with Redis connection")
        except Exception as e:
            logger.error(f"Failed to initialize Redis connection: {e}")
            self.cache = None
            logger.warning(
                "Agent Registry running in degraded mode without persistence"
            )

    def _agent_key(self, agent_id: str) -> str:
        """Generate Redis key for agent"""
        return f"agent:registry:{agent_id}"

    def _all_agents_key(self) -> str:
        """Generate Redis key for all agents set"""
        return "agent:registry:all"

    def register_agent(self, agent_info: AgentInfo) -> bool:
        """Register an agent in the registry"""
        if not self.cache:
            logger.warning(
                f"Cannot register agent {agent_info.agent_id}: Redis unavailable"
            )
            return False

        try:
            # Update last heartbeat
            agent_info.last_heartbeat = datetime.now(timezone.utc)

            # Store agent data with TTL
            agent_key = self._agent_key(agent_info.agent_id)
            # Use model_dump with mode='json' to properly serialize datetime
            agent_data = agent_info.model_dump(mode="json")

            success = self.cache.set_json(agent_key, agent_data, self.agent_ttl)
            if not success:
                logger.error(f"Failed to store agent {agent_info.agent_id} in Redis")
                return False

            # Add to all agents set
            all_agents_key = self._all_agents_key()
            self.cache.redis_client.sadd(all_agents_key, agent_info.agent_id)
            self.cache.expire(all_agents_key, self.agent_ttl)

            logger.info(f"Registered agent: {agent_info.name} at {agent_info.endpoint}")
            return True

        except Exception as e:
            logger.error(f"Error registering agent {agent_info.agent_id}: {e}")
            return False

    def discover_agents(self) -> List[AgentInfo]:
        """Discover all active agents"""
        if not self.cache:
            logger.warning("Cannot discover agents: Redis unavailable")
            return []

        try:
            # Get all agents
            all_agents_key = self._all_agents_key()
            agent_ids = self.cache.redis_client.smembers(all_agents_key)

            agents = []
            for agent_id in agent_ids:
                agent_data = self.get_agent(agent_id)
                if agent_data and agent_data.status == "active":
                    agents.append(agent_data)

            logger.debug(f"Discovered {len(agents)} active agents")
            return agents

        except Exception as e:
            logger.error(f"Error discovering agents: {e}")
            return []

    def get_agent(self, agent_id: str) -> Optional[AgentInfo]:
        """Get specific agent by ID"""
        if not self.cache:
            logger.warning(f"Cannot get agent {agent_id}: Redis unavailable")
            return None

        try:
            agent_key = self._agent_key(agent_id)
            agent_data = self.cache.get_json(agent_key)

            if agent_data:
                # Parse datetime string back to datetime object
                if isinstance(agent_data.get("last_heartbeat"), str):
                    agent_data["last_heartbeat"] = datetime.fromisoformat(
                        agent_data["last_heartbeat"]
                    )
                return AgentInfo(**agent_data)
            return None

        except Exception as e:
            logger.error(f"Error getting agent {agent_id}: {e}")
            return None

    def heartbeat(self, agent_id: str) -> bool:
        """Update agent heartbeat"""
        if not self.cache:
            logger.warning(f"Cannot update heartbeat for {agent_id}: Redis unavailable")
            return False

        try:
            agent = self.get_agent(agent_id)
            if not agent:
                logger.warning(f"Heartbeat for unknown agent: {agent_id}")
                return False

            # Update heartbeat timestamp
            agent.last_heartbeat = datetime.now(timezone.utc)

            # Store updated agent data
            return self.register_agent(agent)

        except Exception as e:
            logger.error(f"Error updating heartbeat for {agent_id}: {e}")
            return False

    def unregister_agent(self, agent_id: str) -> bool:
        """Remove agent from registry"""
        if not self.cache:
            logger.warning(f"Cannot unregister agent {agent_id}: Redis unavailable")
            return False

        try:
            agent = self.get_agent(agent_id)
            if not agent:
                return False

            # Remove from all agents set
            all_agents_key = self._all_agents_key()
            self.cache.redis_client.srem(all_agents_key, agent_id)

            # Remove agent data
            agent_key = self._agent_key(agent_id)
            self.cache.delete(agent_key)

            logger.info(f"Unregistered agent: {agent_id}")
            return True

        except Exception as e:
            logger.error(f"Error unregistering agent {agent_id}: {e}")
            return False

    def cleanup_stale_agents(self, max_age_minutes: int = 10) -> int:
        """Remove agents that haven't sent heartbeats"""
        if not self.cache:
            logger.warning("Cannot cleanup stale agents: Redis unavailable")
            return 0

        try:
            stale_threshold = datetime.now(timezone.utc) - timedelta(
                minutes=max_age_minutes
            )
            stale_count = 0

            # Get all agent IDs
            all_agents_key = self._all_agents_key()
            agent_ids = self.cache.redis_client.smembers(all_agents_key)

            for agent_id in agent_ids:
                agent = self.get_agent(agent_id)
                if agent and agent.last_heartbeat < stale_threshold:
                    logger.info(f"Removing stale agent: {agent_id}")
                    self.unregister_agent(agent_id)
                    stale_count += 1

            if stale_count > 0:
                logger.info(f"Cleaned up {stale_count} stale agents")

            return stale_count

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            return 0

    def get_registry_stats(self) -> Dict[str, Any]:
        """Get registry statistics"""
        if not self.cache:
            return {
                "total_agents": 0,
                "registry_enabled": False,
                "error": "Redis unavailable",
            }

        try:
            all_agents_key = self._all_agents_key()
            total_agents = self.cache.redis_client.scard(all_agents_key) or 0

            return {
                "total_agents": total_agents,
                "registry_enabled": self.cache.enabled,
            }

        except Exception as e:
            logger.error(f"Error getting registry stats: {e}")
            return {"error": str(e)}
