"""
This module is used to load, validate and create llm object from user config
"""

import os

import httpx
from llama_index.llms.google_genai import GoogleGenAI
from llama_index.llms.openai import OpenAI
from llama_index.llms.openai_like import OpenAILike

SUPPORTED_LLMS = {
    "OpenAI": OpenAI,
    "Gemini": GoogleGenAI,
    "OpenAILike": OpenAILike,
}


class LlmNotSupported(Exception):
    "LLM not supported error"

    def __init__(self):
        super().__init__(
            "The llm you are trying to use is not supported please choose one "
            f"of: {SUPPORTED_LLMS.keys().__str__()}"
        )


def get_model(config):
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

    if not config.verify_ssl:
        config.additional_model_parameter["http_client"] = httpx.Client(
            verify=False
        )
        config.additional_model_parameter["async_http_client"] = (
            httpx.AsyncClient(verify=False)
        )

    llm_object = SUPPORTED_LLMS.get(config.llm)
    return llm_object(
        model=config.model,
        api_key=api_key,
        **config.additional_model_parameter,
    )
