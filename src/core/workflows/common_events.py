"""common events for workflows"""

from llama_index.core.workflow import StopEvent


class StopWithErrorEvent(StopEvent):
    """Stop event with error boolean"""

    error: bool
