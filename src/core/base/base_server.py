"""
Base agent server module providing common FastAPI functionality for all agents.
"""

import time
from abc import ABC, abstractmethod

from fastapi import FastAPI
from llama_index.core.agent.workflow import ReActAgent
from llama_index.core.workflow import Context, Workflow
from llama_index.llms.google_genai import GoogleGenAI
from llama_index.llms.openai import OpenAI
from llama_index.llms.openai_like import OpenAILike

from src.infrastructure.logging.logging_config import get_logger

logger = get_logger("agents.base")


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

        self.additional_routes()

        logger.info(f"{title} server initialized successfully")

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
