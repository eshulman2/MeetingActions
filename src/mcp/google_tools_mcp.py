"""Simple MCP server serving google tools"""

from fastmcp import FastMCP

from src.infrastructure.config import get_config
from src.integrations.google_tools import GmailToolSpec, GoogleToolSpec

tools = GmailToolSpec().to_tool_list() + GoogleToolSpec().to_tool_list()
config = get_config()
mcp_server = FastMCP("Google tools mcp server")

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
