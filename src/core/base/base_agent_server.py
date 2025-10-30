"""Base agent server implementation providing common functionality for
all agent servers.

This module contains the BaseAgentServer class that extends BaseServer with
agent-specific
functionality including registry integration, heartbeat management, and standardized
agent endpoints for chat interactions and discovery.
"""

import asyncio
from abc import abstractmethod
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from fastapi import HTTPException
from langfuse import get_client as get_langfuse_client
from llama_index.core.agent.workflow import ReActAgent
from llama_index.core.memory import Memory
from llama_index.core.workflow import Context
from pydantic import BaseModel

from src.core.base.base_server import BaseServer
from src.core.base.error_handler import ErrorContext, handle_error_response
from src.core.base.exceptions import AgentError, MeetingActionsError
from src.core.schemas.agent_response import AgentResponse
from src.infrastructure.config import get_config
from src.infrastructure.logging.logging_config import get_logger
from src.infrastructure.observability.observability import set_up_langfuse
from src.infrastructure.registry.agent_registry import AgentInfo
from src.infrastructure.registry.registry_client import get_registry_client

set_up_langfuse()
logger = get_logger("agents.base")


class ChatQuery(BaseModel):
    """The request model for a user's query."""

    query: str


class BaseAgentServer(BaseServer):
    """Base class for agent servers with registry integration and heartbeat management.

    Extends BaseServer to provide agent-specific functionality including:
    - Single ReActAgent service instance
    - Automatic registration with the agent registry
    - Periodic heartbeat to maintain registry presence
    - Standardized agent chat endpoints
    - Agent discovery capabilities
    - Graceful startup and shutdown handling

    Attributes:
        service: The ReActAgent instance for this server.
    """

    def __init__(self, llm, title, description, auto_register: bool = True):
        super().__init__(llm, title, description)

        # Create the agent service - this must be done after super().__init__()
        # so that self.llm is available for create_service()
        self.service: ReActAgent = self.create_service()

        config = get_config()
        self.heartbeat_interval = config.config.heartbeat_interval
        self.host = config.config.host
        self.port = config.config.port
        self.auto_register = auto_register
        self.agent_id = f"{title.lower().replace(' ', '-')}-{uuid4().hex[:8]}"
        self.registry_client = get_registry_client()
        self._heartbeat_task: Optional[asyncio.Task[None]] = None

        self._setup_agent_routes()
        self._setup_registry_routes()

        # Register startup and shutdown events
        self.app.add_event_handler("startup", self._on_startup)
        self.app.add_event_handler("shutdown", self._on_shutdown)

    @abstractmethod
    def create_service(self) -> ReActAgent:
        """Create and configure the ReActAgent for this server.

        This method must be implemented by concrete agent server subclasses to
        create a ReActAgent instance with the appropriate tools and configuration.
        Use self.llm to access the language model instance.

        Returns:
            ReActAgent: The configured agent instance that will process requests.

        Example:
            ```python
            def create_service(self):
                return ReActAgent(
                    name="my-agent",
                    tools=my_tools,
                    llm=self.llm,  # Use self.llm
                    system_prompt="You are a helpful assistant",
                    output_cls=AgentResponse
                )
            ```
        """

    def _setup_agent_routes(self):
        """Setup common routes for all agent servers."""

        @self.app.post("/agent", response_model=AgentResponse)
        async def chat_with_agent(request: ChatQuery):
            """Main agent endpoint with context and memory.

            This endpoint processes user queries using the configured ReActAgent
            with persistent memory and full observability tracking. The response
            handling prioritizes structured_response when available, falling back
            to the raw agent response for compatibility with different agent types.

            Response Handling Logic:
            - Extracts 'structured_response' attribute from agent response if present
            - Falls back to raw agent_response if structured_response is not available
            - This ensures compatibility with agents that return structured formats
              while maintaining backward compatibility with simple string responses
            """
            logger.info(f"Agent endpoint called with query: {request.query[:100]}...")

            async with ErrorContext(
                "agent_request",
                agent_name=self.app.title,
                query_preview=request.query[:100],
            ):
                try:
                    session_id = (
                        f"{getattr(self.service, 'name', 'agent')}"
                        f"-endpoint-{uuid4()}"
                    )

                    mem = Memory.from_defaults(session_id=session_id)

                    langfuse_client = get_langfuse_client()

                    with langfuse_client.start_as_current_span(name=session_id) as span:

                        agent_response = await self.service.run(
                            request.query, ctx=Context(self.service), memory=mem
                        )

                        # Extract structured response if available,
                        # fallback to raw response
                        # This handles agents with output_cls that return
                        # structured formats
                        res = getattr(
                            agent_response,
                            "structured_response",
                            agent_response,
                        )

                        span.update_trace(
                            session_id=session_id,
                            input=request.query,
                            output=str(res),
                        )
                    langfuse_client.flush()

                    logger.info("Agent request processed successfully")

                    return AgentResponse(
                        response=res.get("response", str(res)),
                        error=res.get("error", True),
                        additional_info_required=res.get(
                            "additional_info_required", False
                        ),
                    )

                except AgentError as e:
                    # Handle our custom agent errors
                    logger.error(f"Agent error: {e.message}")
                    raise handle_error_response(e) from e

                except MeetingActionsError as e:
                    # Handle other custom errors
                    logger.error(f"Error in agent endpoint: {e.message}")
                    raise handle_error_response(e) from e

                # pylint: disable=duplicate-code
                except Exception as e:
                    logger.error(f"Unexpected error in agent endpoint: {e}")
                    raise HTTPException(
                        status_code=500, detail=f"Error processing query: {e}"
                    ) from e

    def _setup_registry_routes(self):
        """Setup registry-related routes for agent discovery and capabilities."""

        @self.app.get("/info")
        async def get_info():
            """Return agent information and metadata."""
            # Use 127.0.0.1 for endpoint if host is 0.0.0.0 (binding address)
            endpoint_host = "127.0.0.1" if self.host == "0.0.0.0" else self.host
            return {
                "agent_id": self.agent_id,
                "name": self.app.title,
                "description": self.app.description,
                "version": self.app.version,
                "status": "active",
                "tools": [
                    tool.metadata.name for tool in getattr(self.service, "tools", [])
                ],
                "endpoint": f"http://{endpoint_host}:{self.port}",
                "health_endpoint": (f"http://{endpoint_host}:{self.port}/health"),
            }

        @self.app.get("/discover")
        async def discover_agents():
            """Discover other agents."""
            try:
                agents = await self.registry_client.discover_agents()
                return {
                    "agents": [
                        {
                            "agent_id": agent.agent_id,
                            "name": agent.name,
                            "description": agent.description,
                            "endpoint": agent.endpoint,
                            "status": agent.status,
                        }
                        for agent in agents
                    ],
                    "total": len(agents),
                }
            except Exception as e:
                logger.error(f"Error discovering agents: {e}")
                raise HTTPException(
                    status_code=500, detail=f"Error discovering agents: {e}"
                ) from e

        @self.app.get("/health/circuits")
        async def circuit_breaker_health():
            """Check circuit breaker health status.

            Returns information about all circuit breakers including their
            current state, failure counts, and configuration.
            """
            # pylint: disable=import-outside-toplevel
            from src.core.base.circuit_breaker import get_all_circuit_breakers

            circuits = get_all_circuit_breakers()

            health = {
                "healthy": True,
                "circuits": {},
                "summary": {
                    "total": len(circuits),
                    "open": 0,
                    "half_open": 0,
                    "closed": 0,
                },
            }

            for name, breaker in circuits.items():
                stats = breaker.get_stats()
                health["circuits"][name] = stats

                # Track circuit states
                if stats["state"] == "open":
                    health["healthy"] = False
                    health["summary"]["open"] += 1
                elif stats["state"] == "half_open":
                    health["summary"]["half_open"] += 1
                else:
                    health["summary"]["closed"] += 1

            return health

    async def _on_startup(self) -> None:
        """Called when the FastAPI app starts up."""
        if self.auto_register:
            # Check if registry service is available
            registry_healthy = await self.registry_client.health_check()
            if not registry_healthy:
                logger.warning(
                    "Registry service is not healthy, but continuing "
                    "with registration attempts"
                )

            await self._register_with_registry()
            await self._start_heartbeat()

    async def _on_shutdown(self) -> None:
        """Called when the FastAPI app shuts down."""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        if self.auto_register:
            await self._unregister_from_registry()

    async def _register_with_registry(self) -> bool:
        """Register this agent with the registry.

        Retry logic is handled by the registry client's @with_retry decorator.
        """
        try:
            # Use 127.0.0.1 for endpoint if host is 0.0.0.0 (binding address)
            # so that other services can actually reach this agent
            endpoint_host = "127.0.0.1" if self.host == "0.0.0.0" else self.host

            agent_info = AgentInfo(
                agent_id=self.agent_id,
                name=self.app.title,
                description=self.app.description,
                endpoint=f"http://{endpoint_host}:{self.port}",
                health_endpoint=(f"http://{endpoint_host}:{self.port}/health"),
                version=self.app.version,
                status="active",
                last_heartbeat=datetime.now(timezone.utc),
                metadata={
                    "tools": [
                        tool.metadata.name
                        for tool in getattr(self.service, "tools", [])
                    ],
                    "max_iterations": getattr(self.service, "max_iterations", None),
                },
            )

            success = await self.registry_client.register_agent(agent_info)
            if success:
                logger.info(f"Successfully registered agent: {self.agent_id}")
                return True

            logger.warning(f"Failed to register agent: {self.agent_id}")
            return False

        except Exception as e:
            logger.error(f"Error registering agent {self.agent_id}: {e}")
            return False

    async def _unregister_from_registry(self) -> bool:
        """Unregister this agent from the registry.

        Retry logic is handled by the registry client's @with_retry decorator.
        """
        try:
            success = await self.registry_client.unregister_agent(self.agent_id)
            if success:
                logger.info(f"Successfully unregistered agent: {self.agent_id}")
                return True

            logger.warning(f"Failed to unregister agent: {self.agent_id}")
            return False

        except Exception as e:
            logger.error(f"Error unregistering agent {self.agent_id}: {e}")
            return False

    async def _start_heartbeat(self) -> None:
        """Start periodic heartbeat to registry."""
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeats to registry."""
        while True:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                success = await self.registry_client.heartbeat(self.agent_id)
                if not success:
                    logger.warning(f"Heartbeat failed for agent: {self.agent_id}")
                    # Try to re-register with retry logic
                    registration_success = await self._register_with_registry()
                    if not registration_success:
                        logger.error(
                            f"Failed to re-register agent {self.agent_id} "
                            f"after heartbeat failure"
                        )

            except asyncio.CancelledError:
                logger.info(f"Heartbeat cancelled for agent: {self.agent_id}")
                break
            except Exception as e:
                logger.error(f"Heartbeat error for agent {self.agent_id}: {e}")
                # Retry in 30 seconds on error
                await asyncio.sleep(30)
