"""
This module is a Jira agent with a simple API server for Jira operations.
"""

import nest_asyncio
import uvicorn
from llama_index.core.agent.workflow import ReActAgent

from src.core.agents.utils import safe_load_mcp_tools
from src.core.base.base_agent_server import BaseAgentServer
from src.core.schemas.agent_response import AgentResponse
from src.infrastructure.config import get_config, get_model
from src.infrastructure.logging.logging_config import get_logger
from src.infrastructure.prompts.prompts import JIRA_AGENT_CONTEXT
from src.integrations.general_tools import DateToolsSpecs

config = get_config()
logger = get_logger("agents.jira")

nest_asyncio.apply()


class JiraAgentServer(BaseAgentServer):
    """Jira agent server implementation."""

    def create_service(self):
        """Create and return the Jira agent with configured tools."""
        logger.info("Creating Jira agent with tools")
        tools = DateToolsSpecs().to_tool_list() + safe_load_mcp_tools(
            config.config.mcp_config.get("servers", [])
        )
        logger.debug(f"Loaded {len(tools)} tools for Jira agent")

        jira_agent = ReActAgent(
            name="jira-agent",
            tools=tools,
            system_prompt=JIRA_AGENT_CONTEXT,
            llm=self.llm,
            output_cls=AgentResponse,
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
    uvicorn.run(app, host=config.config.host, port=config.config.port, log_level="info")
