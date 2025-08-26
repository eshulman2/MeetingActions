"""
This module is a Jira agent with a simple API server for Jira operations.
"""
import os
import nest_asyncio
from llama_index.core.workflow import Context
from llama_index.core.agent.workflow import ReActAgent
from src.configs import ConfigReader, ModelFactory, JIRA_AGENT_CONTEXT
from src.tools.general_tools import DateToolsSpecs
from src.tools.jira_tools import JiraToolSpec
from src.llamaindex_agents.base_agent_server import BaseAgentServer
from src.llamaindex_agents.utils import safe_load_mcp_tools

nest_asyncio.apply()

config = ConfigReader()
llm = ModelFactory(config.config)

tools = DateToolsSpecs().to_tool_list() + JiraToolSpec(
    api_token=os.environ.get('JIRA_API_TOKEN'),
    **config.config.tools_config["jira_tool"]).to_tool_list() \
    + safe_load_mcp_tools(config.config.mcp_config.get('servers', []))

jira_agent = ReActAgent(
    tools=tools,
    llm=llm.llm,
    **config.config.agent_config
)

ctx = Context(jira_agent)


class JiraAgentServer(BaseAgentServer):
    """Jira agent server implementation."""

    def get_agent_context(self) -> str:
        """Return the Jira agent context."""
        return JIRA_AGENT_CONTEXT


# Initialize the server
server = JiraAgentServer(
    agent=jira_agent,
    title="Jira Agent",
    description="An API to expose a LlamaIndex ReActAgent for Jira operations."
)
app = server.app

if __name__ == "__main__":
    print("To run this app, use the following command in your terminal:")
    print("uvicorn jira_agent:app --reload")
    print("Make sure your JIRA_API_TOKEN environment variable is set.")
