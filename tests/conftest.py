"""
Pytest configuration and shared fixtures for all tests.
"""

import os
import tempfile
from unittest.mock import Mock, patch

import fakeredis
import pytest
from fastapi.testclient import TestClient

from src.infrastructure.cache.redis_cache import RedisDocumentCache
from src.infrastructure.config.read_config import ConfigReader, ConfigSchema


@pytest.fixture(scope="session", autouse=True)
def test_environment():
    """Set up test environment variables."""
    # Already set above, but ensure they persist
    yield
    # Cleanup if needed


@pytest.fixture
def temp_config_file():
    """Create a temporary config file for testing."""
    config_data = {
        "llm": "OpenAI",
        "model": "gpt-3.5-turbo",
        "model_api_key": "test_key",
        "verify_ssl": True,
        "max_document_length": 1000,
        "additional_model_parameter": {},
        "tools_config": {"jira_tool": {"server": "https://test-jira.atlassian.net"}},
        "agent_config": {"max_iterations": 10, "verbose": True},
        "mcp_config": {"servers": []},
        "observability": {
            "enable": False,
            "secret_key": None,
            "public_key": None,
            "host": None,
        },
        "cache_config": {
            "enable": False,
            "ttl_hours": 1,
            "max_size_mb": 100,
            "host": "localhost",
            "port": 6379,
            "password": None,
        },
        "meeting_notes_endpoint": "http://127.0.0.1:8002/meeting-notes",
        "agents": {"jira": "http://127.0.0.1:8000", "google": "http://127.0.0.1:8001"},
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        import json

        json.dump(config_data, f)
        temp_path = f.name

    # Set environment variable to use temp config
    old_config_path = os.environ.get("CONFIG_PATH")
    os.environ["CONFIG_PATH"] = temp_path

    yield temp_path

    # Cleanup
    os.unlink(temp_path)
    if old_config_path:
        os.environ["CONFIG_PATH"] = old_config_path
    else:
        os.environ.pop("CONFIG_PATH", None)


@pytest.fixture
def reset_singletons():
    """Reset singleton instances before each test."""
    # Reset ConfigReader singleton
    if ConfigReader in ConfigReader.__class__._instances:
        del ConfigReader.__class__._instances[ConfigReader]

    # Reset RedisDocumentCache singleton
    if RedisDocumentCache in RedisDocumentCache.__class__._instances:
        del RedisDocumentCache.__class__._instances[RedisDocumentCache]

    yield

    # Reset again after test
    if ConfigReader in ConfigReader.__class__._instances:
        del ConfigReader.__class__._instances[ConfigReader]
    if RedisDocumentCache in RedisDocumentCache.__class__._instances:
        del RedisDocumentCache.__class__._instances[RedisDocumentCache]


@pytest.fixture
def test_config(temp_config_file, reset_singletons) -> ConfigSchema:
    """Provide a test configuration instance."""
    config_reader = ConfigReader()
    return config_reader.config


@pytest.fixture
def mock_redis():
    """Provide a mock Redis client using fakeredis."""
    fake_redis = fakeredis.FakeRedis(decode_responses=True)

    with patch("redis.Redis", return_value=fake_redis):
        yield fake_redis


@pytest.fixture
def mock_llm():
    """Provide a mock LLM instance."""
    mock = Mock()
    mock.complete.return_value.text = "Mock LLM response"
    mock.acomplete.return_value.text = "Mock async LLM response"
    return mock


@pytest.fixture
def mock_jira_client():
    """Provide a mock JIRA client."""
    mock = Mock()
    mock.projects.return_value = [Mock(key="TEST", name="Test Project", id="12345")]
    mock.issue.return_value = Mock(
        key="TEST-123",
        fields=Mock(
            summary="Test Issue",
            description="Test Description",
            status=Mock(name="Open"),
        ),
    )
    return mock


@pytest.fixture
def mock_google_service():
    """Provide a mock Google API service."""
    mock = Mock()
    mock.documents().get().execute.return_value = {
        "body": {
            "content": [
                {
                    "paragraph": {
                        "elements": [{"textRun": {"content": "Test document content"}}]
                    }
                }
            ]
        },
        "title": "Test Document",
    }
    return mock


@pytest.fixture
def test_client_factory():
    """Factory for creating test clients for FastAPI apps."""

    def _create_client(app):
        return TestClient(app)

    return _create_client


@pytest.fixture
def sample_meeting_notes():
    """Sample meeting notes for testing workflows."""
    return """
    Meeting: Weekly Team Sync
    Date: 2024-01-15

    Attendees: Alice, Bob, Charlie

    Discussion:
    - Reviewed current sprint progress
    - Discussed upcoming feature releases
    - Identified blockers in authentication module

    Action Items:
    - Alice: Fix authentication bug by Friday
    - Bob: Review pull request #123
    - Charlie: Update documentation for new API endpoints
    """


@pytest.fixture
def sample_action_items():
    """Sample parsed action items for testing."""
    return [
        {
            "assignee": "Alice",
            "task": "Fix authentication bug",
            "due_date": "Friday",
            "priority": "high",
        },
        {
            "assignee": "Bob",
            "task": "Review pull request #123",
            "due_date": None,
            "priority": "medium",
        },
        {
            "assignee": "Charlie",
            "task": "Update documentation for new API endpoints",
            "due_date": None,
            "priority": "low",
        },
    ]


@pytest.fixture
def mock_httpx_client():
    """Provide a mock httpx client for testing HTTP requests."""
    with patch("httpx.AsyncClient") as mock:
        mock_client = Mock()
        mock.return_value.__aenter__.return_value = mock_client
        mock_client.get.return_value.status_code = 200
        mock_client.get.return_value.json.return_value = {"status": "ok"}
        mock_client.post.return_value.status_code = 200
        mock_client.post.return_value.json.return_value = {"result": "success"}
        yield mock_client


# Pytest asyncio configuration
pytest_plugins = ["pytest_asyncio"]


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "performance: Performance tests")
    config.addinivalue_line("markers", "slow: Slow running tests")
    config.addinivalue_line("markers", "redis: Tests requiring Redis")
    config.addinivalue_line("markers", "external: Tests requiring external services")
