"""
This module is used to load, validate and create llm object from user config
"""
import json
import os
from typing import Dict
from pydantic import BaseModel, ValidationError
from llama_index.llms.openai import OpenAI
from llama_index.llms.google_genai import GoogleGenAI

SUPPORTED_LLMS = {
    "OpenAI": OpenAI,
    "Gemini": GoogleGenAI
}


class ConfigSchema(BaseModel):
    """Config Schema for validation"""
    llm: str
    model: str
    api_key: str | None = None
    additional_model_parameter: Dict | None = {}
    tools_config: Dict | None = {}
    agent_config: Dict | None = {}


class LlmNotSupported(Exception):
    "LLM not supported error"
    def __init__(self):
        super().__init__(
            'The llm you are trying to use is not supported please choose one '
            f'of: {SUPPORTED_LLMS.keys().__str__()}')


class ModelFactory:
    """Class for loading user config and generate llm object"""
    def __init__(self, path=os.environ.get("CONFIG_PATH", 'config.json')):
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

            # pylint: disable=consider-iterating-dictionary
            if self.config.llm not in SUPPORTED_LLMS.keys():
                raise LlmNotSupported

            api_key = os.environ.get('MODEL_API_KEY', self.config.api_key)
            if not api_key:
                raise ValueError('Api key is not set please set it in config '
                                 'file or using MODEL_API_KEY environment '
                                 'variable')

            llm_object = SUPPORTED_LLMS.get(self.config.llm)
            self.llm = llm_object(model=self.config.model, api_key=api_key,
                                  **self.config.additional_model_parameter)
