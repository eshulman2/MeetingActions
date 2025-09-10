"""
Tests for agent utilities.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.core.agent_utils import safe_load_mcp_tools


class TestAgentUtils:
    """Test cases for agent utilities."""

    @patch("src.core.agent_utils.aget_tools_from_mcp_url")
    def test_safe_load_mcp_tools_success(self, mock_aget_tools):
        """Test successful loading of MCP tools."""
        # Mock the async function
        mock_tools = [MagicMock(), MagicMock()]
        mock_aget_tools.return_value = mock_tools

        # Mock asyncio.run to avoid actual async execution
        with patch("asyncio.run") as mock_run:
            mock_run.return_value = mock_tools

            mcp_servers = ["http://server1.com", "http://server2.com"]
            result = safe_load_mcp_tools(mcp_servers)

            # Should call asyncio.run for each server
            assert mock_run.call_count == 2

            # Should return combined tools from both servers
            assert len(result) == 4  # 2 tools from each server

    @patch("src.core.agent_utils.aget_tools_from_mcp_url")
    def test_safe_load_mcp_tools_empty_servers(self, mock_aget_tools):
        """Test with empty server list."""
        result = safe_load_mcp_tools([])

        # Should return empty list
        assert result == []
        mock_aget_tools.assert_not_called()

    @patch("src.core.agent_utils.aget_tools_from_mcp_url")
    @patch("src.core.agent_utils.logger")
    def test_safe_load_mcp_tools_exception_handling(self, mock_logger, mock_aget_tools):
        """Test exception handling when MCP server fails."""
        # Mock asyncio.run to raise an exception for the first server
        with patch("asyncio.run") as mock_run:
            mock_run.side_effect = [
                Exception("Connection failed"),  # First server fails
                [MagicMock()],  # Second server succeeds
            ]

            mcp_servers = ["http://failing-server.com", "http://working-server.com"]
            result = safe_load_mcp_tools(mcp_servers)

            # Should log error for failed server
            mock_logger.error.assert_called_once()
            error_call = mock_logger.error.call_args[0][0]
            assert "Failed to load MCP tools" in error_call
            assert "http://failing-server.com" in error_call

            # Should still return tools from working server
            assert len(result) == 1

    @patch("src.core.agent_utils.aget_tools_from_mcp_url")
    @patch("src.core.agent_utils.logger")
    def test_safe_load_mcp_tools_all_servers_fail(self, mock_logger, mock_aget_tools):
        """Test when all servers fail."""
        with patch("asyncio.run") as mock_run:
            mock_run.side_effect = Exception("Connection failed")

            mcp_servers = ["http://server1.com", "http://server2.com"]
            result = safe_load_mcp_tools(mcp_servers)

            # Should log errors for all servers
            assert mock_logger.error.call_count == 2

            # Should return empty list
            assert result == []

    @patch("src.core.agent_utils.aget_tools_from_mcp_url")
    @patch("src.core.agent_utils.logger")
    def test_safe_load_mcp_tools_logs_info(self, mock_logger, mock_aget_tools):
        """Test that info logging works correctly."""
        with patch("asyncio.run") as mock_run:
            mock_run.return_value = [MagicMock()]

            mcp_servers = ["http://test-server.com"]
            safe_load_mcp_tools(mcp_servers)

            # Should log info message for each server
            mock_logger.info.assert_called_once()
            info_call = mock_logger.info.call_args[0][0]
            assert "Fetching tools from mcp" in info_call
            assert "http://test-server.com" in info_call

    def test_safe_load_mcp_tools_with_none_servers(self):
        """Test with None as server list."""
        # This should handle gracefully if passed None
        with pytest.raises((TypeError, AttributeError)):
            safe_load_mcp_tools(None)

    @patch("src.core.agent_utils.aget_tools_from_mcp_url")
    def test_safe_load_mcp_tools_preserves_order(self, mock_aget_tools):
        """Test that tools from different servers are combined in order."""
        with patch("asyncio.run") as mock_run:
            # First server returns tools A, B
            # Second server returns tools C, D
            server1_tools = ["tool_A", "tool_B"]
            server2_tools = ["tool_C", "tool_D"]
            mock_run.side_effect = [server1_tools, server2_tools]

            mcp_servers = ["http://server1.com", "http://server2.com"]
            result = safe_load_mcp_tools(mcp_servers)

            # Should combine tools in order
            expected = ["tool_A", "tool_B", "tool_C", "tool_D"]
            assert result == expected
