"""Simple MCP server serving gmail tools"""

from fastmcp import FastMCP
from llama_index.tools.google import GmailToolSpec

from src.configs.read_config import ConfigReader

config = ConfigReader()
tools = GmailToolSpec().to_tool_list()

mcp_server = FastMCP("Google tools mcp server")

for tool in tools:
    mcp_server.tool(name=tool.metadata.name, description=tool.metadata.description)(
        tool.real_fn
    )

if __name__ == "__main__":
    mcp_server.run(
        transport="streamable-http", port=config.config.mcp_config.get("port", 8002)
    )
