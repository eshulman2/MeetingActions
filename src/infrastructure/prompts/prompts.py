# pylint: disable=line-too-long
"""
This module provides access to all prompts used in the system.
Prompts are loaded from text files in subdirectories for better organization.
"""
from pathlib import Path

from llama_index.core.prompts import PromptTemplate

# Base directory for prompts
PROMPTS_DIR = Path(__file__).parent


def load_prompt(file_path: str) -> str:
    """Load a prompt from a text file.

    Args:
        file_path: Path to prompt file relative to prompts directory

    Returns:
        Prompt text as string
    """
    full_path = PROMPTS_DIR / file_path
    return full_path.read_text(encoding="utf-8")


def load_prompt_template(file_path: str) -> PromptTemplate:
    """Load a prompt template from a text file.

    Args:
        file_path: Path to prompt file relative to prompts directory

    Returns:
        PromptTemplate object
    """
    prompt_text = load_prompt(file_path)
    return PromptTemplate(prompt_text)


# ===== Action Items Prompts =====
ACTION_ITEMS_PROMPT = load_prompt_template("action_items/generation.txt")
REVIEWER_PROMPT = load_prompt_template("action_items/review.txt")
REFINEMENT_PROMPT = load_prompt_template("action_items/refinement.txt")

# ===== Meeting Notes Prompts =====
IDENTIFY_MEETING_NOTES = load_prompt_template("meeting_notes/identify_file.txt")

# ===== Agent Context Prompts =====
JIRA_AGENT_CONTEXT = load_prompt("agents/jira_context.txt")
GOOGLE_AGENT_CONTEXT = load_prompt("agents/google_context.txt")
TOOL_DISPATCHER_PROMPT = load_prompt_template("agents/tool_dispatcher_prompt.txt")
AGENT_QUERY_PROMPT = load_prompt_template("agents/agent_query.txt")

# ===== Summarization Prompts =====
SUMMARIZATION_PROMPT = load_prompt("summarization/basic.txt")

# Progressive summarization prompts
PROGRESSIVE_PASS_1_PROMPT = load_prompt("summarization/progressive_pass1.txt")
PROGRESSIVE_PASS_2_PROMPT = load_prompt("summarization/progressive_pass2.txt")
PROGRESSIVE_PASS_3_PROMPT = load_prompt("summarization/progressive_pass3.txt")


def get_progressive_pass_prompt(pass_number: int) -> str:
    """Get the prompt for a specific progressive summarization pass.

    Args:
        pass_number: The pass number (1, 2, or 3)

    Returns:
        Prompt text for the specified pass

    Raises:
        ValueError: If pass_number is not 1, 2, or 3
    """
    prompts = {
        1: PROGRESSIVE_PASS_1_PROMPT,
        2: PROGRESSIVE_PASS_2_PROMPT,
        3: PROGRESSIVE_PASS_3_PROMPT,
    }

    if pass_number not in prompts:
        raise ValueError(f"Invalid pass number: {pass_number}. Must be 1, 2, or 3")

    return prompts[pass_number]


# ===== Legacy Prompts (for backward compatibility) =====
# These are kept as string constants for code that still references them

ACTION_ITEMS_CONTEXT = load_prompt("legacy/action_items_context.txt")
REVIEW_CONTEXT = load_prompt("legacy/review_context.txt")
TOOL_DISPATCHER_CONTEXT = load_prompt("legacy/tool_dispatcher_context.txt")

REFLECTION_PROMPT = load_prompt_template("legacy/reflection.txt")
JSON_REFLECTION_PROMPT = load_prompt_template("legacy/json_reflection.txt")
