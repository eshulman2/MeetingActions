"""
Unit tests for BaseServer and BaseAgentServer.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.base.base_agent_server import BaseAgentServer, ChatQuery, ChatResponse
from src.core.base.base_server import BaseServer


class MockAgent:
    """Mock agent for testing."""

    def __init__(self, name="test-agent"):
        self.name = name

    async def run(self, query, ctx=None, memory=None):
        return f"Mock response to: {query}"


class TestBaseServer(BaseServer):
    """Test implementation of BaseServer."""

    def create_service(self, llm):
        return MockAgent()

    def additional_routes(self):
        @self.app.get("/test-endpoint")
        async def test_endpoint():
            return {"message": "test"}


class TestBaseAgentServer(BaseAgentServer):
    """Test implementation of BaseAgentServer."""

    def create_service(self, llm):
        return MockAgent()

    def additional_routes(self):
        pass


@pytest.mark.unit
class TestBaseServerClass:
    """Test BaseServer functionality."""

    def test_server_initialization(self, mock_llm):
        """Test server initialization."""
        server = TestBaseServer(
            llm=mock_llm, title="Test Server", description="Test Description"
        )

        assert server.app.title == "Test Server"
        assert server.app.description == "Test Description"
        assert server.app.version == "1.0.0"
        assert isinstance(server.service, MockAgent)

    def test_common_routes_exist(self, mock_llm, test_client_factory):
        """Test that common routes are created."""
        server = TestBaseServer(
            llm=mock_llm, title="Test Server", description="Test Description"
        )
        client = test_client_factory(server.app)

        # Test root endpoint
        response = client.get("/")
        assert response.status_code == 200
        assert "Test Server" in response.json()["message"]

        # Test description endpoint
        response = client.get("/description")
        assert response.status_code == 200
        assert response.json() == "Test Description"

        # Test health endpoint
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "Test Server"
        assert data["version"] == "1.0.0"
        assert "timestamp" in data

    def test_additional_routes(self, mock_llm, test_client_factory):
        """Test that additional routes are added."""
        server = TestBaseServer(
            llm=mock_llm, title="Test Server", description="Test Description"
        )
        client = test_client_factory(server.app)

        response = client.get("/test-endpoint")
        assert response.status_code == 200
        assert response.json() == {"message": "test"}


@pytest.mark.unit
class TestBaseAgentServerClass:
    """Test BaseAgentServer functionality."""

    def test_agent_server_initialization(self, mock_llm):
        """Test agent server initialization."""
        server = TestBaseAgentServer(
            llm=mock_llm, title="Test Agent", description="Test Agent Description"
        )

        assert server.app.title == "Test Agent"
        assert isinstance(server.service, MockAgent)

    @patch("src.core.base.base_agent_server.Context")
    @patch("src.core.base.base_agent_server.Memory")
    @patch("src.core.base.base_agent_server.get_langfuse_client")
    @pytest.mark.asyncio
    async def test_agent_endpoint(
        self, mock_langfuse, mock_memory, mock_context, mock_llm, test_client_factory
    ):
        """Test agent chat endpoint."""
        # Setup mocks
        mock_span = MagicMock()
        mock_langfuse_client = MagicMock()
        span_context = mock_langfuse_client.start_as_current_span.return_value
        span_context.__enter__.return_value = mock_span
        mock_langfuse.return_value = mock_langfuse_client

        mock_memory_instance = MagicMock()
        mock_memory.from_defaults.return_value = mock_memory_instance

        mock_context_instance = MagicMock()
        mock_context.return_value = mock_context_instance

        server = TestBaseAgentServer(
            llm=mock_llm, title="Test Agent", description="Test Agent Description"
        )

        client = test_client_factory(server.app)

        # Mock the async agent run method
        server.service.run = AsyncMock(return_value="Test response")

        response = client.post("/agent", json={"query": "test query"})
        assert response.status_code == 200

        data = response.json()
        assert "response" in data

    def test_chat_query_validation(self):
        """Test ChatQuery model validation."""
        # Valid query
        query = ChatQuery(query="Test query")
        assert query.query == "Test query"

        # Test with empty query - should still be valid
        query = ChatQuery(query="")
        assert query.query == ""

    def test_chat_response_creation(self):
        """Test ChatResponse model creation."""
        response = ChatResponse(response="Test response")
        assert response.response == "Test response"


@pytest.mark.unit
class TestBaseServerRoutes:
    """Test specific route functionality."""

    def test_health_check_content(self, mock_llm, test_client_factory):
        """Test health check endpoint content."""
        server = TestBaseServer(
            llm=mock_llm, title="Health Test Server", description="Health Test"
        )
        client = test_client_factory(server.app)

        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "Health Test Server"
        assert data["version"] == "1.0.0"
        assert isinstance(data["timestamp"], (int, float))

    def test_description_endpoint(self, mock_llm, test_client_factory):
        """Test description endpoint."""
        server = TestBaseServer(
            llm=mock_llm, title="Description Test", description="Custom Description"
        )
        client = test_client_factory(server.app)

        response = client.get("/description")
        assert response.status_code == 200
        assert response.json() == "Custom Description"

    def test_root_endpoint_message(self, mock_llm, test_client_factory):
        """Test root endpoint message format."""
        server = TestBaseServer(
            llm=mock_llm, title="Root Test Server", description="Root Test"
        )
        client = test_client_factory(server.app)

        response = client.get("/")
        assert response.status_code == 200

        data = response.json()
        assert "Root Test Server" in data["message"]
        assert "API is running" in data["message"]
        assert "/docs" in data["message"]
