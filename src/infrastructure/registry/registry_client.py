"""HTTP client for agent registry operations"""

from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from src.infrastructure.config import get_config
from src.infrastructure.logging.logging_config import get_logger
from src.infrastructure.registry.agent_registry import AgentInfo

logger = get_logger("registry_client")


class RegistryClient:
    """HTTP client for interacting with the agent registry service"""

    def __init__(self):
        """Initialize the registry client with configuration"""
        config = get_config()
        self.registry_endpoint = str(config.config.registry_endpoint).rstrip("/")
        # 10 second timeout for HTTP requests
        self.timeout = 10.0
        logger.info(
            f"Registry client initialized with endpoint: " f"{self.registry_endpoint}"
        )

    async def register_agent(self, agent_info: AgentInfo) -> bool:
        """Register an agent with the registry service"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Convert AgentInfo to dict for JSON serialization
                # with datetime handling
                agent_data = agent_info.model_dump(mode="json")

                response = await client.post(
                    f"{self.registry_endpoint}/register", json=agent_data
                )
                response.raise_for_status()

                logger.info(f"Successfully registered agent: {agent_info.agent_id}")
                return True

        except httpx.TimeoutException:
            logger.error(
                f"Timeout registering agent {agent_info.agent_id} - "
                f"registry service unreachable"
            )
            return False
        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error registering agent {agent_info.agent_id}: "
                f"{e.response.status_code}"
            )
            return False
        except Exception as e:
            logger.error(f"Error registering agent {agent_info.agent_id}: {e}")
            return False

    async def discover_agents(self) -> List[AgentInfo]:
        """Discover all active agents from the registry service"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.registry_endpoint}/discover")
                response.raise_for_status()

                result = response.json()
                agents = []

                for agent_data in result["agents"]:
                    # Parse datetime string back to datetime object
                    if isinstance(agent_data.get("last_heartbeat"), str):
                        agent_data["last_heartbeat"] = datetime.fromisoformat(
                            agent_data["last_heartbeat"]
                        )
                    agents.append(AgentInfo(**agent_data))

                logger.debug(f"Discovered {len(agents)} agents from registry service")
                return agents

        except httpx.TimeoutException:
            logger.error("Timeout discovering agents - registry service unreachable")
            return []
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error discovering agents: {e.response.status_code}")
            return []
        except Exception as e:
            logger.error(f"Error discovering agents: {e}")
            return []

    async def heartbeat(self, agent_id: str) -> bool:
        """Send heartbeat for an agent to the registry service"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.registry_endpoint}/heartbeat/{agent_id}"
                )
                response.raise_for_status()

                logger.debug(f"Heartbeat successful for agent: {agent_id}")
                return True

        except httpx.TimeoutException:
            logger.error(
                f"Timeout sending heartbeat for {agent_id} - "
                f"registry service unreachable"
            )
            return False
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"Agent {agent_id} not found in registry")
            else:
                logger.error(
                    f"HTTP error sending heartbeat for {agent_id}: "
                    f"{e.response.status_code}"
                )
            return False
        except Exception as e:
            logger.error(f"Error sending heartbeat for {agent_id}: {e}")
            return False

    async def unregister_agent(self, agent_id: str) -> bool:
        """Unregister an agent from the registry service"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.delete(
                    f"{self.registry_endpoint}/agents/{agent_id}"
                )
                response.raise_for_status()

                logger.info(f"Successfully unregistered agent: {agent_id}")
                return True

        except httpx.TimeoutException:
            logger.error(
                f"Timeout unregistering agent {agent_id} - "
                f"registry service unreachable"
            )
            return False
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(
                    f"Agent {agent_id} not found in registry " f"for unregistration"
                )
                # Consider this success - agent is not registered
                return True
            else:
                logger.error(
                    f"HTTP error unregistering agent {agent_id}: "
                    f"{e.response.status_code}"
                )
            return False
        except Exception as e:
            logger.error(f"Error unregistering agent {agent_id}: {e}")
            return False

    async def get_agent(self, agent_id: str) -> Optional[AgentInfo]:
        """Get specific agent information from the registry service"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.registry_endpoint}/agents/{agent_id}"
                )
                response.raise_for_status()

                agent_data = response.json()

                # Parse datetime string back to datetime object
                if isinstance(agent_data.get("last_heartbeat"), str):
                    agent_data["last_heartbeat"] = datetime.fromisoformat(
                        agent_data["last_heartbeat"]
                    )

                return AgentInfo(**agent_data)

        except httpx.TimeoutException:
            logger.error(
                f"Timeout getting agent {agent_id} - " f"registry service unreachable"
            )
            return None
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.debug(f"Agent {agent_id} not found in registry")
            else:
                logger.error(
                    f"HTTP error getting agent {agent_id}: " f"{e.response.status_code}"
                )
            return None
        except Exception as e:
            logger.error(f"Error getting agent {agent_id}: {e}")
            return None

    async def get_registry_stats(self) -> Dict[str, Any]:
        """Get registry statistics from the registry service"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.registry_endpoint}/stats")
                response.raise_for_status()

                return response.json()

        except httpx.TimeoutException:
            logger.error(
                "Timeout getting registry stats - " "registry service unreachable"
            )
            return {"error": "Registry service unreachable"}
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error getting registry stats: {e.response.status_code}")
            return {"error": f"HTTP {e.response.status_code}"}
        except Exception as e:
            logger.error(f"Error getting registry stats: {e}")
            return {"error": str(e)}

    async def health_check(self) -> bool:
        """Check if the registry service is healthy and reachable"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.registry_endpoint}/health")
                response.raise_for_status()

                result = response.json()
                is_healthy = result.get("status") == "healthy"
                logger.debug(
                    f"Registry health check: "
                    f"{'healthy' if is_healthy else 'unhealthy'}"
                )
                return is_healthy

        except httpx.TimeoutException:
            logger.warning("Registry service health check timeout")
            return False
        except httpx.HTTPStatusError as e:
            logger.warning(
                f"Registry service health check failed: " f"{e.response.status_code}"
            )
            return False
        except Exception as e:
            logger.warning(f"Registry service health check error: {e}")
            return False


def get_registry_client() -> RegistryClient:
    """Get a registry client instance

    Returns:
        RegistryClient: The registry client instance
    """
    return RegistryClient()
