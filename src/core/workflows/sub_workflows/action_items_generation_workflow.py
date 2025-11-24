"""Action Items Generation Workflow.

This workflow handles the generation and refinement of action items from meeting notes
using LLMTextCompletionProgram with Pydantic models for structured output.
"""

from datetime import datetime

from llama_index.core.memory import Memory
from llama_index.core.program import LLMTextCompletionProgram
from llama_index.core.workflow import Context, Event, StartEvent, Workflow, step

from src.core.schemas.workflow_models import ActionItemsList, ReviewFeedback
from src.core.workflows.common_events import StopWithErrorEvent
from src.infrastructure.config import get_config
from src.infrastructure.logging.logging_config import get_logger
from src.infrastructure.prompts.prompts import (
    ACTION_ITEMS_PROMPT,
    REFINEMENT_PROMPT,
    REVIEWER_PROMPT,
)
from src.shared.llm.summarization.progressive import (
    ProgressiveSummaryResult,
    SummarizationStrategy,
    progressive_summarize,
    summarize_meeting_notes,
)
from src.shared.llm.token_utils import (
    count_tokens,
    get_max_context_tokens,
    should_summarize_notes,
)

logger = get_logger("workflows.action_items_generation")
config = get_config()


class NotesReadyEvent(Event):
    """Event indicating meeting notes are prepared and ready for processing."""

    meeting_notes: str
    original_notes: str
    was_summarized: bool
    progressive_passes: int = 0
    was_chunked: bool = False
    num_chunks: int = 0


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

    def __init__(self, llm, *args, max_iterations: int = 5, **kwargs):
        """Initialize the workflow.

        Args:
            llm: Language model for generating action items
            max_iterations: Maximum number of refinement iterations (default: 5)
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
    async def prepare_meeting_notes(self, event: StartEvent) -> NotesReadyEvent:
        """Prepare meeting notes by summarizing if needed.

        Handles token counting, threshold checking, and applies either progressive
        or simple summarization based on configuration and content length.

        Args:
            event: StartEvent containing original meeting notes

        Returns:
            NotesReadyEvent with prepared notes and metadata
        """
        logger.info("Preparing meeting notes for processing")

        try:
            original_notes = event.meeting_notes
            meeting_notes = original_notes
            token_count = count_tokens(meeting_notes, self.llm)
            logger.info(f"Meeting notes token count: {token_count}")

            # Initialize metadata
            was_summarized = False
            progressive_passes = 0
            was_chunked = False
            num_chunks = 0

            # Check if we should use progressive summarization for very long notes
            progressive_config = config.config.progressive_summarization
            progressive_threshold = int(
                self.max_context_tokens * progressive_config.threshold_ratio
            )

            if token_count > progressive_threshold:
                # Use progressive summarization (includes automatic chunking)
                # This is always used for very long documents to ensure robust handling
                logger.info(
                    f"Notes are very long ({token_count} tokens > "
                    f"{progressive_threshold} threshold), "
                    "using progressive summarization"
                )

                # Get strategy enum from config
                strategy_map = {
                    "aggressive": SummarizationStrategy.AGGRESSIVE,
                    "balanced": SummarizationStrategy.BALANCED,
                    "conservative": SummarizationStrategy.CONSERVATIVE,
                }
                strategy = strategy_map.get(
                    progressive_config.strategy,
                    SummarizationStrategy.BALANCED,
                )

                # Target: 80% of threshold to leave room
                target_tokens = int(self.token_threshold * 0.8)

                progressive_result: ProgressiveSummaryResult = (
                    await progressive_summarize(
                        text=meeting_notes,
                        llm=self.llm,
                        target_tokens=target_tokens,
                        max_passes=progressive_config.max_passes,
                        strategy=strategy,
                        chunk_threshold_ratio=(
                            progressive_config.chunk_threshold_ratio
                        ),
                        chunk_size_ratio=progressive_config.chunk_size_ratio,
                        chunk_overlap_tokens=(progressive_config.chunk_overlap_tokens),
                    )
                )

                meeting_notes = progressive_result.final_summary
                was_summarized = True
                progressive_passes = progressive_result.total_passes
                was_chunked = progressive_result.was_chunked
                num_chunks = progressive_result.num_chunks

                chunked_msg = (
                    f", chunked into {progressive_result.num_chunks} pieces"
                    if progressive_result.was_chunked
                    else ""
                )
                logger.info(
                    f"Progressive summarization complete: "
                    f"{progressive_result.total_passes} passes, "
                    f"{token_count} -> {progressive_result.final_tokens} "
                    f"tokens ({progressive_result.overall_reduction:.1%} "
                    f"reduction){chunked_msg}"
                )
            elif should_summarize_notes(
                meeting_notes, self.llm, token_threshold=self.token_threshold
            ):
                # Use simple single-pass summarization for moderately long notes
                logger.warning(
                    "Meeting notes exceed token threshold, using "
                    "single-pass summarization"
                )
                meeting_notes = await summarize_meeting_notes(
                    meeting_notes, llm=self.llm, target_length_ratio=0.4
                )
                summarized_token_count = count_tokens(meeting_notes, self.llm)
                was_summarized = True

                logger.info(
                    f"Summarized notes: {token_count} -> "
                    f"{summarized_token_count} tokens "
                    f"({summarized_token_count/token_count*100:.1f}%)"
                )

            logger.info(
                f"Notes preparation complete: "
                f"summarized={was_summarized}, "
                f"passes={progressive_passes}, "
                f"chunked={was_chunked}"
            )

            return NotesReadyEvent(
                meeting_notes=meeting_notes,
                original_notes=original_notes,
                was_summarized=was_summarized,
                progressive_passes=progressive_passes,
                was_chunked=was_chunked,
                num_chunks=num_chunks,
            )

        except Exception as e:
            logger.error(f"Error preparing meeting notes: {e}")
            raise

    @step
    async def generate_action_items(
        self, ctx: Context, event: NotesReadyEvent
    ) -> ReviewRequired:
        """Generate action items from prepared meeting notes.

        Uses LLMTextCompletionProgram to ensure structured output via Pydantic models.

        Args:
            ctx: Workflow context
            event: NotesReadyEvent with prepared (potentially summarized) notes

        Returns:
            ReviewRequired event with generated action items
        """
        logger.info("Generating action items from prepared meeting notes")

        try:
            meeting_notes = event.meeting_notes

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
        Includes convergence detection to prevent infinite loops.
        """
        logger.info("Reviewing generated action items")

        try:
            # Use the meeting notes from the event (which may already be summarized)
            meeting_notes = event.meeting_notes

            # Check for convergence - detect if we're oscillating between similar states
            current_action_items_json = event.action_items.model_dump_json(indent=2)
            previous_action_items = await ctx.store.get(
                "previous_action_items", default=[]
            )

            # If we've seen this exact set of action items before, stop to prevent
            # infinite loop
            if current_action_items_json in previous_action_items:
                logger.warning(
                    "Detected convergence loop - action items "
                    "returned to previous state. "
                    "Stopping refinement to prevent infinite loop."
                )
                return StopWithErrorEvent(result=event.action_items, error=False)

            # Store current action items for convergence detection (keep last 3)
            previous_action_items.append(current_action_items_json)
            if len(previous_action_items) > 3:
                previous_action_items.pop(0)
            await ctx.store.set("previous_action_items", previous_action_items)

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
