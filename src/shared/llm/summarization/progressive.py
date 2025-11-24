"""Progressive summarization for very long documents.

This module implements multi-pass iterative summarization that gradually
reduces content while preserving critical information through multiple passes.
It also supports chunking for documents that exceed the LLM context window.
"""

import asyncio
from enum import Enum
from typing import List

from llama_index.core.llms import LLM
from llama_index.core.program import LLMTextCompletionProgram
from pydantic import BaseModel, Field

from src.infrastructure.logging.logging_config import get_logger
from src.infrastructure.prompts.prompts import (
    SUMMARIZATION_PROMPT,
    get_progressive_pass_prompt,
)
from src.shared.llm.token_utils import (
    chunk_text_by_tokens,
    count_tokens,
    get_max_context_tokens,
    truncate_text_by_tokens,
)

logger = get_logger("utils.progressive_summarization")


class SummarizationStrategy(Enum):
    """Strategy for progressive summarization."""

    AGGRESSIVE = "aggressive"  # Faster reduction, may lose some details
    BALANCED = "balanced"  # Balanced approach (default)
    CONSERVATIVE = "conservative"  # Slower reduction, preserves more


class PassSummaryOutput(BaseModel):
    """Output from a single summarization pass."""

    summary: str = Field(..., description="The summarized text")
    key_points: List[str] = Field(
        default_factory=list, description="Key points retained"
    )
    topics: List[str] = Field(default_factory=list, description="Topics covered")


class SummaryPass(BaseModel):
    """Result from a single summarization pass."""

    pass_number: int
    input_tokens: int
    output_tokens: int
    reduction_ratio: float
    summary: str
    key_points_retained: List[str] = Field(default_factory=list)
    topics_covered: List[str] = Field(default_factory=list)


class ProgressiveSummaryResult(BaseModel):
    """Result from progressive summarization."""

    final_summary: str
    total_passes: int
    original_tokens: int
    final_tokens: int
    overall_reduction: float
    passes: List[SummaryPass]
    warnings: List[str] = Field(default_factory=list)
    was_chunked: bool = Field(default=False, description="Whether document was chunked")
    num_chunks: int = Field(default=0, description="Number of chunks processed")


class ChunkSummary(BaseModel):
    """Summary of a single chunk."""

    chunk_number: int
    input_tokens: int
    output_tokens: int
    summary: str
    key_points: List[str] = Field(default_factory=list)


def calculate_reduction_targets(
    original_tokens: int,
    target_tokens: int,
    max_passes: int,
    strategy: SummarizationStrategy,
) -> List[int]:
    """Calculate target token counts for each pass.

    Args:
        original_tokens: Original document token count
        target_tokens: Target final token count
        max_passes: Maximum number of passes
        strategy: Summarization strategy to use

    Returns:
        List of target token counts for each pass
    """
    if strategy == SummarizationStrategy.AGGRESSIVE:
        # Faster reduction: 50%, 30%, 15%
        ratios = [0.5, 0.3, 0.15]
    elif strategy == SummarizationStrategy.CONSERVATIVE:
        # Slower reduction: 70%, 50%, 35%
        ratios = [0.7, 0.5, 0.35]
    else:  # BALANCED
        # Balanced: 60%, 40%, 25%
        ratios = [0.6, 0.4, 0.25]

    targets = []
    current = original_tokens

    for i in range(min(max_passes, len(ratios))):
        target = int(current * ratios[i])
        targets.append(max(target, target_tokens))
        current = target

    return targets


