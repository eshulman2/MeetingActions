"""Agent package initialization with logging setup."""

from src.infrastructure.logging.logging_config import setup_logging

# Initialize logging when the package is imported
logger = setup_logging()
logger.info("Agents package initialized")
