"""Action items server"""

from typing import Any
from uuid import uuid4

import uvicorn
from fastapi import HTTPException
from langfuse import get_client as get_langfuse_client
from pydantic import BaseModel, PastDate

from src.core.base.base_workflow_server import BaseWorkflowServer
from src.core.schemas.workflow_models import ActionItemsList
from src.core.workflows.action_items_dispatch_orchestrator import (
    ActionItemsDispatchOrchestrator,
)
from src.core.workflows.meeting_notes_and_generation_orchestrator import (
    MeetingNotesAndGenerationOrchestrator,
)
from src.infrastructure.config import get_config, get_model
from src.infrastructure.logging.logging_config import get_logger
from src.infrastructure.observability.observability import set_up_langfuse

set_up_langfuse()
logger = get_logger("workflow_server.action_items")
config = get_config()


class Meeting(BaseModel):
    """Request model for meeting information.

    Attributes:
        meeting: Name or identifier of the meeting
        date: Date of the meeting in string format
    """

    meeting: str
    date: PastDate


class ActionItemsResponse(BaseModel):
    """Response model for workflow output.

    Attributes:
        action_items: Dictionary containing structured action items
    """

    action_items: Any


class DispatchRequest(BaseModel):
    """Request model for dispatching action items to agents.

    Attributes:
        action_items: ActionItemsList to dispatch
    """

    action_items: ActionItemsList


class DispatchResponse(BaseModel):
    """Response model for dispatch results.

    Attributes:
        results: List of agent execution results
    """

    results: Any


class ActionItemsServer(BaseWorkflowServer):
    """Action items workflow server implementation.

    This server provides endpoints for generating action items from meetings
    and dispatching them to agents. It uses workflow orchestrators created
    per-request rather than a single persistent service.
    """

    def additional_routes(self):

        @self.app.post("/generate", response_model=ActionItemsResponse)
        async def generate_action_items_endpoint(request: Meeting):
            """FastAPI endpoint for generating action items only (no agent dispatch).

            This endpoint retrieves meeting notes and generates action items without
            dispatching them to agents. Useful for reviewing action items before
            execution.

            Args:
                request: Meeting request containing meeting name and date

            Returns:
                ActionItemsResponse with generated action items

            Raises:
                HTTPException: If workflow execution fails
            """
            logger.info(
                f"Generating action items for meeting: {request.meeting}, "
                f"date: {request.date}"
            )
            try:
                session_id = f"generate-action-items-{str(uuid4())}"
                langfuse_client = get_langfuse_client()

                with langfuse_client.start_as_current_span(name=session_id) as span:
                    # Initialize generation workflow
                    generation_workflow = MeetingNotesAndGenerationOrchestrator(
                        llm=self.llm,
                        timeout=600,
                        verbose=True,
                        max_iterations=5,
                    )

                    res = await generation_workflow.run(
                        meeting=request.meeting, date=request.date
                    )

                    span.update_trace(
                        session_id=session_id,
                        input=(
                            f"meeting: {request.meeting}, "
                            f"date: {request.date.strftime('%Y-%m-%d')}"
                        ),
                        output=str(res),
                    )
                langfuse_client.flush()

                if getattr(res, "error", False):
                    raise HTTPException(status_code=500, detail=f"{res.result}")

                logger.info("Action items generation completed successfully")
                return ActionItemsResponse(action_items=res.result)
            except Exception as e:
                logger.error(f"Error generating action items: {e}")
                raise HTTPException(
                    status_code=500, detail=f"Error generating action items: {e}"
                ) from e

        @self.app.post("/dispatch", response_model=DispatchResponse)
        async def dispatch_action_items_endpoint(request: DispatchRequest):
            """FastAPI endpoint for dispatching action items to agents.

            This endpoint takes pre-generated action items and dispatches them to
            appropriate agents for execution.

            Args:
                request: DispatchRequest containing action items to dispatch

            Returns:
                DispatchResponse with execution results

            Raises:
                HTTPException: If workflow execution fails
            """
            logger.info(
                f"Dispatching {len(request.action_items.action_items)} "
                "action items to agents"
            )
            try:
                session_id = f"dispatch-action-items-{str(uuid4())}"
                langfuse_client = get_langfuse_client()

                with langfuse_client.start_as_current_span(name=session_id) as span:
                    # Initialize dispatch workflow
                    dispatch_workflow = ActionItemsDispatchOrchestrator(
                        llm=self.llm,
                        timeout=300,
                        verbose=True,
                    )

                    res = await dispatch_workflow.run(action_items=request.action_items)

                    span.update_trace(
                        session_id=session_id,
                        input=str(request.action_items),
                        output=str(res),
                    )
                langfuse_client.flush()

                if getattr(res, "error", False):
                    raise HTTPException(status_code=500, detail=f"{res.result}")

                logger.info("Action items dispatch completed successfully")
                return DispatchResponse(results=res.result)
            except Exception as e:
                logger.error(f"Error dispatching action items: {e}")
                raise HTTPException(
                    status_code=500, detail=f"Error dispatching action items: {e}"
                ) from e


# Initialize the server
logger.info("Initializing Action Items Workflow server")
server = ActionItemsServer(
    llm=get_model(config.config),
    title="Action Items Workflow",
    description=("llamaindex workflow for taking meeting notes and process them"),
)
app = server.app
logger.info("Action Items Workflow server initialized successfully")

if __name__ == "__main__":
    uvicorn.run(app, host=config.config.host, port=config.config.port, log_level="info")
