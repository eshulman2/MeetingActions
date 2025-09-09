"""Setup observability with langfuse"""

from langfuse import Langfuse
from openinference.instrumentation.llama_index import LlamaIndexInstrumentor

from src.infrastructure.config import get_config
from src.infrastructure.logging.logging_config import get_logger

logger = get_logger("configs.observability")


def set_up_langfuse() -> None:
    """Initialize Langfuse client with environment variables."""
    config = get_config()

    if not config.config.observability.enable:
        logger.info("Langfuse observability is disabled")
        return

    if (
        not config.config.observability.secret_key
        or not config.config.observability.public_key
        or not config.config.observability.host
    ):
        raise ValueError("LANGFUSE_SECRET_KEY and LANGFUSE_PUBLIC_KEY must be set")

    logger.info("Applying tracing")
    Langfuse(
        secret_key=config.config.observability.secret_key,
        public_key=config.config.observability.public_key,
        host=str(config.config.observability.host),
    )
    LlamaIndexInstrumentor().instrument()
    logger.info("Tracing applied")
