"""Simple MCP server serving JIRA tools"""

import os

from fastmcp import FastMCP

from src.infrastructure.config import get_config
from src.integrations.jira_tools import JiraToolSpec

# Get JIRA configuration
config = get_config()
api_token = os.environ.get("JIRA_API_TOKEN")
if not api_token:
    raise ValueError("JIRA_API_TOKEN environment variable is required")

jira_server = config.config.tools_config.get("jira_tool", {}).get("server")
if not jira_server:
    raise ValueError("JIRA server must be configured in tools_config.jira_tool.server")

# Initialize JIRA tools
tools = JiraToolSpec(api_token=api_token, server=jira_server).to_tool_list()

# Create MCP server
mcp_server = FastMCP("JIRA tools mcp server")

# Register all tools with the MCP server
for tool in tools:
    mcp_server.tool(name=tool.metadata.name, description=tool.metadata.description)(
        tool.real_fn
    )

if __name__ == "__main__":
    mcp_server.run(
        transport="streamable-http",
        port=config.config.port,
        host="0.0.0.0",
    )
