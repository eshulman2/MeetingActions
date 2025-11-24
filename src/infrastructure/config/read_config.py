"""module for reading configuration"""

import json
import os
from typing import Any, Dict

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    ValidationError,
    model_validator,
)

from src.shared.common.singleton_meta import SingletonMeta


class ObservabilityConfigSchema(BaseModel):
    """Config schema for observability"""

    enable: bool = False
    secret_key: str | None = Field(
        default_factory=lambda: os.getenv("LANGFUSE_SECRET_KEY", None),
        description="Langfuse secret key",
    )
    public_key: str | None = Field(
        default_factory=lambda: os.getenv("LANGFUSE_PUBLIC_KEY", None),
        description="Langfuse public key",
    )
    host: HttpUrl | None = Field(default=None, description="Langfuse host URL")

    @model_validator(mode="after")
    def check_keys_if_enabled(self) -> "ObservabilityConfigSchema":
        """Validate required keys when observability is enabled."""
        if self.enable and not self.secret_key:
            raise ValueError("secret_key is required when observability is enabled")
        if self.enable and not self.public_key:
            raise ValueError("public_key is required when observability is enabled")
        if self.enable and not self.host:
            raise ValueError("host is required when observability is enabled")
        return self


class CacheConfigSchema(BaseModel):
    """Config schema for redis cache"""

    enable: bool = False
    ttl_hours: int = Field(gt=0, default=1, description="Cache TTL in hours")
    max_size_mb: int = Field(gt=0, default=100, description="Max cache size in MB")
    host: str = Field(default="localhost", description="Redis host")
    port: int = Field(gt=0, le=65535, default=6380, description="Redis port")
    password: str | None = Field(
        default_factory=lambda: os.getenv("REDIS_PASSWORD", None),
        description="Redis password",
    )

    @model_validator(mode="after")
    def check_password_if_enabled(self) -> "CacheConfigSchema":
        """Validate required password when cache is enabled."""
        if self.enable and not self.password:
            raise ValueError("Password is required when cache is enabled")
        return self


class ProgressiveSummarizationConfig(BaseModel):
    """Configuration for progressive summarization.

    Progressive summarization automatically activates when documents exceed
    the threshold_ratio to ensure robust handling of large documents.
    """

    threshold_ratio: float = Field(
        default=0.75,
        gt=0,
        le=1.0,
        description="Use progressive when notes exceed max_context_tokens * this ratio",
    )
    max_passes: int = Field(
        default=3, gt=0, le=5, description="Maximum summarization passes"
    )
    strategy: str = Field(
        default="balanced",
        description="Strategy: aggressive, balanced, or conservative",
    )
    chunk_threshold_ratio: float = Field(
        default=0.5,
        gt=0,
        le=1.0,
        description="Chunk if document exceeds this ratio of LLM context window",
    )
    chunk_size_ratio: float = Field(
        default=0.4,
        gt=0,
        le=0.8,
        description="Each chunk size as ratio of LLM context window",
    )
    chunk_overlap_tokens: int = Field(
        default=500,
        ge=0,
        description="Token overlap between consecutive chunks",
    )

    @model_validator(mode="after")
    def validate_strategy(self) -> "ProgressiveSummarizationConfig":
        """Validate strategy value."""
        valid_strategies = ["aggressive", "balanced", "conservative"]
        if self.strategy not in valid_strategies:
            raise ValueError(
                f"Invalid strategy: {self.strategy}. "
                f"Must be one of: {', '.join(valid_strategies)}"
            )
        return self


class ConfigSchema(BaseModel):
    """Config Schema for validation"""

    model_config = ConfigDict(extra="forbid")

    llm: str = "Gemini"
    model: str = "gemini-2.0-flash"
    host: str = Field(
        default_factory=lambda: os.getenv("UVICORN_HOST", "0.0.0.0"),
        description="uvicorn server host/IP address",
    )
    port: int = Field(
        gt=0,
        le=65535,
        default_factory=lambda: int(os.getenv("UVICORN_PORT") or "8000"),
        description="uvicorn server port",
    )
    heartbeat_interval: int = Field(
        gt=0,
        default=60,
        description="Agent heartbeat interval in seconds",
    )
    model_api_key: str | None = Field(
        default_factory=lambda: os.getenv("MODEL_API_KEY", None),
        description="Model api key",
    )
    verify_ssl: bool = True
    additional_model_parameter: Dict[str, Any] = {}
    tools_config: Dict[str, Any] = {}
    agent_config: Dict[str, Any] = {}
    mcp_config: Dict[str, Any] = {}
    observability: ObservabilityConfigSchema = Field(
        default_factory=ObservabilityConfigSchema
    )
    cache_config: CacheConfigSchema = Field(default_factory=CacheConfigSchema)
    progressive_summarization: ProgressiveSummarizationConfig = Field(
        default_factory=ProgressiveSummarizationConfig,
        description="Progressive summarization configuration",
    )
    google_mcp: HttpUrl = Field(
        default_factory=lambda: HttpUrl("http://127.0.0.1:8100/mcp")
    )
    registry_endpoint: HttpUrl = Field(
        default_factory=lambda: HttpUrl("http://localhost:8003"),
        description="Agent registry service endpoint",
    )
    agent_endpoint: str | None = Field(
        default=None,
        description=(
            "Override endpoint for agent to advertise to "
            "registry (for containerized deployments)"
        ),
    )


class ConfigReader(metaclass=SingletonMeta):
    """Class for loading user configuration"""

    def __init__(self) -> None:
        if hasattr(self, "_initialized"):
            return

        self._initialized = True

        path = os.environ.get("CONFIG_PATH", "config.json")

        if not os.path.exists(path):
            raise FileNotFoundError(f"Config file not found at {path}")

        with open(path, "r") as config_file:
            try:
                config_data = json.load(config_file)
            except json.JSONDecodeError as ex:
                raise json.JSONDecodeError(
                    msg=(
                        "Config json failed loading with the "
                        f"following exception: {ex}"
                    ),
                    doc=ex.doc,
                    pos=ex.pos,
                ) from ex

            try:
                self.config = ConfigSchema(**config_data)
            except ValidationError as err:
                raise err


def get_config() -> ConfigReader:
    """Get the global configuration instance."""
    return ConfigReader()
