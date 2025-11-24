"""
Base server module providing common FastAPI functionality for all servers.
"""

import time
from abc import ABC, abstractmethod

from fastapi import FastAPI

from src.infrastructure.logging.logging_config import get_logger

logger = get_logger("servers.base")


class BaseServer(ABC):
    """Base class for all servers with common FastAPI functionality.

    This class provides common FastAPI setup and routing for both agent-based
    and workflow-based servers. Subclasses should extend either BaseAgentServer
    or BaseWorkflowServer depending on their needs.

    Attributes:
        llm: The language model instance available to subclasses.
        app: The FastAPI application instance.
    """

    def __init__(self, llm, title: str, description: str):
        """Initialize the base server with FastAPI app configuration.

        Sets up the FastAPI application and common routes. Subclasses are
        responsible for creating their service instances if needed.

        Args:
            llm: The language model instance to use.
            title: The title for the FastAPI application.
            description: The description for the FastAPI application.
        """
        logger.info(f"Initializing {title} server")
        self.llm = llm
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
