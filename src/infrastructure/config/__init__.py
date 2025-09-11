"""init for configs package"""

from src.infrastructure.config.models import get_model
from src.infrastructure.config.read_config import ConfigReader, get_config

__all__ = [
    "get_model",
    "ConfigReader",
    "get_config",
]
