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


def get_model(config) -> OpenAI | GoogleGenAI | OpenAILike:
    """Create and configure a language model instance from configuration.

    This function creates a language model instance based on the provided
    configuration, handling API key management, SSL verification settings,
    and model-specific parameters.

    Args:
        config: Configuration object containing:
            - llm (str): The LLM type to create (must be in SUPPORTED_LLMS)
            - model (str): The specific model name/ID to use
            - api_key (str, optional): API key for the model service
            - verify_ssl (bool, optional): Whether to verify SSL certificates
            - additional_model_parameter (dict): Additional parameters for model
                initialization

    Returns:
        OpenAI | GoogleGenAI | OpenAILike: Configured language model instance
        ready for use.

    Raises:
        LlmNotSupported: If the requested LLM type is not in SUPPORTED_LLMS.
        ValueError: If no API key is provided via config or MODEL_API_KEY
            environment variable.

    Environment Variables:
        MODEL_API_KEY: API key for the language model service (overrides
            config.api_key).

    Note:
        - API key from MODEL_API_KEY environment variable takes precedence over
            config.api_key
        - When verify_ssl=False, HTTP clients are configured to skip SSL verification
        - Additional model parameters are passed directly to the model constructor
    """

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
        config.additional_model_parameter["http_client"] = httpx.Client(verify=False)
        config.additional_model_parameter["async_http_client"] = httpx.AsyncClient(
            verify=False
        )

    llm_object = SUPPORTED_LLMS.get(config.llm)
    return llm_object(
        model=config.model,
        api_key=api_key,
        **config.additional_model_parameter,
    )  # type: ignore[misc]