async def perform_summary_pass(
    text: str, llm: LLM, pass_number: int, target_tokens: int
) -> SummaryPass:
    """Perform a single summarization pass.

    Args:
        text: Text to summarize
        llm: Language model to use
        pass_number: Pass number (1, 2, or 3)
        target_tokens: Target token count for this pass

    Returns:
        SummaryPass result
    """
    input_tokens = count_tokens(text, llm)

    logger.info(
        f"Pass {pass_number}: {input_tokens} tokens -> "
        f"target {target_tokens} tokens"
    )

    # Get appropriate prompt for this pass
    prompt = get_progressive_pass_prompt(pass_number)

    try:
        # Create structured program for summarization
        program = LLMTextCompletionProgram.from_defaults(
            llm=llm,
            output_cls=PassSummaryOutput,
            prompt=prompt,
            verbose=False,
        )

        # Generate summary
        result = await program.acall(text=text)

        if not isinstance(result, PassSummaryOutput):
            logger.error("Pass output is not PassSummaryOutput type")
            raise ValueError("Invalid summary structure generated")

        output_tokens = count_tokens(result.summary, llm)

        return SummaryPass(
            pass_number=pass_number,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            reduction_ratio=(input_tokens - output_tokens) / input_tokens,
            summary=result.summary,
            key_points_retained=result.key_points,
            topics_covered=result.topics,
        )

    except Exception as e:
        logger.error(f"Error in pass {pass_number}: {e}")
        # Fallback: use truncation
        logger.warning(f"Pass {pass_number} failed, using truncation as fallback")
        truncated = truncate_text_by_tokens(
            text, target_tokens, llm, keep_start=True, buffer_ratio=0.9
        )
        output_tokens = count_tokens(truncated, llm)

        return SummaryPass(
            pass_number=pass_number,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            reduction_ratio=(input_tokens - output_tokens) / input_tokens,
            summary=truncated,
            key_points_retained=[],
            topics_covered=[],
        )


async def summarize_chunk(
    chunk: str,
    chunk_number: int,
    llm: LLM,
    target_reduction: float = 0.6,
) -> ChunkSummary:
    """Summarize a single chunk of text.

    Args:
        chunk: Text chunk to summarize
        chunk_number: Index of this chunk
        llm: Language model to use
        target_reduction: Target reduction ratio (0.6 = reduce to 60% of original)

    Returns:
        ChunkSummary with summarized chunk and metadata
    """
    input_tokens = count_tokens(chunk, llm)
    target_tokens = int(input_tokens * target_reduction)

    logger.info(
        f"Summarizing chunk {chunk_number}: {input_tokens} tokens -> "
        f"target ~{target_tokens} tokens"
    )

    try:
        # Use basic summarization prompt for chunks
        program = LLMTextCompletionProgram.from_defaults(
            llm=llm,
            output_cls=PassSummaryOutput,
            prompt=SUMMARIZATION_PROMPT,
            verbose=False,
        )

        result = await program.acall(text=chunk)

        if not isinstance(result, PassSummaryOutput):
            logger.error(f"Chunk {chunk_number} output is not PassSummaryOutput type")
            raise ValueError("Invalid chunk summary structure generated")

        output_tokens = count_tokens(result.summary, llm)

        logger.info(
            f"Chunk {chunk_number} summarized: {input_tokens} -> {output_tokens} tokens"
        )

        return ChunkSummary(
            chunk_number=chunk_number,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            summary=result.summary,
            key_points=result.key_points,
        )

    except Exception as e:
        logger.error(f"Error summarizing chunk {chunk_number}: {e}")
        # Fallback: use truncation
        logger.warning(f"Chunk {chunk_number} failed, using truncation as fallback")
        truncated = truncate_text_by_tokens(
            chunk, target_tokens, llm, keep_start=True, buffer_ratio=0.9
        )
        output_tokens = count_tokens(truncated, llm)

        return ChunkSummary(
            chunk_number=chunk_number,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            summary=truncated,
            key_points=[],
        )


async def summarize_with_chunking(
    text: str,
    llm: LLM,
    target_tokens: int,
    chunk_size: int,
    chunk_overlap: int,
) -> tuple[str, List[ChunkSummary], List[str]]:
    """Summarize very large text by chunking and parallel processing.

    Args:
        text: Original text to summarize
        llm: Language model for summarization
        target_tokens: Target token count for final summary
        chunk_size: Maximum tokens per chunk
        chunk_overlap: Token overlap between chunks

    Returns:
        Tuple of (combined_summary, chunk_summaries, warnings)
    """
    original_tokens = count_tokens(text, llm)
    warnings = []

    logger.info(
        f"Starting chunk-based summarization: {original_tokens} tokens, "
        f"chunk_size={chunk_size}, overlap={chunk_overlap}"
    )

    # Split text into chunks
    chunks = chunk_text_by_tokens(text, chunk_size, llm, overlap=chunk_overlap)
    num_chunks = len(chunks)

    logger.info(f"Split into {num_chunks} chunks")

    # Summarize all chunks in parallel
    chunk_tasks = [
        summarize_chunk(chunk, i + 1, llm, target_reduction=0.6)
        for i, chunk in enumerate(chunks)
    ]

    chunk_summaries = await asyncio.gather(*chunk_tasks)

    # Combine chunk summaries
    combined_summary = "\n\n".join(
        f"# Section {cs.chunk_number}\n{cs.summary}" for cs in chunk_summaries
    )

    combined_tokens = count_tokens(combined_summary, llm)

    logger.info(
        f"Combined {num_chunks} chunk summaries: {combined_tokens} tokens "
        f"(reduced from {original_tokens})"
    )

    # Check if combined summary still exceeds target
    if combined_tokens > target_tokens:
        warning = (
            f"Combined chunk summaries ({combined_tokens} tokens) still exceed "
            f"target ({target_tokens} tokens). Will apply progressive summarization."
        )
        logger.warning(warning)
        warnings.append(warning)

    return combined_summary, list(chunk_summaries), warnings


