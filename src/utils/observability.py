"""Setup observability with langfuse"""

from langfuse import Langfuse
from openinference.instrumentation.llama_index import LlamaIndexInstrumentor

from src.configs.logging_config import get_logger

logger = get_logger("configs.observability")
_langfuse_enabled = False


def set_up_langfuse(
    secret_key: str, public_key: str, host: str, **kwargs
) -> None:
    """Initialize Langfuse client with environment variables."""
    global _langfuse_enabled

    _langfuse_enabled = kwargs.get("enable", False)

    if not _langfuse_enabled:
        logger.info("Langfuse observability is disabled")
        return None

    if not secret_key or not public_key or not host:
        raise ValueError(
            "LANGFUSE_SECRET_KEY and LANGFUSE_PUBLIC_KEY must be set"
        )

    logger.info("Applying tracing")
    Langfuse(secret_key=secret_key, public_key=public_key, host=host)
    LlamaIndexInstrumentor().instrument()
    logger.info("Tracing applied")
