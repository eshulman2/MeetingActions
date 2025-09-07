"""Utils"""

import asyncio

from llama_index.tools.mcp import aget_tools_from_mcp_url

from src.infrastructure.logging.logging_config import get_logger

logger = get_logger("utils")


def safe_load_mcp_tools(mcp_servers):
    """safe load mcp tool in case it is not available"""
    tools = []
    for server in mcp_servers:
        try:
            logger.info(f"Fetching tools from mcp: {server}")
            tools.extend(asyncio.run(aget_tools_from_mcp_url(server)))
        # pylint: disable=broad-exception-caught
        except Exception as e:
            logger.error(
                f"Warning: Failed to load MCP tools from {server}: {e}"
            )

    return tools
