"""
This module is an agent with a simple API server for getting
action items from meeting summaries.
"""

import nest_asyncio
from pydantic import BaseModel, Field
from llama_index.core.agent.workflow import ReActAgent
from llama_index.core.llms import ChatMessage
from fastapi import HTTPException
from src.configs import (ModelFactory, ConfigReader,
                         GOOGLE_AGENT_CONTEXT, GOOGLE_MEETING_NOTES)
from src.tools.google_tools import CalendarToolSpec, DocsToolSpec
from src.tools.general_tools import DateToolsSpecs
from src.llamaindex.base_agent_server import BaseAgentServer
from src.llamaindex.utils import safe_load_mcp_tools

nest_asyncio.apply()

config = ConfigReader()


class MeetingNoteFormat(BaseModel):
    """test format for meeting note endpoint reply"""
    link: str = Field(description='link to meeting notes file')
    content: str = Field(
        description='the agent message', default=None)
    error: bool = Field(
        description='field indicating on rather or not an error occurred')


class GoogleAgentServer(BaseAgentServer):
    """Action item agent server implementation."""

    def create_agent(self, llm):
        """Return agent"""
        tools = CalendarToolSpec().to_tool_list() \
            + DocsToolSpec().to_tool_list() \
            + DateToolsSpecs().to_tool_list() \
            + safe_load_mcp_tools(config.config.mcp_config.get('servers', []))

        google_agent = ReActAgent(
            tools=tools,
            llm=llm.llm,
            output_cls=MeetingNoteFormat,
            **config.config.agent_config
        )

        return google_agent

    def get_agent_context(self) -> str:
        """Return the action item agent context."""
        return GOOGLE_AGENT_CONTEXT

    def additional_routes(self):
        @self.app.get("/meeting-notes")
        async def meeting_notes(date: str, meeting: str):
            """Main agent endpoint with context."""
            try:
                agent_context = ChatMessage(
                    role='system',
                    content=self.get_agent_context()
                )

                agent_response = await self.agent.run(GOOGLE_MEETING_NOTES
                                                      .format(
                                                          date=date,
                                                          meeting=meeting),
                                                      chat_history=[
                                                          agent_context],
                                                      ctx=self.ctx
                                                      )

                return agent_response.structured_response
            # pylint: disable=duplicate-code
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Error processing query: {e}"
                ) from e


# Initialize the server
server = GoogleAgentServer(
    llm=ModelFactory(config.config),
    title="Google Agent",
    description="An API to expose a LlamaIndex \
        ReActAgent for Google api access."
)
app = server.app

if __name__ == "__main__":
    print("Make sure your Google API credentials are properly configured.")
