"""Agent package initialization with logging setup."""

from src.configs.logging_config import setup_logging
from src.configs.read_config import ConfigReader
from src.utils.observability import set_up_langfuse

# Initialize logging when the package is imported
logger = setup_logging()
logger.info("Agents package initialized")
config = ConfigReader()
set_up_langfuse(**config.config.observability)
