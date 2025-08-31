"""Agent package initialization with logging setup."""

from .configs.logging_config import setup_logging

# Initialize logging when the package is imported
logger = setup_logging()
logger.info("Agents package initialized")