# pylint: disable=too-many-arguments,too-many-positional-arguments
async def progressive_summarize(
    text: str,
    llm: LLM,
    target_tokens: int,
    max_passes: int = 3,
    strategy: SummarizationStrategy = SummarizationStrategy.BALANCED,
    chunk_threshold_ratio: float = 0.5,
    chunk_size_ratio: float = 0.4,
    chunk_overlap_tokens: int = 500,
) -> ProgressiveSummaryResult:
    """Progressively summarize text through multiple passes.

    Automatically uses chunking for documents that exceed the LLM context window.

    Args:
        text: Original text to summarize
        llm: Language model for summarization
        target_tokens: Target token count for final summary
        max_passes: Maximum number of summarization passes (default: 3)
        strategy: Summarization strategy (default: BALANCED)
        chunk_threshold_ratio: Chunk if text exceeds this ratio of context
            window (default: 0.5)
        chunk_size_ratio: Each chunk size as ratio of context window (default: 0.4)
        chunk_overlap_tokens: Token overlap between chunks (default: 500)

    Returns:
        ProgressiveSummaryResult with summary and metadata
    """
    current_text = text
    original_tokens = count_tokens(text, llm)
    passes = []
    warnings = []
    was_chunked = False
    num_chunks = 0

    logger.info(
        f"Starting progressive summarization: {original_tokens} tokens "
        f"-> target {target_tokens} tokens ({strategy.value} strategy)"
    )

    # Check if summarization is needed
    if original_tokens <= target_tokens:
        logger.info("Text already within target, no summarization needed")
        return ProgressiveSummaryResult(
            final_summary=text,
            total_passes=0,
            original_tokens=original_tokens,
            final_tokens=original_tokens,
            overall_reduction=0.0,
            passes=[],
            warnings=["Text was already within target token limit"],
            was_chunked=False,
            num_chunks=0,
        )

    # Check if chunking is needed (document exceeds LLM context window threshold)
    max_context = get_max_context_tokens(llm)
    chunk_threshold = int(max_context * chunk_threshold_ratio)

    logger.info(
        f"Context window: {max_context} tokens, "
        f"chunk threshold: {chunk_threshold} tokens"
    )

    if original_tokens > chunk_threshold:
        logger.info(
            f"Document ({original_tokens} tokens) exceeds chunk threshold "
            f"({chunk_threshold} tokens). Using chunking strategy."
        )

        # Calculate chunk size based on context window
        chunk_size = int(max_context * chunk_size_ratio)

        # Summarize with chunking
        chunk_summary, chunk_summaries, chunk_warnings = await summarize_with_chunking(
            text=text,
            llm=llm,
            target_tokens=target_tokens,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap_tokens,
        )

        # Update state
        current_text = chunk_summary
        was_chunked = True
        num_chunks = len(chunk_summaries)
        warnings.extend(chunk_warnings)

        logger.info(
            f"Chunking complete: {num_chunks} chunks processed, "
            f"combined to {count_tokens(current_text, llm)} tokens"
        )

    # Calculate reduction targets for each pass
    reduction_targets = calculate_reduction_targets(
        original_tokens, target_tokens, max_passes, strategy
    )

    targets_str = " -> ".join(map(str, reduction_targets))
    logger.info("Reduction plan: %s -> %s", original_tokens, targets_str)

    # Perform summarization passes
    for pass_num in range(1, max_passes + 1):
        current_tokens = count_tokens(current_text, llm)

        # Check if we've reached target
        if current_tokens <= target_tokens:
            logger.info(
                f"Target reached after {pass_num - 1} passes "
                f"({current_tokens} tokens)"
            )
            break

        # Check if we have more passes than reduction targets
        if pass_num > len(reduction_targets):
            logger.warning(
                f"No more reduction targets, stopping at pass {pass_num - 1}"
            )
            break

        # Perform summarization pass
        try:
            pass_result = await perform_summary_pass(
                text=current_text,
                llm=llm,
                pass_number=pass_num,
                target_tokens=reduction_targets[pass_num - 1],
            )

            passes.append(pass_result)
            current_text = pass_result.summary

            logger.info(
                f"Pass {pass_num} complete: {pass_result.input_tokens} -> "
                f"{pass_result.output_tokens} tokens "
                f"({pass_result.reduction_ratio:.1%} reduction)"
            )

        except Exception as e:
            logger.error(f"Pass {pass_num} failed: {e}")
            warnings.append(f"Pass {pass_num} failed: {str(e)}")
            break

    final_tokens = count_tokens(current_text, llm)

    # Check if we met the target
    if final_tokens > target_tokens:
        warning = (
            f"Final token count ({final_tokens}) exceeds " f"target ({target_tokens})"
        )
        logger.warning(warning)
        warnings.append(warning)

    result = ProgressiveSummaryResult(
        final_summary=current_text,
        total_passes=len(passes),
        original_tokens=original_tokens,
        final_tokens=final_tokens,
        overall_reduction=(
            (original_tokens - final_tokens) / original_tokens
            if original_tokens > 0
            else 0.0
        ),
        passes=passes,
        warnings=warnings,
        was_chunked=was_chunked,
        num_chunks=num_chunks,
    )

    logger.info(
        f"Progressive summarization complete: "
        f"{result.total_passes} passes, "
        f"{result.overall_reduction:.1%} reduction, "
        f"{result.final_tokens} final tokens"
        f"{f', chunked into {num_chunks} pieces' if was_chunked else ''}"
    )

    return result


