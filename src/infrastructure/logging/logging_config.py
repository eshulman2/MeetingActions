"""Logging configuration for the Gmeet agent project."""

import logging
import logging.config
import os
from pathlib import Path
from typing import Any, Dict


def get_log_level() -> str:
    """Get log level from environment variable or default to INFO."""
    return os.getenv("LOG_LEVEL", "INFO").upper()


def get_logging_config() -> Dict[str, Any]:
    """Get the logging configuration dictionary."""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    log_level = get_log_level()

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "detailed": {
                # pylint: disable=line-too-long
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(module)s - %(funcName)s:%(lineno)d - %(message)s",  # noqa: E501
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": log_level,
                "formatter": "standard",
                "stream": "ext://sys.stdout",
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "DEBUG",
                "formatter": "detailed",
                "filename": str(log_dir / "agent.log"),
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "encoding": "utf8",
            },
            "error_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "ERROR",
                "formatter": "detailed",
                "filename": str(log_dir / "errors.log"),
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "encoding": "utf8",
            },
        },
        "loggers": {
            "agents": {
                "level": "DEBUG",
                "handlers": ["console", "file", "error_file"],
                "propagate": False,
            },
            "google": {
                "level": "WARNING",
                "handlers": ["console", "file"],
                "propagate": False,
            },
            "jira": {
                "level": "WARNING",
                "handlers": ["console", "file"],
                "propagate": False,
            },
            "httpx": {
                "level": "WARNING",
                "handlers": ["console", "file"],
                "propagate": False,
            },
            "fastmcp": {
                "level": "INFO",
                "handlers": ["console", "file"],
                "propagate": False,
            },
            "redis": {
                "level": "WARNING",
                "handlers": ["console", "file"],
                "propagate": False,
            },
        },
        "root": {
            "level": log_level,
            "handlers": ["console", "file"],
        },
    }


def setup_logging() -> logging.Logger:
    """Set up logging configuration and return the main logger."""
    config = get_logging_config()
    logging.config.dictConfig(config)

    logger = logging.getLogger("agents")
    logger.info("Logging initialized successfully")

    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the specified name under the agents hierarchy."""
    return logging.getLogger(f"agents.{name}")
