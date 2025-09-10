"""
Integration tests for API endpoints.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.core.base.base_agent_server import BaseAgentServer
from src.core.base.base_server import BaseServer


class MockWorkflowServer(BaseServer):
    """Mock implementation for workflow testing."""

    def create_service(self, llm):
        mock_workflow = MagicMock()
        mock_workflow.run = lambda *args, **kwargs: "Workflow response"
        return mock_workflow

    def additional_routes(self):
        @self.app.post("/workflow")
        async def workflow_endpoint(request: dict):
            result = await self.service.run(request.get("input", ""))
            return {"result": result}


class MockAgentServerForIntegration(BaseAgentServer):
    """Mock implementation for agent testing."""

    def create_service(self, llm):
        mock_agent = MagicMock()
        mock_agent.name = "integration-test-agent"
        mock_agent.run = MagicMock()
        return mock_agent

    def additional_routes(self):
        @self.app.get("/custom")
        async def custom_endpoint():
            return {"message": "Custom endpoint working"}


@pytest.fixture
def mock_llm():
    """Mock LLM for testing."""
    return MagicMock()


@pytest.fixture
def workflow_server(mock_llm):
    """Create workflow server for testing."""
    with patch("src.core.base.base_server.get_logger"):
        return MockWorkflowServer(
            llm=mock_llm,
            title="Test Workflow Server",
            description="Integration test workflow server",
        )


@pytest.fixture
def agent_server(mock_llm):
    """Create agent server for testing."""
    with patch("src.core.base.base_agent_server.set_up_langfuse"), patch(
        "src.core.base.base_agent_server.get_langfuse_client"
    ):
        return MockAgentServerForIntegration(
            llm=mock_llm,
            title="Integration Test Agent",
            description="Integration test agent server",
        )


class TestWorkflowServerIntegration:
    """Integration tests for workflow server."""

    def test_workflow_server_endpoints(self, workflow_server):
        """Test all workflow server endpoints work together."""
        client = TestClient(workflow_server.app)

        # Test root endpoint
        response = client.get("/")
        assert response.status_code == 200
        assert "Test Workflow Server" in response.json()["message"]

        # Test health endpoint
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

        # Test description endpoint
        response = client.get("/description")
        assert response.status_code == 200
        assert response.json() == "Integration test workflow server"

        # Test custom workflow endpoint
        response = client.post("/workflow", json={"input": "test input"})
        assert response.status_code == 200
        assert response.json()["result"] == "Workflow response"


class TestAgentServerIntegration:
    """Integration tests for agent server."""

    @patch("src.core.base.base_agent_server.Memory")
    @patch("src.core.base.base_agent_server.get_langfuse_client")
    def test_agent_server_full_flow(self, mock_langfuse, mock_memory, agent_server):
        """Test complete agent server request flow."""
        client = TestClient(agent_server.app)

        # Setup mocks
        mock_span = MagicMock()
        mock_langfuse_client = MagicMock()
        span_context = mock_langfuse_client.start_as_current_span.return_value
        span_context.__enter__.return_value = mock_span
        mock_langfuse.return_value = mock_langfuse_client

        mock_memory_instance = MagicMock()
        mock_memory.from_defaults.return_value = mock_memory_instance

        agent_server.service.run.return_value = "Agent integration test response"

        # Test all common endpoints
        response = client.get("/")
        assert response.status_code == 200

        response = client.get("/health")
        assert response.status_code == 200

        response = client.get("/description")
        assert response.status_code == 200

        # Test custom endpoint
        response = client.get("/custom")
        assert response.status_code == 200
        assert response.json()["message"] == "Custom endpoint working"

        # Test main agent endpoint
        response = client.post("/agent", json={"query": "integration test query"})
        assert response.status_code == 200
        assert response.json()["response"] == "Agent integration test response"

        # Verify agent was called with correct parameters
        agent_server.service.run.assert_called_once()
        call_args = agent_server.service.run.call_args
        assert call_args[0][0] == "integration test query"
        assert "ctx" in call_args[1]
        assert "memory" in call_args[1]

    def test_agent_server_error_handling_integration(self, agent_server):
        """Test error handling across the full request pipeline."""
        client = TestClient(agent_server.app)

        with patch("src.core.base.base_agent_server.Memory"), patch(
            "src.core.base.base_agent_server.get_langfuse_client"
        ):

            # Make agent raise an exception
            agent_server.service.run.side_effect = Exception("Integration test error")

            response = client.post("/agent", json={"query": "test query"})
            assert response.status_code == 500
            assert "Error processing query" in response.json()["detail"]
            assert "Integration test error" in response.json()["detail"]

    def test_malformed_requests_handling(self, agent_server):
        """Test handling of malformed requests."""
        client = TestClient(agent_server.app)

        # Test invalid JSON
        response = client.post(
            "/agent", data="invalid json", headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422

        # Test missing required field
        response = client.post("/agent", json={})
        assert response.status_code == 422

        # Test wrong field type
        response = client.post("/agent", json={"query": 123})
        assert response.status_code == 422


class TestCrossServerCompatibility:
    """Test compatibility between different server implementations."""

    def test_common_endpoints_consistency(self, workflow_server, agent_server):
        """Test that common endpoints behave consistently across server types."""
        workflow_client = TestClient(workflow_server.app)
        agent_client = TestClient(agent_server.app)

        # Test root endpoints
        workflow_response = workflow_client.get("/")
        agent_response = agent_client.get("/")

        assert workflow_response.status_code == 200
        assert agent_response.status_code == 200
        assert "message" in workflow_response.json()
        assert "message" in agent_response.json()

        # Test health endpoints
        workflow_response = workflow_client.get("/health")
        agent_response = agent_client.get("/health")

        assert workflow_response.status_code == 200
        assert agent_response.status_code == 200

        workflow_health = workflow_response.json()
        agent_health = agent_response.json()

        # Both should have same structure
        assert workflow_health["status"] == "healthy"
        assert agent_health["status"] == "healthy"
        assert "service" in workflow_health
        assert "service" in agent_health
        assert "version" in workflow_health
        assert "version" in agent_health
        assert "timestamp" in workflow_health
        assert "timestamp" in agent_health

    def test_server_isolation(self, workflow_server, agent_server):
        """Test that servers don't interfere with each other."""
        workflow_client = TestClient(workflow_server.app)
        agent_client = TestClient(agent_server.app)

        # Agent server should have agent endpoint
        response = agent_client.post("/agent", json={"query": "test"})
        # Might fail due to missing mocks, but should at least be recognized
        assert response.status_code != 404

        # Workflow server should NOT have agent endpoint
        response = workflow_client.post("/agent", json={"query": "test"})
        assert response.status_code == 404

        # Each should have their custom endpoints
        response = agent_client.get("/custom")
        assert response.status_code == 200

        response = workflow_client.post("/workflow", json={"input": "test"})
        assert response.status_code == 200
