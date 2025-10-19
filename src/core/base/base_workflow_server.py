"""Base workflow server implementation providing common functionality for
workflow-based servers.

This module contains the BaseWorkflowServer class that extends BaseServer for
servers that use multiple workflow orchestrators instead of a single agent service.
"""

from src.core.base.base_server import BaseServer
from src.infrastructure.logging.logging_config import get_logger

logger = get_logger("workflows.base")


class BaseWorkflowServer(BaseServer):
    """Base class for workflow servers that use multiple workflow orchestrators.

    This class extends BaseServer but does not require a single service instance.
    Instead, workflow servers create workflow orchestrators on-demand within
    their endpoints.

    Key differences from BaseAgentServer:
    - No create_service() requirement
    - No registry integration
    - No heartbeat management
    - Workflows are created per-request in endpoints

    Example:
        class MyWorkflowServer(BaseWorkflowServer):
            def additional_routes(self):
                @self.app.post("/my-endpoint")
                async def my_endpoint(request: Request):
                    # Create workflow on-demand
                    workflow = MyWorkflow(llm=self.llm)
                    result = await workflow.run(data=request.data)
                    return result
    """

    def __init__(self, llm, title: str, description: str):
        """Initialize the workflow server.

        Args:
            llm: Language model instance to use for workflows
            title: The title for the FastAPI application
            description: The description for the FastAPI application
        """
        logger.info(f"Initializing {title} workflow server")
        super().__init__(llm, title, description)
        logger.info(f"{title} workflow server initialized successfully")
