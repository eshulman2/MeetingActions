"""
This file is a technically unnecessary reflection workflow
but I'm here to practice so, so be it
"""

import json
import re
from typing import Any, Dict

import nest_asyncio
from fastapi import FastAPI, HTTPException
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.memory import Memory
from llama_index.core.workflow import (
    Context,
    Event,
    StartEvent,
    StopEvent,
    Workflow,
    step,
)
from pydantic import BaseModel

from src.configs import (
    ACTION_ITEMS_CONTEXT,
    ACTION_ITEMS_PROMPT,
    JSON_REFLECTION_PROMPT,
    REFLECTION_PROMPT,
    REVIEW_CONTEXT,
    REVIEWER_PROMPT,
    ConfigReader,
    ModelFactory,
)
from src.configs.logging_config import get_logger

logger = get_logger("workflows.action_items_workflow")

nest_asyncio.apply()

config = ConfigReader()
llm = ModelFactory(config.config)


class ReviewErrorEvent(Event):
    """Event triggered when review identifies errors in action items.

    Attributes:
        review: The review feedback indicating what needs to be changed
        action_items: The action items that were reviewed and found to have errors
    """

    review: str
    action_items: str


class ActionItemsDone(Event):
    """Event triggered when action items have been created or updated.

    Attributes:
        action_items: The generated action items content
    """

    action_items: str


class JsonCheckEvent(Event):
    """Event triggered to validate JSON format of action items.

    Attributes:
        action_items: The action items to be validated for JSON format
    """

    action_items: str


class JsonCheckError(Event):
    """Event triggered when JSON validation fails.

    Attributes:
        wrong_answer: The malformed response that failed JSON validation
        error: The specific error encountered during JSON parsing
    """

    wrong_answer: str
    error: Any


