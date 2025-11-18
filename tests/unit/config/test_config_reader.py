"""
Unit tests for ConfigReader and configuration schemas.
"""

import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from src.infrastructure.config.read_config import (
    CacheConfigSchema,
    ConfigReader,
    ConfigSchema,
    ObservabilityConfigSchema,
)


@pytest.mark.unit
class TestConfigSchema:
    """Test ConfigSchema validation."""

    def test_default_config_creation(self):
        """Test creating config with default values."""
        config = ConfigSchema(agents={"test": "http://localhost:8000"})

        assert config.llm == "Gemini"
        assert config.model == "gemini-2.0-flash"
        assert config.verify_ssl is True
        assert config.max_document_length == 2000

    def test_observability_config_validation(self):
        """Test observability configuration validation."""
        # Test disabled observability
        obs_config = ObservabilityConfigSchema(enable=False)
        print("-" * 50)
        print(obs_config.model_dump_json())
        print("-" * 50)
        assert obs_config.enable is False
        assert obs_config.secret_key is None

        # Test enabled observability with missing keys
        with pytest.raises(ValidationError, match="secret_key is required"):
            ObservabilityConfigSchema(enable=True, secret_key=None)

    def test_cache_config_validation(self):
        """Test cache configuration validation."""
        # Test disabled cache
        cache_config = CacheConfigSchema(enable=False)
        assert cache_config.enable is False

        # Test enabled cache with missing password
        with pytest.raises(ValidationError, match="Password is required"):
            CacheConfigSchema(enable=True, password=None)

    def test_port_validation(self):
        """Test port number validation."""
        # Valid port
        cache_config = CacheConfigSchema(port=6379)
        assert cache_config.port == 6379

        # Invalid ports
        with pytest.raises(ValidationError):
            CacheConfigSchema(port=0)

        with pytest.raises(ValidationError):
            CacheConfigSchema(port=70000)

    def test_environment_variable_integration(self):
        """Test environment variable integration."""
        with patch.dict(
            os.environ,
            {
                "MODEL_API_KEY": "test_key_from_env",
                "LANGFUSE_SECRET_KEY": "test_langfuse_secret",
                "REDIS_PASSWORD": "test_redis_pass",
            },
        ):
            config = ConfigSchema(agents={"test": "http://localhost:8000"})

            assert config.model_api_key == "test_key_from_env"
            assert config.observability.secret_key == "test_langfuse_secret"
            assert config.cache_config.password == "test_redis_pass"


@pytest.mark.unit
class TestConfigReader:
    """Test ConfigReader singleton behavior."""

    def test_singleton_behavior(self, test_config):
        """Test that ConfigReader follows singleton pattern."""
        reader1 = ConfigReader()
        reader2 = ConfigReader()

        assert reader1 is reader2
        assert id(reader1) == id(reader2)

    def test_config_loading(self, test_config):
        """Test configuration loading from file."""
        reader = ConfigReader()
        config = reader.config

        assert isinstance(config, ConfigSchema)
        assert config.llm == "OpenAI"
        assert config.model == "gpt-3.5-turbo"

    def test_reset_instance(self, temp_config_file):
        """Test resetting singleton instance."""
        from src.common.singleton_meta import SingletonMeta

        # Create first instance
        reader1 = ConfigReader()

        # Reset singleton
        SingletonMeta.reset_instance(ConfigReader)

        # Create new instance
        reader2 = ConfigReader()

        # Should be different instances
        assert reader1 is not reader2

    def test_file_not_found_error(self):
        """Test error when config file doesn't exist."""
        from src.common.singleton_meta import SingletonMeta

        # Reset singleton before test
        SingletonMeta.reset_instance(ConfigReader)

        with patch.dict(os.environ, {"CONFIG_PATH": "/nonexistent/config.json"}):
            with pytest.raises(FileNotFoundError, match="Config file not found"):
                ConfigReader()

        # Cleanup
        SingletonMeta.reset_instance(ConfigReader)

    def test_json_decode_error(self, tmp_path):
        """Test error when config file has invalid JSON."""
        from src.common.singleton_meta import SingletonMeta

        # Reset singleton before test
        SingletonMeta.reset_instance(ConfigReader)

        invalid_config = tmp_path / "invalid.json"
        invalid_config.write_text("{ invalid json }")

        with patch.dict(os.environ, {"CONFIG_PATH": str(invalid_config)}):
            with pytest.raises(Exception):  # JSON decode error
                ConfigReader()

        # Cleanup
        SingletonMeta.reset_instance(ConfigReader)

    def test_validation_error(self, tmp_path):
        """Test error when config file has invalid schema."""
        from src.common.singleton_meta import SingletonMeta

        # Reset singleton before test
        SingletonMeta.reset_instance(ConfigReader)

        invalid_config = tmp_path / "invalid_schema.json"
        invalid_config.write_text('{"invalid_field": "value"}')

        with patch.dict(os.environ, {"CONFIG_PATH": str(invalid_config)}):
            with pytest.raises(ValidationError):
                ConfigReader()

        # Cleanup
        SingletonMeta.reset_instance(ConfigReader)


@pytest.mark.unit
class TestObservabilityConfigSchema:
    """Test ObservabilityConfigSchema specifically."""

    def test_enabled_with_all_fields(self):
        """Test enabled observability with all required fields."""
        config = ObservabilityConfigSchema(
            enable=True,
            secret_key="test_secret",
            public_key="test_public",
            host="http://localhost:3000",
        )

        assert config.enable is True
        assert config.secret_key == "test_secret"
        assert config.public_key == "test_public"
        assert str(config.host) == "http://localhost:3000/"

    def test_enabled_missing_secret_key(self):
        """Test validation error when secret_key is missing."""
        with pytest.raises(ValidationError, match="secret_key is required"):
            ObservabilityConfigSchema(
                enable=True, public_key="test_public", host="http://localhost:3000"
            )

    def test_enabled_missing_public_key(self):
        """Test validation error when public_key is missing."""
        with pytest.raises(ValidationError, match="public_key is required"):
            ObservabilityConfigSchema(
                enable=True, secret_key="test_secret", host="http://localhost:3000"
            )

    def test_enabled_missing_host(self):
        """Test validation error when host is missing."""
        with pytest.raises(ValidationError, match="host is required"):
            ObservabilityConfigSchema(
                enable=True, secret_key="test_secret", public_key="test_public"
            )


@pytest.mark.unit
class TestCacheConfigSchema:
    """Test CacheConfigSchema specifically."""

    def test_enabled_with_password(self):
        """Test enabled cache with password."""
        config = CacheConfigSchema(enable=True, password="test_password")

        assert config.enable is True
        assert config.password == "test_password"

    def test_enabled_without_password(self):
        """Test validation error when password is missing."""
        with pytest.raises(ValidationError, match="Password is required"):
            CacheConfigSchema(enable=True)

    def test_ttl_validation(self):
        """Test TTL validation."""
        # Valid TTL
        config = CacheConfigSchema(ttl_hours=24)
        assert config.ttl_hours == 24

        # Invalid TTL (zero or negative)
        with pytest.raises(ValidationError):
            CacheConfigSchema(ttl_hours=0)

        with pytest.raises(ValidationError):
            CacheConfigSchema(ttl_hours=-1)

    def test_max_size_validation(self):
        """Test max size validation."""
        # Valid size
        config = CacheConfigSchema(max_size_mb=512)
        assert config.max_size_mb == 512

        # Invalid size
        with pytest.raises(ValidationError):
            CacheConfigSchema(max_size_mb=0)

        with pytest.raises(ValidationError):
            CacheConfigSchema(max_size_mb=-100)
