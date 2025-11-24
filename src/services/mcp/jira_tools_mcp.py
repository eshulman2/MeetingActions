"""Simple MCP server serving JIRA tools"""

import os

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from src.infrastructure.config import get_config
from src.infrastructure.logging.logging_config import get_logger
from src.integrations.jira import JiraToolSpec

logger = get_logger("mcp.jira_tools")

logger.info("Initializing JIRA MCP server")

# Get JIRA configuration
config = get_config()
api_token = os.environ.get("JIRA_API_TOKEN")
if not api_token:
    logger.error("JIRA_API_TOKEN environment variable is not set")
    raise ValueError("JIRA_API_TOKEN environment variable is required")

jira_server = config.config.tools_config.get("jira_tool", {}).get("server")
if not jira_server:
    logger.error("JIRA server not configured in tools_config.jira_tool.server")
    raise ValueError("JIRA server must be configured in tools_config.jira_tool.server")

logger.info(f"Connecting to JIRA server: {jira_server}")

# Initialize JIRA tools
try:
    tools = JiraToolSpec(api_token=api_token, server=jira_server).to_tool_list()
    logger.info(f"Loaded {len(tools)} tools for JIRA MCP server")
except Exception as e:
    logger.error(f"Failed to load JIRA tools: {e}", exc_info=True)
    raise

# Create MCP server
mcp_server = FastMCP("JIRA tools mcp server")


# Health check endpoint using FastMCP custom_route
@mcp_server.custom_route("/health", methods=["GET"])
async def health_check(_request: Request) -> PlainTextResponse:
    """Health check endpoint for container monitoring"""
    return PlainTextResponse("OK")


# Register all tools with the MCP server
for tool in tools:
    logger.debug(f"Registering tool: {tool.metadata.name}")
    mcp_server.tool(name=tool.metadata.name, description=tool.metadata.description)(
        tool.real_fn
    )

logger.info(f"Registered {len(tools)} tools with MCP server")

if __name__ == "__main__":
    logger.info(
        f"Starting JIRA MCP server on {config.config.host}:{config.config.port}"
    )
    mcp_server.run(
        transport="streamable-http",
        port=config.config.port,
        host="0.0.0.0",
    )