class ActionItemsWorkflow(Workflow):
    """Workflow for processing meeting notes and generating action items.

    This workflow takes meeting notes as input and generates structured action items
    through a multi-step process including creation, review, and JSON validation.
    """

    def __init__(
        self,
        *args: Any,
        max_iterations: int,  # Pass custom parameters too.
        **kwargs: Any,
    ) -> None:
        """Initialize the WorkItemWorkflow.

        Args:
            max_iterations: Maximum number of retry iterations for
                action item generation
            *args: Additional positional arguments passed to parent Workflow
            **kwargs: Additional keyword arguments passed to parent Workflow
        """
        logger.info(
            f"Initializing ActionItemsWorkflow with max_iterations: {max_iterations}"
        )

        # Initialize the super class
        super().__init__(*args, **kwargs)
        # Store input into instance variables
        self.max_retries = max_iterations
        self.meeting_notes = None
        self.memory = Memory.from_defaults(
            session_id="my_session", token_limit=40000
        )
        logger.debug("ActionItemsWorkflow initialized successfully")

    @step
    async def create_action_items(
        self,
        ctx: Context,
        event: StartEvent | ReviewErrorEvent | JsonCheckError,
    ) -> StopEvent | ActionItemsDone:
        """Create or refine action items based on meeting notes and feedback.

        Args:
            ctx: Workflow context for storing state
            event: The triggering event (start, review error, or JSON error)

        Returns:
            StopEvent if max retries reached or no input provided,
            ActionItemsDone if action items were successfully created
        """
        current_retries = await ctx.store.get("retries", default=0)
        logger.debug(
            f"Creating action items, attempt {current_retries + 1}/{self.max_retries}"
        )

        if current_retries >= self.max_retries:
            logger.warning("Max retries reached for action items creation")
            return StopEvent(result="Max retries reached", error=True)
        await ctx.store.set("retries", current_retries + 1)

        if isinstance(event, StartEvent):
            self.meeting_notes = event.get("meeting_notes")
            if not self.meeting_notes:
                logger.error("No meeting notes provided as input")
                return StopEvent(result="no input was provided", error=True)
            logger.info("Starting action items creation from meeting notes")

            self.memory.put_messages(
                [
                    ChatMessage(
                        role=MessageRole.SYSTEM, content=ACTION_ITEMS_CONTEXT
                    ),
                    ChatMessage(
                        role=MessageRole.USER,
                        content=ACTION_ITEMS_PROMPT.format(
                            meeting_notes=self.meeting_notes
                        ),
                    ),
                ]
            )

        elif isinstance(event, ReviewErrorEvent):
            logger.info("Refining action items based on review feedback")
            review = event.review
            action_items = event.action_items
            self.memory.put(
                ChatMessage(
                    role=MessageRole.USER,
                    content=REFLECTION_PROMPT.format(
                        review=review, action_items=action_items
                    ),
                )
            )

        elif isinstance(event, JsonCheckError):
            logger.info("Fixing JSON formatting issues in action items")
            output = await llm.llm.achat(
                [
                    ChatMessage(
                        role=MessageRole.USER,
                        content=JSON_REFLECTION_PROMPT.format(
                            wrong_answer=event.wrong_answer, error=event.error
                        ),
                    )
                ]
            )
            logger.debug("JSON formatting fix applied")
            print(output)
            return JsonCheckEvent(action_items=str(output))

        output = await llm.llm.achat(self.memory.get())
        logger.debug("LLM response generated for action items")

        self.memory.put(
            ChatMessage(role=MessageRole.ASSISTANT, content=output)
        )

        logger.info("Action items created successfully")
        return ActionItemsDone(action_items=str(output))

    @step
    async def review(
        self,
        event: ActionItemsDone,
    ) -> JsonCheckEvent | ReviewErrorEvent:
        """Review generated action items for quality and accuracy.

        Args:
            event: ActionItemsDone event containing the action items to review

        Returns:
            JsonCheckEvent if no changes required,
            ReviewErrorEvent if improvements are needed
        """
        logger.info("Reviewing generated action items for quality")
        review = await llm.llm.achat(
            [
                ChatMessage(role=MessageRole.SYSTEM, content=REVIEW_CONTEXT),
                ChatMessage(
                    role=MessageRole.USER,
                    content=REVIEWER_PROMPT.format(
                        action_items=event.action_items,
                        meeting_notes=self.meeting_notes,
                    ),
                ),
            ]
        )
        if "No Changes Required" in str(review):
            logger.info("Review passed: No changes required")
            return JsonCheckEvent(action_items=event.action_items)
        logger.info("Review identified issues: Changes required")
        return ReviewErrorEvent(
            action_items=event.action_items, review=str(review)
        )

    @step
    async def json_check(
        self, event: JsonCheckEvent
    ) -> StopEvent | JsonCheckError:
        """Validate that action items are in proper JSON format.

        Args:
            event: JsonCheckEvent containing action items to validate

        Returns:
            StopEvent with the valid JSON if successful,
            JsonCheckError if JSON parsing fails
        """
        logger.info("Validating action items JSON format")
        try:
            match = re.search(r"\{.*\}", event.action_items, re.DOTALL)
            if not match:
                logger.warning("No JSON found in action items output")
                return JsonCheckError(
                    wrong_answer=event.action_items,
                    error="no Json was found in the output",
                )
            j = json.loads(match.group(0))
            logger.info("JSON validation successful")
            return StopEvent(result=j)
        except json.JSONDecodeError as err:
            logger.error(f"JSON validation failed: {err}")
            return JsonCheckError(wrong_answer=event.action_items, error=err)


class MeetingNotes(BaseModel):
    """The request model for a user's query."""

    meeting_notes: str


class ActionItemsResponse(BaseModel):
    """The response model for the agent's answer."""

    action_items: Dict


app = FastAPI(
    title="Work item workflow",
    description="Work item workflow endpoints",
    version="1.0.0",
)


@app.post("/action-items", response_model=ActionItemsResponse)
async def create_action_items_endpoint(request: MeetingNotes):
    """Action items workflow"""
    logger.info(
        f"Processing action items request with {len(request.meeting_notes)} "
        "characters of meeting notes"
    )
    try:
        workflow = ActionItemsWorkflow(
            timeout=30, verbose=True, max_iterations=20
        )
        res = await workflow.run(meeting_notes=request.meeting_notes)
        logger.info("Action items workflow completed successfully")
        return ActionItemsResponse(action_items=res)
    except Exception as e:
        logger.error(f"Error processing action items request: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error processing request: {e}"
        ) from e
