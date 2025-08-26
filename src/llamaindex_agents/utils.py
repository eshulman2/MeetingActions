"""Utils"""
from llama_index.tools.mcp import get_tools_from_mcp_url


def safe_load_mcp_tools(mcp_servers):
    """Safe load mcp tool in case it is not available"""
    tools = []
    for server in mcp_servers:
        try:
            tools.extend(get_tools_from_mcp_url(server))
        # pylint: disable=broad-exception-caught
        except Exception as e:
            print(f"Warning: Failed to load MCP tools from {server}: {e}")

    return tools
