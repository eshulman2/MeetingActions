"""module for reading configuration"""

import json
import os
from typing import Any, Dict

from pydantic import BaseModel, ValidationError


class ConfigSchema(BaseModel):
    """Config Schema for validation"""

    llm: str = "Gemini"
    model: str = "gemini-2.0-flash"
    verify_ssl: bool = True
    max_document_length: int = 2000
    api_key: str | None = None
    additional_model_parameter: Dict[str, Any] = {}
    tools_config: Dict[str, Any] = {}
    agent_config: Dict[str, Any] = {}
    mcp_config: Dict[str, Any] = {}
    observability: Dict[str, Any] = {}
    cache_config: Dict[str, Any] = {}
    meeting_notes_endpoint: str = "http://127.0.0.1:8000/meeting-notes"
    agents: Dict[str, str]


class ConfigReader:
    """Class for loading user configuration"""

    def __init__(
        self, path=os.environ.get("CONFIG_PATH", "config.json")
    ) -> None:
        with open(path, "r") as config:
            try:
                config = json.load(config)
            except json.JSONDecodeError as ex:
                # pylint: disable=no-value-for-parameter
                raise json.JSONDecodeError(
                    "Config json failed loading with the"
                    f"following exception: {ex}"
                )

            try:
                self.config = ConfigSchema(**config)
            except ValidationError as err:
                raise err
