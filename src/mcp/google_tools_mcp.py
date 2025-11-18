"""Simple MCP server serving google tools"""

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from src.infrastructure.config import get_config
from src.infrastructure.logging.logging_config import get_logger
from src.integrations.google_tools import GmailToolSpec, GoogleToolSpec

logger = get_logger("mcp.google_tools")

logger.info("Initializing Google MCP server")

try:
    tools = GmailToolSpec().to_tool_list() + GoogleToolSpec().to_tool_list()
    logger.info(f"Loaded {len(tools)} tools for Google MCP server")
except Exception as e:
    logger.error(f"Failed to load tools: {e}", exc_info=True)
    raise

config = get_config()
mcp_server = FastMCP("Google tools mcp server")


# Health check endpoint using FastMCP custom_route
@mcp_server.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> PlainTextResponse:
    """Health check endpoint for container monitoring"""
    return PlainTextResponse("OK")


for tool in tools:
    logger.debug(f"Registering tool: {tool.metadata.name}")
    mcp_server.tool(name=tool.metadata.name, description=tool.metadata.description)(
        tool.real_fn
    )

logger.info(f"Registered {len(tools)} tools with MCP server")

if __name__ == "__main__":
    logger.info(
        f"Starting Google MCP server on {config.config.host}:{config.config.port}"
    )
    mcp_server.run(
        transport="streamable-http",
        port=config.config.port,
        host="0.0.0.0",
    )
