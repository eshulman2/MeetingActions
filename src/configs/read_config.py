"""module for reading configuration"""
from typing import Dict
import json
import os
from pydantic import BaseModel, ValidationError


class ConfigSchema(BaseModel):
    """Config Schema for validation"""
    llm: str
    model: str
    api_key: str | None = None
    additional_model_parameter: Dict | None = {}
    tools_config: Dict | None = {}
    agent_config: Dict | None = {}


class ConfigReader:
    """Class for loading user configuration"""

    def __init__(self,
                 path=os.environ.get("CONFIG_PATH", 'config.json')
                 ) -> ConfigSchema:
        with open(path, 'r') as config:
            try:
                config = json.load(config)
            except json.JSONDecodeError as ex:
                # pylint: disable=no-value-for-parameter
                raise json.JSONDecodeError(
                    'Config json failed loading with the'
                    f'following exception: {ex}')

            try:
                self.config = ConfigSchema(**config)
            except ValidationError as err:
                raise err
