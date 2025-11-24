"""
Tests for BaseAgentServer class.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from llama_index.core.agent.workflow import ReActAgent
from llama_index.core.memory import Memory

from src.core.schemas.agent_response import AgentResponse
from src.shared.base.base_agent_server import BaseAgentServer, ChatQuery


class MockAgentServer(BaseAgentServer):
    """Mock implementation of BaseAgentServer for testing."""

    def create_service(self):
        mock_agent = MagicMock(spec=ReActAgent)
        mock_agent.name = "test-agent"
        mock_agent.run = AsyncMock()
        return mock_agent

    def additional_routes(self):
        pass


@pytest.fixture
def mock_llm():
    """Mock LLM instance."""
    return MagicMock()


@pytest.fixture
def agent_server(mock_llm):
    """Create a test agent server instance."""
    with patch("src.shared.base.base_agent_server.set_up_langfuse"), patch(
        "src.shared.base.base_agent_server.get_langfuse_client"
    ):
        return MockAgentServer(
            llm=mock_llm, title="Test Agent", description="Test agent for unit testing"
        )


@pytest.fixture
def test_client(agent_server):
    """Create test client."""
    return TestClient(agent_server.app)


class TestBaseAgentServer:
    """Test cases for BaseAgentServer."""

    def test_initialization(self, agent_server):
        """Test agent server initialization."""
        assert agent_server.app.title == "Test Agent"
        assert agent_server.app.description == "Test agent for unit testing"
        assert agent_server.app.version == "1.0.0"
        assert hasattr(agent_server, "service")

    def test_root_endpoint(self, test_client):
        """Test root endpoint."""
        response = test_client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "Test Agent" in data["message"]
        assert "API is running" in data["message"]

    def test_health_endpoint(self, test_client):
        """Test health check endpoint."""
        response = test_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "Test Agent"
        assert data["version"] == "1.0.0"
        assert "timestamp" in data

    def test_description_endpoint(self, test_client):
        """Test description endpoint."""
        response = test_client.get("/description")
        assert response.status_code == 200
        assert response.json() == "Test agent for unit testing"

    @patch("src.shared.base.base_agent_server.Context")
    @patch("src.shared.base.base_agent_server.Memory")
    @patch("src.shared.base.base_agent_server.get_langfuse_client")
    def test_chat_with_agent_success(
        self, mock_langfuse, mock_memory, mock_context, test_client, agent_server
    ):
        """Test successful chat with agent."""
        # Setup mocks
        mock_span = MagicMock()
        mock_langfuse_client = MagicMock()
        span_context = mock_langfuse_client.start_as_current_span.return_value
        span_context.__enter__.return_value = mock_span
        mock_langfuse.return_value = mock_langfuse_client

        mock_memory_instance = MagicMock(spec=Memory)
        mock_memory.from_defaults.return_value = mock_memory_instance

        mock_context_instance = MagicMock()
        mock_context.return_value = mock_context_instance

        # Mock response as dict (matching AgentResponse structure)
        mock_agent_response = MagicMock()
        mock_agent_response.structured_response = {
            "response": "Test response from agent",
            "error": False,
            "additional_info_required": False,
        }
        agent_server.service.run.return_value = mock_agent_response

        # Make request
        query = {"query": "Test query"}
        response = test_client.post("/agent", json=query)

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["response"] == "Test response from agent"
        assert data["error"] is False

        # Verify agent was called correctly
        agent_server.service.run.assert_called_once()
        call_args = agent_server.service.run.call_args
        assert call_args[0][0] == "Test query"
        assert "ctx" in call_args[1]
        assert "memory" in call_args[1]

    @patch("src.shared.base.base_agent_server.Context")
    @patch("src.shared.base.base_agent_server.Memory")
    @patch("src.shared.base.base_agent_server.get_langfuse_client")
    def test_chat_with_agent_structured_response(
        self, mock_langfuse, mock_memory, mock_context, test_client, agent_server
    ):
        """Test chat with agent returning structured response."""
        # Setup mocks
        mock_span = MagicMock()
        mock_langfuse_client = MagicMock()
        span_context = mock_langfuse_client.start_as_current_span.return_value
        span_context.__enter__.return_value = mock_span
        mock_langfuse.return_value = mock_langfuse_client

        mock_memory_instance = MagicMock(spec=Memory)
        mock_memory.from_defaults.return_value = mock_memory_instance

        mock_context_instance = MagicMock()
        mock_context.return_value = mock_context_instance

        # Mock response with structured_response attribute as dict
        mock_response = MagicMock()
        mock_response.structured_response = {
            "response": "Structured response content",
            "error": False,
            "additional_info_required": False,
        }
        agent_server.service.run.return_value = mock_response

        # Make request
        query = {"query": "Test query"}
        response = test_client.post("/agent", json=query)

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["response"] == "Structured response content"
        assert data["error"] is False

    @patch("src.shared.base.base_agent_server.Memory")
    @patch("src.shared.base.base_agent_server.get_langfuse_client")
    def test_chat_with_agent_error(
        self, mock_langfuse, mock_memory, test_client, agent_server
    ):
        """Test error handling in chat endpoint."""
        # Setup mocks
        mock_span = MagicMock()
        mock_langfuse_client = MagicMock()
        span_context = mock_langfuse_client.start_as_current_span.return_value
        span_context.__enter__.return_value = mock_span
        mock_langfuse.return_value = mock_langfuse_client

        mock_memory_instance = MagicMock(spec=Memory)
        mock_memory.from_defaults.return_value = mock_memory_instance

        # Make agent raise an exception
        agent_server.service.run.side_effect = Exception("Test error")

        # Make request
        query = {"query": "Test query"}
        response = test_client.post("/agent", json=query)

        # Assertions
        assert response.status_code == 500
        assert "Error processing query" in response.json()["detail"]

    def test_chat_query_model(self):
        """Test ChatQuery model validation."""
        # Valid query
        query = ChatQuery(query="Test query")
        assert query.query == "Test query"

        # Test with empty string (should still be valid)
        query = ChatQuery(query="")
        assert query.query == ""

    def test_agent_response_model(self):
        """Test AgentResponse model validation."""
        response = AgentResponse(response="Test response", error=False)
        assert response.response == "Test response"
        assert response.error is False
        assert response.additional_info_required is False

        # Test with error
        response = AgentResponse(response="Error occurred", error=True)
        assert response.error is True

        # Test with additional info required
        response = AgentResponse(
            response="Need more info", error=False, additional_info_required=True
        )
        assert response.additional_info_required is True

    def test_invalid_json_request(self, test_client):
        """Test handling of invalid JSON in agent endpoint."""
        response = test_client.post("/agent", data="invalid json")
        assert response.status_code == 422  # Unprocessable Entity

    def test_missing_query_field(self, test_client):
        """Test handling of missing query field."""
        response = test_client.post("/agent", json={})
        assert response.status_code == 422  # Unprocessable Entity
