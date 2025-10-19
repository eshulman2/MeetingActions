"""Meeting Notes and Action Items Generation Orchestrator.

This workflow orchestrates the retrieval of meeting notes and generation of
action items. It composes the MeetingNotesWorkflow and
ActionItemsGenerationWorkflow.
"""

from typing import Any

from llama_index.core.workflow import (
    Event,
    StartEvent,
    Workflow,
    step,
)

from src.core.schemas.workflow_models import ActionItemsList
from src.core.workflows.common_events import StopWithErrorEvent
from src.core.workflows.sub_workflows.action_items_generation_workflow import (
    ActionItemsGenerationWorkflow,
)
from src.core.workflows.sub_workflows.meeting_notes_workflow import MeetingNotesWorkflow
from src.infrastructure.logging.logging_config import get_logger

logger = get_logger("workflows.meeting_notes_and_generation")


class MeetingNotesRetrieved(Event):
    """Event indicating meeting notes have been retrieved."""

    meeting_notes: str


class MeetingNotesAndGenerationOrchestrator(Workflow):
    """Orchestrator workflow for retrieving meeting notes and generating action items.

    This workflow provides:
    1. Meeting notes retrieval via MeetingNotesWorkflow
    2. Action items generation via ActionItemsGenerationWorkflow
    3. Centralized error handling and logging
    """

    def __init__(
        self,
        llm,
        *args: Any,
        max_iterations: int = 3,
        **kwargs: Any,
    ):
        """Initialize the orchestrator workflow.

        Args:
            llm: Language model for sub-workflows
            max_iterations: Maximum number of refinement iterations
        """
        super().__init__(*args, **kwargs)
        self.llm = llm
        self.max_iterations = max_iterations

        logger.info(
            f"Initialized MeetingNotesAndGenerationOrchestrator with "
            f"max_iterations: {max_iterations}"
        )

    @step
    async def retrieve_meeting_notes(
        self, event: StartEvent
    ) -> MeetingNotesRetrieved | StopWithErrorEvent:
        """Retrieve meeting notes using the MeetingNotesWorkflow.

        Args:
            event: StartEvent with 'meeting' and 'date' parameters

        Returns:
            MeetingNotesRetrieved event or StopWithErrorEvent on failure
        """
        logger.info(
            f"Retrieving meeting notes for meeting: {event['meeting']}, "
            f"date: {event['date']}"
        )

        try:
            # Initialize and run the meeting notes workflow
            meeting_notes_workflow = MeetingNotesWorkflow(llm=self.llm)

            meeting_notes_result = await meeting_notes_workflow.run(
                date=event.date, meeting=event.meeting
            )

            # Handle workflow result
            if hasattr(meeting_notes_result, "error") and meeting_notes_result.error:
                logger.error(
                    f"Meeting notes workflow failed: {meeting_notes_result.result}"
                )
                return StopWithErrorEvent(
                    result=meeting_notes_result.result, error=True
                )

            # Extract content
            meeting_notes_content = (
                meeting_notes_result.result
                if hasattr(meeting_notes_result, "result")
                else str(meeting_notes_result)
            )

            # Validate content
            if (
                not isinstance(meeting_notes_content, str)
                or not meeting_notes_content.strip()
            ):
                logger.warning("Meeting notes content is empty or invalid")
                return StopWithErrorEvent(result="empty_meeting_notes", error=True)

            logger.info(
                "Successfully retrieved meeting notes "
                f"({len(meeting_notes_content)} chars)"
            )

            return MeetingNotesRetrieved(meeting_notes=meeting_notes_content)

        except Exception as e:
            logger.error(f"Error retrieving meeting notes: {e}")
            return StopWithErrorEvent(result="meeting_notes_error", error=True)

    @step
    async def generate_action_items(
        self, event: MeetingNotesRetrieved
    ) -> StopWithErrorEvent:
        """Generate action items using the ActionItemsGenerationWorkflow.

        Args:
            event: MeetingNotesRetrieved event with meeting notes content

        Returns:
            StopWithErrorEvent with ActionItemsList result or error
        """
        logger.info("Generating action items from meeting notes")

        try:
            # Initialize and run the action items generation workflow
            generation_workflow = ActionItemsGenerationWorkflow(
                llm=self.llm, max_iterations=self.max_iterations
            )

            generation_result = await generation_workflow.run(
                meeting_notes=event.meeting_notes
            )

            # Extract action items from result
            if hasattr(generation_result, "result"):
                action_items = generation_result.result
            else:
                logger.error("Invalid result from action items generation workflow")
                return StopWithErrorEvent(result="generation_error", error=True)

            # Validate action items
            if not isinstance(action_items, ActionItemsList):
                logger.error("Generated action items are not of type ActionItemsList")
                return StopWithErrorEvent(result="invalid_action_items", error=True)

            logger.info(f"Generated {len(action_items.action_items)} action items")

            return StopWithErrorEvent(result=action_items, error=False)

        except Exception as e:
            logger.error(f"Error generating action items: {e}")
            return StopWithErrorEvent(result="generation_error", error=True)
