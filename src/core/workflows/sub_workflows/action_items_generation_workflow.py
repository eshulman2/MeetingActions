"""Action Items Generation Workflow.

This workflow handles the generation and refinement of action items from meeting notes
using LLMTextCompletionProgram with Pydantic models for structured output.
"""

from datetime import datetime

from llama_index.core.memory import Memory
from llama_index.core.program import LLMTextCompletionProgram
from llama_index.core.workflow import (
    Context,
    Event,
    StartEvent,
    Workflow,
    step,
)

from src.core.schemas.workflow_models import ActionItemsList, ReviewFeedback
from src.core.workflows.common_events import StopWithErrorEvent
from src.infrastructure.config import get_config
from src.infrastructure.logging.logging_config import get_logger
from src.infrastructure.prompts.prompts import (
    ACTION_ITEMS_PROMPT,
    REFINEMENT_PROMPT,
    REVIEWER_PROMPT,
)
from src.infrastructure.utils.token_utils import (
    count_tokens,
    get_max_context_tokens,
    should_summarize_notes,
    summarize_meeting_notes,
)

logger = get_logger("workflows.action_items_generation")
config = get_config()


class ReviewRequired(Event):
    """Event indicating review is needed."""

    action_items: ActionItemsList
    meeting_notes: str


class RefinementRequired(Event):
    """Event indicating refinement based on review feedback."""

    action_items: ActionItemsList
    feedback: ReviewFeedback
    meeting_notes: str


