"""
This module is a Jira agent with a simple API server for Jira operations.
"""

import os
import nest_asyncio
from llama_index.core.agent.workflow import ReActAgent
from src.configs import ConfigReader, ModelFactory, JIRA_AGENT_CONTEXT
from src.tools.general_tools import DateToolsSpecs
from src.tools.jira_tools import JiraToolSpec
from src.llamaindex.base_agent_server import BaseAgentServer
from src.llamaindex.utils import safe_load_mcp_tools

nest_asyncio.apply()

config = ConfigReader()


class JiraAgentServer(BaseAgentServer):
    """Jira agent server implementation."""

    def create_agent(self, llm):
        tools = (
            DateToolsSpecs().to_tool_list()
            + JiraToolSpec(
                api_token=os.environ.get("JIRA_API_TOKEN"),
                **config.config.tools_config["jira_tool"]
            ).to_tool_list()
            + safe_load_mcp_tools(config.config.mcp_config.get("servers", []))
        )

        jira_agent = ReActAgent(tools=tools, llm=llm.llm, **config.config.agent_config)

        return jira_agent

    def get_agent_context(self) -> str:
        """Return the Jira agent context."""
        return JIRA_AGENT_CONTEXT

    def additional_routes(self):
        pass


# Initialize the server
server = JiraAgentServer(
    llm=ModelFactory(config.config),
    title="Jira Agent",
    description="An API to expose a LlamaIndex ReActAgent for Jira operations.",
)
app = server.app

if __name__ == "__main__":
    print("To run this app, use the following command in your terminal:")
    print("uvicorn jira_agent:app --reload")
    print("Make sure your JIRA_API_TOKEN environment variable is set.")
