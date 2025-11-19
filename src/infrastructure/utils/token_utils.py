"""Utilities for token counting and text processing to handle token limits.

This module provides utilities for:
- Counting tokens in text using LlamaIndex (model-agnostic)
- Detecting when text exceeds token limits
- Chunking large text into manageable pieces
- Summarizing long meeting notes
"""

from typing import List

from llama_index.core.llms import LLM
from llama_index.core.program import LLMTextCompletionProgram
from pydantic import BaseModel, Field

from src.infrastructure.logging.logging_config import get_logger

logger = get_logger("utils.token_utils")


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


SUMMARIZATION_PROMPT = """
You are an expert at summarizing meeting notes while preserving all critical
information.

Given the following meeting notes, create a concise summary that:
1. Preserves ALL action items, decisions, and commitments
2. Maintains names of people and their responsibilities
3. Keeps important dates, deadlines, and metrics
4. Removes redundant discussion and filler content
5. Uses bullet points for clarity

Meeting Notes:
{meeting_notes}

Provide a summary that is approximately 30-40% of the original length while retaining
all actionable information."""


def get_max_context_tokens(llm: LLM) -> int:
    """Get the maximum context window size from the LLM metadata.

    Args:
        llm: The LLM instance

    Returns:
        Maximum context tokens supported by the model
    """
    try:
        # Try to get from metadata
        metadata = llm.metadata
        if hasattr(metadata, "context_window"):
            return metadata.context_window
        elif hasattr(metadata, "max_tokens"):
            return metadata.max_tokens

        # Fallback: check if llm has the attribute directly
        if hasattr(llm, "context_window"):
            return llm.context_window
        if hasattr(llm, "max_tokens"):
            return llm.max_tokens

        logger.warning(
            "Could not determine max context tokens from LLM, using default: 8192"
        )
        return 8192
    except Exception as e:
        logger.warning(
            f"Error getting max context tokens from LLM: {e}, using default: 8192"
        )
        return 8192


def count_tokens(text: str, llm: LLM) -> int:
    """Count the number of tokens in a text string using the LLM's tokenizer.

    Args:
        text: The text to count tokens for
        llm: The LLM instance to use for token counting

    Returns:
        Number of tokens in the text
    """
    try:
        # Use LlamaIndex's built-in token counting which is model-agnostic
        token_count = llm.get_num_tokens(text)
        return token_count
    except Exception as e:
        logger.warning(
            f"Error counting tokens with LLM: {e}, using character-based estimate"
        )
        # Fallback: rough estimate (1 token ≈ 4 characters)
        return len(text) // 4


def truncate_text_by_tokens(
    text: str,
    max_tokens: int,
    llm: LLM,
    keep_start: bool = True,
    buffer_ratio: float = 0.9,
) -> str:
    """Truncate text to fit within a token limit with a safety buffer.

    Args:
        text: The text to truncate
        max_tokens: Maximum number of tokens to keep
        llm: The LLM instance to use for token counting
        keep_start: If True, keep the start of the text. If False, keep the end.
        buffer_ratio: Safety buffer ratio (0.9 = target 90% of max_tokens)

    Returns:
        Truncated text that fits within max_tokens
    """
    current_tokens = count_tokens(text, llm)

    if current_tokens <= max_tokens:
        return text

    # Apply aggressive buffer from the start (default 90% of max_tokens)
    target_tokens = int(max_tokens * buffer_ratio)

    # Estimate the character ratio we need
    char_ratio = target_tokens / current_tokens
    target_chars = int(len(text) * char_ratio)

    if keep_start:
        truncated_text = text[:target_chars]
        logger.warning(
            f"Truncated text from {current_tokens} to ~{target_tokens} tokens "
            f"(kept start, buffer={buffer_ratio})"
        )
    else:
        truncated_text = text[-target_chars:]
        logger.warning(
            f"Truncated text from {current_tokens} to ~{target_tokens} tokens "
            f"(kept end, buffer={buffer_ratio})"
        )

    return truncated_text


def chunk_text_by_tokens(
    text: str, max_tokens: int, llm: LLM, overlap: int = 100
) -> List[str]:
    """Split text into chunks that fit within token limits.

    Args:
        text: The text to chunk
        max_tokens: Maximum tokens per chunk
        llm: The LLM instance to use for token counting
        overlap: Number of tokens to overlap between chunks (approximate)

    Returns:
        List of text chunks
    """
    total_tokens = count_tokens(text, llm)

    if total_tokens <= max_tokens:
        return [text]

    chunks = []
    # Estimate character positions based on token ratios
    chars_per_token = len(text) / total_tokens
    chunk_size_chars = int(max_tokens * chars_per_token)
    overlap_chars = int(overlap * chars_per_token)

    start = 0
    while start < len(text):
        end = min(start + chunk_size_chars, len(text))
        chunk = text[start:end]
        chunks.append(chunk)

        # Move forward with overlap
        start = end - overlap_chars
        if start >= len(text) - overlap_chars:
            break

    logger.info(f"Split {total_tokens} tokens into {len(chunks)} chunks")
    return chunks


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


def estimate_prompt_tokens(
    meeting_notes: str, llm: LLM, additional_context: str = ""
) -> int:
    """Estimate total tokens for a prompt including meeting notes.

    Args:
        meeting_notes: The meeting notes text
        llm: The LLM instance to use for token counting
        additional_context: Any additional context in the prompt

    Returns:
        Estimated total token count
    """
    total_text = meeting_notes + additional_context
    return count_tokens(total_text, llm)


def should_summarize_notes(
    meeting_notes: str, llm: LLM, token_threshold: int = 10000
) -> bool:
    """Determine if meeting notes should be summarized.

    Args:
        meeting_notes: The meeting notes to check
        llm: The LLM instance to use for token counting
        token_threshold: Token count above which summarization is recommended

    Returns:
        True if notes should be summarized, False otherwise
    """
    token_count = count_tokens(meeting_notes, llm)
    should_summarize = token_count > token_threshold

    if should_summarize:
        logger.info(
            f"Meeting notes contain {token_count} tokens "
            f"(threshold: {token_threshold}), summarization recommended"
        )
    else:
        logger.info(
            f"Meeting notes contain {token_count} tokens "
            f"(threshold: {token_threshold}), no summarization needed"
        )

    return should_summarize
