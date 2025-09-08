"""
Base agent server module providing common FastAPI functionality for all agents.
"""

import time
from abc import ABC, abstractmethod
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from langfuse import get_client as get_langfuse_client
from llama_index.core.agent.workflow import ReActAgent
from llama_index.core.memory import Memory
from llama_index.core.workflow import Context, Workflow
from llama_index.llms.google_genai import GoogleGenAI
from llama_index.llms.openai import OpenAI
from llama_index.llms.openai_like import OpenAILike
from pydantic import BaseModel

from src.infrastructure.logging.logging_config import get_logger

logger = get_logger("agents.base")
langfuse_client = get_langfuse_client()


class ChatQuery(BaseModel):
    """The request model for a user's query."""

    query: str


class ChatResponse(BaseModel):
    """The response model for the agent's answer."""

    response: str


class BaseServer(ABC):
    """Base class for agent servers with common FastAPI functionality."""

    def __init__(self, llm, title: str, description: str):
        """Initialize the base server with FastAPI app and service configuration.

        Sets up the FastAPI application, creates the service instance (agent or
        workflow), configures routing based on service type, and initializes
        the workflow context.

        Args:
            llm: The language model instance to pass to the service.
            title: The title for the FastAPI application.
            description: The description for the FastAPI application.
        """
        logger.info(f"Initializing {title} server")
        self.service = self.create_service(llm)
        self.ctx = Context(self.service)
        self.app = FastAPI(
            title=title,
            description=description,
            version="1.0.0",
        )

        self._setup_common_routes()
        if isinstance(self.service, ReActAgent):
            self._setup_agent_routes()
        self.additional_routes()

        logger.info(f"{title} agent server initialized successfully")

    def _setup_common_routes(self):
        """Setup common routes for all servers."""

        @self.app.get("/description")
        async def description_endpoint():
            """Get the server description.

            Returns:
                str: The description of this server instance as configured
                during initialization.
            """
            return self.app.description

        @self.app.get("/")
        async def root():
            """Root endpoint to confirm API is running."""
            logger.debug("Root endpoint accessed")
            return {
                "message": f"{self.app.title}, "
                "API is running. Go to /docs for interactive documentation."
            }

        @self.app.get("/health")
        async def health_check():
            """Health check endpoint for monitoring and load balancer status.

            Returns:
                dict: Health status information including service status,
                timestamp, and basic service metadata.
            """
            logger.debug("Health check endpoint accessed")
            return {
                "status": "healthy",
                "service": self.app.title,
                "version": self.app.version,
                "timestamp": time.time(),
            }

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
                session_id = f"{getattr(
                    self.service, 'name', 'agent')}-endpoint-{uuid4()}"

                mem = Memory.from_defaults(session_id=session_id)

                with langfuse_client.start_as_current_span(name=session_id) as span:

                    agent_response = await self.service.run(
                        request.query, ctx=self.ctx, memory=mem
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

    @abstractmethod
    def create_service(
        self, llm: OpenAI | GoogleGenAI | OpenAILike
    ) -> ReActAgent | Workflow:
        """Create and configure the service instance for this server.

        This method must be implemented by concrete subclasses to create either
        a ReActAgent or Workflow instance that will handle the core business logic.

        Args:
            llm: The language model instance to use. Can be OpenAI, GoogleGenAI,
                 or OpenAILike compatible model.

        Returns:
            ReActAgent | Workflow: The configured service instance that will
            process requests. ReActAgent instances will automatically get
            agent-specific routes (/test, /agent), while Workflow instances
            will only get common routes.

        Example:
            For an agent:
            ```python
            def create_service(self, llm):
                return ReActAgent(
                    name="my-agent",
                    tools=my_tools,
                    llm=llm,
                    system_prompt="You are a helpful assistant"
                )
            ```

            For a workflow:
            ```python
            def create_service(self, llm):
                return MyWorkflow(llm=llm, timeout=30)
            ```
        """

    @abstractmethod
    def additional_routes(self):
        """Define additional custom routes specific to this server implementation.

        This method must be implemented by concrete subclasses to add any
        custom FastAPI routes beyond the common ones provided by the base class.
        The method should use self.app to register new routes.

        Common routes provided by base class:
        - GET /: Root endpoint with server information
        - GET /description: Returns server description
        - POST /test: Test endpoint (ReActAgent only)
        - POST /agent: Main agent endpoint with memory (ReActAgent only)

        Example:
            ```python
            def additional_routes(self):
                @self.app.post("/custom-endpoint")
                async def custom_endpoint(request: CustomRequest):
                    # Custom logic here
                    result = await self.service.run(custom_param=request.param)
                    return CustomResponse(result=result)

                @self.app.get("/health")
                async def health_check():
                    return {"status": "healthy"}
            ```

        Note:
            - Use appropriate response models for type safety
            - Include proper error handling with HTTPException
            - Add logging for observability
            - Consider adding Langfuse tracing for monitoring
        """
