"""
This module is an agent with a simple API server for getting
action items from meeting summaries.
"""

from llama_index.core.workflow import Context
from llama_index.core.agent.workflow import ReActAgent
from llama_index.tools.google import GmailToolSpec
from src.configs import ModelFactory, ConfigReader, GOOGLE_AGENT_CONTEXT
from src.tools.google_tools import CalendarToolSpec, DocsToolSpec
from src.tools.general_tools import DateToolsSpecs
from src.agents.base_agent_server import BaseAgentServer


config = ConfigReader()
llm = ModelFactory(config.config)

tools = CalendarToolSpec().to_tool_list() \
    + DocsToolSpec().to_tool_list() \
    + DateToolsSpecs().to_tool_list() \
    + GmailToolSpec().to_tool_list()


google_agent = ReActAgent(
    tools=tools,
    llm=llm.llm,
    **config.config.agent_config
)

ctx = Context(google_agent)


class ActionItemAgentServer(BaseAgentServer):
    """Action item agent server implementation."""

    def get_agent_context(self) -> str:
        """Return the action item agent context."""
        return GOOGLE_AGENT_CONTEXT


# Initialize the server
server = ActionItemAgentServer(
    agent=google_agent,
    title="Google Agent",
    description="An API to expose a LlamaIndex \
        ReActAgent for Google api access."
)
app = server.app

if __name__ == "__main__":
    print("To run this app, use the following command in your terminal:")
    print("uvicorn action_item_agent:app --reload")
    print("Make sure your Google API credentials are properly configured.")
