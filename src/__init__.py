"""Agent package initialization with logging setup."""

from src.infrastructure.config.read_config import ConfigReader
from src.infrastructure.logging.logging_config import setup_logging
from src.infrastructure.observability.observability import set_up_langfuse

# Initialize logging when the package is imported
logger = setup_logging()
logger.info("Agents package initialized")
config = ConfigReader()
set_up_langfuse(**config.config.observability)