class ActionItemsGenerationWorkflow(Workflow):
    """Workflow for generating and refining action items from meeting notes.

    This workflow uses LLMTextCompletionProgram with Pydantic models to ensure
    structured, validated output without manual JSON parsing.
    """

    def __init__(self, llm, *args, max_iterations: int = 20, **kwargs):
        """Initialize the workflow.

        Args:
            llm: Language model for generating action items
            max_iterations: Maximum number of refinement iterations
        """
        super().__init__(*args, **kwargs)
        self.llm = llm
        self.max_iterations = max_iterations

        # Dynamically get max context tokens from LLM metadata
        self.max_context_tokens = get_max_context_tokens(llm)

        # Set token threshold for summarization (25% of max context)
        self.token_threshold = int(self.max_context_tokens * 0.25)

        self.memory = Memory.from_defaults(
            session_id="action_items_generation",
            token_limit=self.max_context_tokens,
        )
        logger.info(
            f"Initialized ActionItemsGenerationWorkflow with "
            f"max_iterations: {max_iterations}, "
            f"max_context_tokens: {self.max_context_tokens}, "
            f"token_threshold: {self.token_threshold}"
        )

    @step
    async def generate_action_items(
        self, ctx: Context, event: StartEvent
    ) -> ReviewRequired:
        """Generate initial action items from meeting notes.

        Uses LLMTextCompletionProgram to ensure structured output via Pydantic models.
        Automatically summarizes long meeting notes to prevent token limit issues.
        """
        logger.info("Generating action items from meeting notes")

        try:
            # Check if meeting notes need summarization
            meeting_notes = event.meeting_notes
            token_count = count_tokens(meeting_notes, self.llm)
            logger.info(f"Meeting notes token count: {token_count}")

            # Store original notes for potential use in review
            await ctx.store.set("original_meeting_notes", meeting_notes)

            # Summarize if notes are too long
            if should_summarize_notes(
                meeting_notes, self.llm, token_threshold=self.token_threshold
            ):
                logger.warning(
                    "Meeting notes exceed token threshold, summarizing to "
                    "prevent token limit issues"
                )
                meeting_notes = await summarize_meeting_notes(
                    meeting_notes, llm=self.llm, target_length_ratio=0.4
                )
                summarized_token_count = count_tokens(meeting_notes, self.llm)
                logger.info(
                    f"Summarized notes: {token_count} -> "
                    f"{summarized_token_count} tokens "
                    f"({summarized_token_count/token_count*100:.1f}%)"
                )
                await ctx.store.set("notes_were_summarized", True)
            else:
                await ctx.store.set("notes_were_summarized", False)

            # Get current date and time for context
            current_datetime = datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")

            # Create structured program for action items generation
            program = LLMTextCompletionProgram.from_defaults(
                llm=self.llm,
                output_cls=ActionItemsList,
                prompt=ACTION_ITEMS_PROMPT,
                verbose=True,
            )

            # Generate action items with structured output
            action_items = await program.acall(
                meeting_notes=meeting_notes, current_datetime=current_datetime
            )

            # Validate the generated action items
            if not isinstance(action_items, ActionItemsList):
                logger.error("Generated output is not ActionItemsList type")
                raise ValueError("Invalid action items structure generated")

            if not action_items.action_items:
                logger.warning("No action items were generated")
                # Return empty but valid ActionItemsList
                action_items = ActionItemsList(action_items=[])

            logger.info(f"Generated {len(action_items.action_items)} action items")
            logger.debug(
                f"Action items: {[item.title for item in action_items.action_items]}"
            )

            # Store iteration count for refinement tracking
            await ctx.store.set("iteration_count", 0)

            return ReviewRequired(
                action_items=action_items, meeting_notes=event.meeting_notes
            )

        except Exception as e:
            logger.error(f"Error generating action items: {e}")
            raise

    @step
    async def review_action_items(
        self, ctx: Context, event: ReviewRequired
    ) -> StopWithErrorEvent | RefinementRequired:
        """Review generated action items for quality and completeness.

        Uses LLMTextCompletionProgram for structured review feedback.
        Uses summarized notes if available to stay within token limits.
        """
        logger.info("Reviewing generated action items")

        try:
            # Use the meeting notes from the event (which may already be summarized)
            meeting_notes = event.meeting_notes

            # Log token count for review context
            review_token_count = count_tokens(
                f"{event.action_items.model_dump_json(indent=2)}\n" f"{meeting_notes}",
                self.llm,
            )
            logger.info(f"Review context token count: {review_token_count}")

            # Get current date and time for context
            current_datetime = datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")

            # Create structured program for review with improved prompt handling
            review_program = LLMTextCompletionProgram.from_defaults(
                llm=self.llm,
                output_cls=ReviewFeedback,
                prompt=REVIEWER_PROMPT,
                verbose=True,
            )

            # Get structured review feedback
            review = await review_program.acall(
                action_items=event.action_items.model_dump_json(indent=2),
                meeting_notes=meeting_notes,
                current_datetime=current_datetime,
            )

            # Validate review result
            if not isinstance(review, ReviewFeedback):
                logger.warning(
                    "Review output is not ReviewFeedback type, proceeding with original"
                )
                return StopWithErrorEvent(result=event.action_items, error=False)

            if not review.requires_changes:
                logger.info("Review passed: Action items approved")
                logger.debug(event.action_items)
                return StopWithErrorEvent(result=event.action_items, error=False)

            logger.info(f"Review identified issues: {review.feedback}")
            return RefinementRequired(
                action_items=event.action_items,
                feedback=review,
                meeting_notes=event.meeting_notes,
            )

        except Exception as e:
            logger.error(f"Error during review: {e}")
            # If review fails, report error instead of proceeding
            return StopWithErrorEvent(result=f"review_error: {str(e)}", error=True)

    @step
    async def refine_action_items(
        self, ctx: Context, event: RefinementRequired
    ) -> ReviewRequired | StopWithErrorEvent:
        """Refine action items based on review feedback.

        Uses memory to maintain context across refinement iterations.
        """
        iteration_count = await ctx.store.get("iteration_count", default=0)
        iteration_count += 1

        logger.info(
            f"Refining action items (iteration "
            f"{iteration_count}/{self.max_iterations})"
        )

        if iteration_count >= self.max_iterations:
            logger.warning(
                "Max refinement iterations reached, proceeding with "
                "current action items"
            )
            return StopWithErrorEvent(result=event.action_items, error=False)

        await ctx.store.set("iteration_count", iteration_count)

        try:
            # Create structured program for refinement
            refinement_program = LLMTextCompletionProgram.from_defaults(
                llm=self.llm,
                output_cls=ActionItemsList,
                prompt=REFINEMENT_PROMPT,
                verbose=True,
            )

            # Refine with structured output
            refined_action_items = await refinement_program.acall(
                review=event.feedback.feedback,
                action_items=event.action_items.model_dump_json(indent=2),
            )

            # Validate the refined action items
            if not isinstance(refined_action_items, ActionItemsList):
                logger.warning("Refined output is not ActionItemsList, using original")
                return StopWithErrorEvent(result=event.action_items, error=False)

            if not refined_action_items.action_items:
                logger.warning("Refined output has no action items, using original")
                return StopWithErrorEvent(result=event.action_items, error=False)

            logger.info(f"Refined action items (iteration {iteration_count})")
            logger.debug(
                f"Refined items: "
                f"{[item.title for item in refined_action_items.action_items]}"
            )

            return ReviewRequired(
                action_items=refined_action_items, meeting_notes=event.meeting_notes
            )

        except Exception as e:
            logger.error(f"Error during refinement: {e}")
            # If refinement fails, report error
            return StopWithErrorEvent(result=f"refinement_error: {str(e)}", error=True)
