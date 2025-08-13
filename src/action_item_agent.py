"""
This module is an agent with a simple API server for getting
action items from meeting summaries.
"""

from llama_index.core.workflow import Context
from llama_index.core.agent.workflow import ReActAgent
from configs.model_factory import ModelFactory
from configs.read_config import ConfigReader
from configs.agents_contexts import ACTION_ITEM_AGENT_CONTEXT
from tools.google_tools import CalendarToolSpec, DocsToolSpec
from tools.general_tools import DateToolsSpecs
from agent_server import BaseAgentServer


config = ConfigReader()
llm = ModelFactory(config.config)

tools = CalendarToolSpec().to_tool_list() + DocsToolSpec().to_tool_list() + \
    DateToolsSpecs().to_tool_list()

action_item_agent = ReActAgent(
    tools=tools,
    llm=llm.llm,
    **config.config.agent_config
)

ctx = Context(action_item_agent)


class ActionItemAgentServer(BaseAgentServer):
    """Action item agent server implementation."""

    def get_agent_context(self) -> str:
        """Return the action item agent context."""
        return ACTION_ITEM_AGENT_CONTEXT


# Initialize the server
server = ActionItemAgentServer(
    agent=action_item_agent,
    title="Action Item Agent",
    description="An API to expose a LlamaIndex \
        ReActAgent for action item extraction."
)
app = server.app

if __name__ == "__main__":
    print("To run this app, use the following command in your terminal:")
    print("uvicorn action_item_agent:app --reload")
    print("Make sure your Google API credentials are properly configured.")