class MeetingNotesSummary(BaseModel):
    """Summarized version of meeting notes."""

    summary: str = Field(
        ..., description="Concise summary preserving all key points and action items"
    )
    key_decisions: List[str] = Field(
        default_factory=list, description="Critical decisions made in the meeting"
    )
    topics_discussed: List[str] = Field(
        default_factory=list, description="Main topics covered"
    )


async def summarize_meeting_notes(
    meeting_notes: str, llm: LLM, target_length_ratio: float = 0.4
) -> str:
    """Summarize long meeting notes while preserving key information.

    Args:
        meeting_notes: The full meeting notes text
        llm: Language model to use for summarization
        target_length_ratio: Target summary length as ratio of original (0.4 = 40%)

    Returns:
        Summarized meeting notes
    """
    logger.info(
        f"Summarizing meeting notes ({len(meeting_notes)} chars) "
        f"to ~{int(target_length_ratio * 100)}% of original length"
    )

    try:
        # Create structured program for summarization
        program = LLMTextCompletionProgram.from_defaults(
            llm=llm,
            output_cls=MeetingNotesSummary,
            prompt=SUMMARIZATION_PROMPT,
            verbose=False,
        )

        # Generate summary
        summary_result = await program.acall(meeting_notes=meeting_notes)

        if not isinstance(summary_result, MeetingNotesSummary):
            logger.error("Summary output is not MeetingNotesSummary type")
            raise ValueError("Invalid summary structure generated")

        # Format the summary for use
        formatted_summary = f"""# Meeting Summary

{summary_result.summary}

## Key Decisions
{chr(10).join(f"- {decision}" for decision in summary_result.key_decisions)}

## Topics Discussed
{chr(10).join(f"- {topic}" for topic in summary_result.topics_discussed)}
"""

        logger.info(
            f"Successfully summarized notes: "
            f"{len(meeting_notes)} -> {len(formatted_summary)} chars "
            f"({len(formatted_summary)/len(meeting_notes)*100:.1f}%)"
        )

        return formatted_summary

    except Exception as e:
        logger.error(f"Error summarizing meeting notes: {e}")
        # Fallback: use simple truncation
        logger.warning("Falling back to simple truncation")
        return truncate_text_by_tokens(meeting_notes, max_tokens=8000, llm=llm)
