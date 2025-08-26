"""
This module is an agent with a simple API server for getting
action items from meeting summaries.
"""

import nest_asyncio
from llama_index.core.workflow import Context
from llama_index.core.agent.workflow import ReActAgent
from src.configs import ModelFactory, ConfigReader, GOOGLE_AGENT_CONTEXT
from src.tools.google_tools import CalendarToolSpec, DocsToolSpec
from src.tools.general_tools import DateToolsSpecs
from src.llamaindex_agents.base_agent_server import BaseAgentServer
from src.llamaindex_agents.utils import safe_load_mcp_tools

nest_asyncio.apply()

config = ConfigReader()
llm = ModelFactory(config.config)

tools = CalendarToolSpec().to_tool_list() \
    + DocsToolSpec().to_tool_list() \
    + DateToolsSpecs().to_tool_list() \
    + safe_load_mcp_tools(config.config.mcp_config.get('servers', []))

google_agent = ReActAgent(
    tools=tools,
    llm=llm.llm,
    **config.config.agent_config
)

ctx = Context(google_agent)


class GoogleAgentServer(BaseAgentServer):
    """Action item agent server implementation."""

    def get_agent_context(self) -> str:
        """Return the action item agent context."""
        return GOOGLE_AGENT_CONTEXT


# Initialize the server
server = GoogleAgentServer(
    agent=google_agent,
    title="Google Agent",
    description="An API to expose a LlamaIndex \
        ReActAgent for Google api access."
)
app = server.app

if __name__ == "__main__":
    print("Make sure your Google API credentials are properly configured.")
