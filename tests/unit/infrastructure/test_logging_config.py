"""
Tests for logging configuration.
"""

import logging
import os
from unittest.mock import MagicMock, patch

from src.infrastructure.logging.logging_config import (
    get_log_level,
    get_logger,
    get_logging_config,
    setup_logging,
)


class TestLoggingConfig:
    """Test cases for logging configuration."""

    def test_get_log_level_default(self):
        """Test get_log_level returns default INFO."""
        with patch.dict(os.environ, {}, clear=True):
            level = get_log_level()
            assert level == "INFO"

    def test_get_log_level_from_env(self):
        """Test get_log_level reads from environment variable."""
        with patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"}):
            level = get_log_level()
            assert level == "DEBUG"

    def test_get_log_level_case_conversion(self):
        """Test that log level is converted to uppercase."""
        with patch.dict(os.environ, {"LOG_LEVEL": "debug"}):
            level = get_log_level()
            assert level == "DEBUG"

    @patch("src.infrastructure.logging.logging_config.Path.mkdir")
    def test_get_logging_config_creates_log_dir(self, mock_mkdir):
        """Test that get_logging_config creates logs directory."""
        config = get_logging_config()

        # Should create logs directory
        mock_mkdir.assert_called_once_with(exist_ok=True)

        # Should return valid config
        assert isinstance(config, dict)
        assert "version" in config
        assert config["version"] == 1

    def test_get_logging_config_structure(self):
        """Test that get_logging_config returns properly structured config."""
        with patch("src.infrastructure.logging.logging_config.Path.mkdir"):
            config = get_logging_config()

            # Check required top-level keys
            required_keys = [
                "version",
                "disable_existing_loggers",
                "formatters",
                "handlers",
                "loggers",
                "root",
            ]
            for key in required_keys:
                assert key in config

            # Check formatters
            assert "standard" in config["formatters"]
            assert "detailed" in config["formatters"]

            # Check handlers
            assert "console" in config["handlers"]
            assert "file" in config["handlers"]
            assert "error_file" in config["handlers"]

            # Check loggers
            assert "agents" in config["loggers"]
            assert "google" in config["loggers"]
            assert "jira" in config["loggers"]

    def test_get_logging_config_uses_log_level(self):
        """Test that get_logging_config uses the environment log level."""
        with patch("src.infrastructure.logging.logging_config.Path.mkdir"), patch.dict(
            os.environ, {"LOG_LEVEL": "WARNING"}
        ):

            config = get_logging_config()

            # Console handler should use the env log level
            assert config["handlers"]["console"]["level"] == "WARNING"
            # Root logger should use the env log level
            assert config["root"]["level"] == "WARNING"

    @patch("src.infrastructure.logging.logging_config.logging.config.dictConfig")
    @patch("src.infrastructure.logging.logging_config.get_logging_config")
    def test_setup_logging_calls_dictconfig(self, mock_get_config, mock_dict_config):
        """Test that setup_logging configures logging properly."""
        mock_config = {"version": 1, "handlers": {}}
        mock_get_config.return_value = mock_config

        # Mock the logger that gets returned
        mock_logger = MagicMock(spec=logging.Logger)
        with patch(
            "src.infrastructure.logging.logging_config.logging.getLogger"
        ) as mock_get_logger:
            mock_get_logger.return_value = mock_logger

            result = setup_logging()

            # Should call dictConfig with the config
            mock_dict_config.assert_called_once_with(mock_config)

            # Should get the 'agents' logger
            mock_get_logger.assert_called_once_with("agents")

            # Should log initialization message
            mock_logger.info.assert_called_once_with("Logging initialized successfully")

            # Should return the logger
            assert result == mock_logger

    def test_get_logger_returns_logger_with_prefix(self):
        """Test that get_logger returns a logger with agents prefix."""
        with patch(
            "src.infrastructure.logging.logging_config.logging.getLogger"
        ) as mock_get_logger:
            mock_logger = MagicMock(spec=logging.Logger)
            mock_get_logger.return_value = mock_logger

            result = get_logger("test.module")

            # Should call getLogger with agents prefix
            mock_get_logger.assert_called_once_with("agents.test.module")
            assert result == mock_logger

    def test_get_logger_different_names(self):
        """Test that get_logger calls getLogger with different names."""
        with patch(
            "src.infrastructure.logging.logging_config.logging.getLogger"
        ) as mock_get_logger:
            get_logger("module1")
            get_logger("module2")

            # Should call getLogger twice with different names
            assert mock_get_logger.call_count == 2
            calls = mock_get_logger.call_args_list
            assert calls[0][0][0] == "agents.module1"
            assert calls[1][0][0] == "agents.module2"

    def test_logging_config_file_paths(self):
        """Test that logging config contains correct file paths."""
        with patch("src.infrastructure.logging.logging_config.Path.mkdir"):
            config = get_logging_config()

            # File handler should point to logs/agent.log
            file_handler = config["handlers"]["file"]
            assert "logs/agent.log" in file_handler["filename"]

            # Error file handler should point to logs/errors.log
            error_handler = config["handlers"]["error_file"]
            assert "logs/errors.log" in error_handler["filename"]

    def test_logging_config_formatters(self):
        """Test that logging config has proper formatters."""
        with patch("src.infrastructure.logging.logging_config.Path.mkdir"):
            config = get_logging_config()

            standard_formatter = config["formatters"]["standard"]
            assert "%(asctime)s" in standard_formatter["format"]
            assert "%(name)s" in standard_formatter["format"]
            assert "%(levelname)s" in standard_formatter["format"]
            assert "%(message)s" in standard_formatter["format"]

            detailed_formatter = config["formatters"]["detailed"]
            assert "%(module)s" in detailed_formatter["format"]
            assert "%(funcName)s" in detailed_formatter["format"]
            assert "%(lineno)d" in detailed_formatter["format"]

    def test_logging_config_agents_logger_setup(self):
        """Test that agents logger is configured properly."""
        with patch("src.infrastructure.logging.logging_config.Path.mkdir"):
            config = get_logging_config()

            agents_logger = config["loggers"]["agents"]
            assert agents_logger["level"] == "DEBUG"
            assert "console" in agents_logger["handlers"]
            assert "file" in agents_logger["handlers"]
            assert "error_file" in agents_logger["handlers"]
            assert agents_logger["propagate"] is False

    def test_logging_config_handler_levels(self):
        """Test that handlers have correct log levels."""
        with patch("src.infrastructure.logging.logging_config.Path.mkdir"):
            config = get_logging_config()

            # File handler should always be DEBUG
            assert config["handlers"]["file"]["level"] == "DEBUG"

            # Error file handler should be ERROR
            assert config["handlers"]["error_file"]["level"] == "ERROR"
