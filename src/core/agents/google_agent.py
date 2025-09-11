"""
This module is an agent with a simple API server for getting
action items from meeting summaries.
"""

from uuid import uuid4

import nest_asyncio
import uvicorn
from fastapi import HTTPException
from langfuse import get_client as get_langfuse_client
from llama_index.core.agent.workflow import ReActAgent
from llama_index.core.memory import Memory
from llama_index.core.workflow import Context
from pydantic import BaseModel, Field

from src.core.agent_utils import safe_load_mcp_tools
from src.core.base.base_agent_server import BaseAgentServer
from src.infrastructure.config import (
    GOOGLE_AGENT_CONTEXT,
    GOOGLE_MEETING_NOTES,
    get_config,
    get_model,
)
from src.infrastructure.logging.logging_config import get_logger
from src.infrastructure.observability.observability import set_up_langfuse
from src.integrations.general_tools import DateToolsSpecs

set_up_langfuse()
logger = get_logger("agents.google")
config = get_config()

nest_asyncio.apply()


class AgentResponseFormat(BaseModel):
    """test format for meeting note endpoint reply"""

    response: str = Field(description="Response if an error occurred describe it")
    error: bool = Field(
        description="field indicating on rather or not an error occurred"
    )
    additional_info: str | None = Field(
        description="ask for additional info if needed", default=None
    )


class GoogleAgentServer(BaseAgentServer):
    """Google agent server implementation."""

    def create_service(self, llm):
        """Return agent"""
        logger.info("Creating Google agent with tools")
        tools = DateToolsSpecs().to_tool_list() + safe_load_mcp_tools(
            config.config.mcp_config.get("servers", [])
        )
        logger.debug(f"Loaded {len(tools)} tools for Google agent")

        google_agent = ReActAgent(
            name="google-agent",
            tools=tools,
            llm=llm,
            system_prompt=GOOGLE_AGENT_CONTEXT,
            output_cls=AgentResponseFormat,
            **config.config.agent_config,
        )
        logger.info("Google agent created successfully")

        return google_agent

    def additional_routes(self):

        @self.app.get("/meeting-notes")
        async def meeting_notes(date: str, meeting: str):
            """Main agent endpoint with context."""
            logger.info(
                f"Processing meeting notes request for date: {date}, meeting: "
                f"{meeting}"
            )
            try:
                session_id = f"meeting-notes-{str(uuid4())}"
                mem = Memory.from_defaults(session_id=session_id)
                langfuse_client = get_langfuse_client()

                with langfuse_client.start_as_current_span(name=session_id) as span:

                    agent_response = await self.service.run(
                        GOOGLE_MEETING_NOTES.format(date=date, meeting=meeting),
                        ctx=Context(self.service),
                        memory=mem,
                    )

                    span.update_trace(
                        session_id=session_id,
                        input=GOOGLE_MEETING_NOTES.format(date=date, meeting=meeting),
                        output=str(
                            getattr(
                                agent_response,
                                "structured_response",
                                agent_response,
                            )
                        ),
                    )
                langfuse_client.flush()

                logger.info("Meeting notes request processed successfully")
                return agent_response.structured_response
            # pylint: disable=duplicate-code
            except Exception as e:
                logger.error(f"Error processing meeting notes request: {e}")
                raise HTTPException(
                    status_code=500, detail=f"Error processing query: {e}"
                ) from e


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
