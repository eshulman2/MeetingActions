"""
This module is a Jira agent with a simple API server for Jira operations.
"""

import os

import nest_asyncio
from llama_index.core.agent.workflow import ReActAgent

from src import config
from src.core.agent_utils import safe_load_mcp_tools
from src.core.base.base_agent_server import BaseServer
from src.infrastructure.config import JIRA_AGENT_CONTEXT, get_model
from src.infrastructure.logging.logging_config import get_logger
from src.integrations.general_tools import DateToolsSpecs
from src.integrations.jira_tools import JiraToolSpec

logger = get_logger("agents.jira")

nest_asyncio.apply()


class JiraAgentServer(BaseServer):
    """Jira agent server implementation."""

    def create_service(self, llm):
        logger.info("Creating Jira agent with tools")
        tools = (
            DateToolsSpecs().to_tool_list()
            + JiraToolSpec(
                api_token=os.environ.get("JIRA_API_TOKEN"),
                **config.config.tools_config["jira_tool"],
            ).to_tool_list()
            + safe_load_mcp_tools(config.config.mcp_config.get("servers", []))
        )
        logger.debug(f"Loaded {len(tools)} tools for Jira agent")

        jira_agent = ReActAgent(
            name="jira-agent",
            tools=tools,
            system_prompt=JIRA_AGENT_CONTEXT,
            llm=llm,
            **config.config.agent_config,
        )
        logger.info("Jira agent created successfully")

        return jira_agent

    def additional_routes(self):
        logger.debug("No additional routes defined for Jira agent")


# Initialize the server
logger.info("Initializing Jira agent server")
server = JiraAgentServer(
    llm=get_model(config.config),
    title="Jira Agent",
    description=(
        "An API to expose a LlamaIndex ReActAgent for Jira "
        "operations. This is useful for Creating, updating and "
        "managing jira tickets"
    ),
)
app = server.app
logger.info("Jira agent server initialized successfully")

if __name__ == "__main__":
    print("To run this app, use the following command in your terminal:")
    print("uvicorn jira_agent:app --reload")
    print("Make sure your JIRA_API_TOKEN environment variable is set.")
