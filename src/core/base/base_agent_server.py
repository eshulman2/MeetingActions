"""Base agent server implementation for the Agents framework."""

import asyncio
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from fastapi import HTTPException
from langfuse import get_client as get_langfuse_client
from llama_index.core.memory import Memory
from llama_index.core.workflow import Context
from pydantic import BaseModel

from src.core.base.base_server import BaseServer
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


class ChatResponse(BaseModel):
    """The response model for the agent's answer."""

    response: str


class BaseAgentServer(BaseServer):
    """Base class for agent servers with registry integration."""

    def __init__(self, llm, title, description, auto_register: bool = True):
        super().__init__(llm, title, description)
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

    def _setup_agent_routes(self):
        """Setup common routes for all agent servers."""

        @self.app.post("/agent", response_model=ChatResponse)
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
            try:
                session_id = (
                    f"{getattr(self.service, 'name', 'agent')}" f"-endpoint-{uuid4()}"
                )

                mem = Memory.from_defaults(session_id=session_id)

                langfuse_client = get_langfuse_client()

                with langfuse_client.start_as_current_span(name=session_id) as span:

                    agent_response = await self.service.run(
                        request.query, ctx=Context(self.service), memory=mem
                    )

                    # Extract structured response if available, fallback to raw response
                    # This handles agents with output_cls that return structured formats
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
                return ChatResponse(response=str(res))
            # pylint: disable=duplicate-code
            except Exception as e:
                logger.error(f"Error in agent endpoint: {e}")
                raise HTTPException(
                    status_code=500, detail=f"Error processing query: {e}"
                ) from e

    def _setup_registry_routes(self):
        """Setup registry-related routes for agent discovery and capabilities."""

        @self.app.get("/info")
        async def get_info():
            """Return agent information and metadata."""
            return {
                "agent_id": self.agent_id,
                "name": self.app.title,
                "description": self.app.description,
                "version": self.app.version,
                "status": "active",
                "tools": [
                    tool.metadata.name for tool in getattr(self.service, "tools", [])
                ],
                "endpoint": f"http://{self.host}:{self.port}",
                "health_endpoint": (f"http://{self.host}:{self.port}/health"),
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

    async def _register_with_registry(self, max_retries: int = 3) -> bool:
        """Register this agent with the registry with retry logic."""
        for attempt in range(max_retries):
            try:
                agent_info = AgentInfo(
                    agent_id=self.agent_id,
                    name=self.app.title,
                    description=self.app.description,
                    endpoint=f"http://{self.host}:{self.port}",
                    health_endpoint=(f"http://{self.host}:{self.port}/health"),
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

                logger.warning(
                    f"Failed to register agent: {self.agent_id} "
                    f"(attempt {attempt + 1}/{max_retries})"
                )

            except Exception as e:
                logger.warning(
                    f"Error registering agent {self.agent_id} "
                    f"(attempt {attempt + 1}/{max_retries}): {e}"
                )

            # Wait before retrying (exponential backoff)
            if attempt < max_retries - 1:
                wait_time = 2**attempt  # 1s, 2s, 4s
                logger.info(f"Retrying registration in {wait_time} seconds...")
                await asyncio.sleep(wait_time)

        logger.error(
            f"Failed to register agent {self.agent_id} " f"after {max_retries} attempts"
        )
        return False

    async def _unregister_from_registry(self, max_retries: int = 2) -> bool:
        """Unregister this agent from the registry with retry logic."""
        for attempt in range(max_retries):
            try:
                success = await self.registry_client.unregister_agent(self.agent_id)
                if success:
                    logger.info(f"Successfully unregistered agent: {self.agent_id}")
                    return True

                logger.warning(
                    f"Agent {self.agent_id} was not found in registry "
                    f"(attempt {attempt + 1}/{max_retries})"
                )

            except Exception as e:
                logger.warning(
                    f"Error unregistering agent {self.agent_id} "
                    f"(attempt {attempt + 1}/{max_retries}): {e}"
                )

            # Wait before retrying (shorter backoff for unregistration)
            if attempt < max_retries - 1:
                wait_time = 1  # Just 1 second between retries for unregistration
                await asyncio.sleep(wait_time)

        logger.error(
            f"Failed to unregister agent {self.agent_id} "
            f"after {max_retries} attempts"
        )
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
