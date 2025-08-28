"""
This module is used to load, validate and create llm object from user config
"""

import os
from llama_index.llms.openai import OpenAI
from llama_index.llms.google_genai import GoogleGenAI

SUPPORTED_LLMS = {"OpenAI": OpenAI, "Gemini": GoogleGenAI}


class LlmNotSupported(Exception):
    "LLM not supported error"

    def __init__(self):
        super().__init__(
            "The llm you are trying to use is not supported please choose one "
            f"of: {SUPPORTED_LLMS.keys().__str__()}"
        )


class ModelFactory:
    """Class for loading user config and generate llm object"""

    def __init__(self, config):
        # pylint: disable=consider-iterating-dictionary
        if config.llm not in SUPPORTED_LLMS.keys():
            raise LlmNotSupported

        api_key = os.environ.get("MODEL_API_KEY", config.api_key)
        if not api_key:
            raise ValueError(
                "Api key is not set please set it in config "
                "file or using MODEL_API_KEY environment "
                "variable"
            )

        llm_object = SUPPORTED_LLMS.get(config.llm)
        self.llm = llm_object(
            model=config.model, api_key=api_key, **config.additional_model_parameter
        )
