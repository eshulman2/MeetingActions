"""
This module is an agent with a simple API server for getting
action items from meeting summaries.
"""

import nest_asyncio
import uvicorn
from llama_index.core.agent.workflow import ReActAgent

from src.core.schemas.agent_response import AgentResponse
from src.infrastructure.config import get_config, get_model
from src.infrastructure.logging.logging_config import get_logger
from src.infrastructure.observability.observability import set_up_langfuse
from src.infrastructure.prompts.prompts import GOOGLE_AGENT_CONTEXT
from src.integrations.common import DateToolsSpecs
from src.shared.agents.utils import safe_load_mcp_tools
from src.shared.base.base_agent_server import BaseAgentServer

set_up_langfuse()
logger = get_logger("agents.google")
config = get_config()

nest_asyncio.apply()


class GoogleAgentServer(BaseAgentServer):
    """Google agent server implementation."""

    def create_service(self):
        """Create and return the Google agent with configured tools."""
        logger.info("Creating Google agent with tools")
        tools = DateToolsSpecs().to_tool_list() + safe_load_mcp_tools(
            config.config.mcp_config.get("servers", [])
        )
        logger.debug(f"Loaded {len(tools)} tools for Google agent")

        google_agent = ReActAgent(
            name="google-agent",
            tools=tools,
            llm=self.llm,
            system_prompt=GOOGLE_AGENT_CONTEXT,
            output_cls=AgentResponse,
            **config.config.agent_config,
        )
        logger.info("Google agent created successfully")

        return google_agent

    def additional_routes(self):
        pass


# Initialize the server
logger.info("Initializing Google agent server")
server = GoogleAgentServer(
    llm=get_model(config.config),
    title="Google Agent",
    description=(
        "An API to expose a LlamaIndex "
        "ReActAgent for Google api access. This agent is useful for "
        "interacting with gmail for sending emails, google calendar "
        "and google docs"
    ),
)
app = server.app
logger.info("Google agent server initialized successfully")

if __name__ == "__main__":
    uvicorn.run(app, host=config.config.host, port=config.config.port, log_level="info")
