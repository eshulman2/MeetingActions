"""
This module is an agent with a simple api server for getting
action items from meeting summaries
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from llm_init import InitLlm
from llama_index.core.workflow import Context
from llama_index.core.agent.workflow import ReActAgent
from llama_index.core.llms import ChatMessage
from tools.google_tools import CalendarToolSpec, DocsToolSpec
from tools.general_tools import DateToolsSpecs
from agents_context import ACTION_ITEM_AGENT_CONTEXT


conf = InitLlm()

tools = CalendarToolSpec().to_tool_list() + DocsToolSpec().to_tool_list() + \
    DateToolsSpecs().to_tool_list()

action_item_agent = ReActAgent(
    tools=tools,
    llm=conf.llm,
    verbose=True  # Set verbose for detailed logs
)
ctx = Context(action_item_agent)


class ChatQuery(BaseModel):
    """The request model for a user's query."""
    query: str


class ChatResponse(BaseModel):
    """The response model for the agent's answer."""
    response: str


app = FastAPI(
    title="Google Agent",
    description="An API to expose a LlamaIndex ReActAgent for chat.",
    version="1.0.0",
)


@app.post("/test", response_model=ChatResponse)
async def test_endpoint(request: ChatQuery):
    """
    This endpoint receives is for testing only a user query, passes it to the
    agent with no additional context and returns the agent's response.
    """
    try:
        # Use the agent's asynchronous chat method
        agent_response = await action_item_agent.run(request.query)
        # The actual text response is in the 'response' attribute
        return ChatResponse(response=str(agent_response))
    except Exception as e:
        # Handle potential errors during agent processing
        raise HTTPException(
            status_code=500, detail=f"Error processing query: {e}") from e


@app.post("/agent", response_model=ChatResponse)
async def chat_with_agent(request: ChatQuery):
    """
    This endpoint receives a user query, passes it to the agent,
    and returns the agent's response.
    """
    try:
        agent_context = ChatMessage(role='system',
                                    content=ACTION_ITEM_AGENT_CONTEXT)
        # Use the agent's asynchronous chat method
        agent_response = await action_item_agent.run(request.query,
                                                     chat_history=[
                                                         agent_context])
        # The actual text response is in the 'response' attribute
        return ChatResponse(response=str(agent_response))
    except Exception as e:
        # Handle potential errors during agent processing
        raise HTTPException(
            status_code=500, detail=f"Error processing query: {e}") from e


@app.get("/")
async def root():
    """A simple root endpoint to confirm the API is running."""
    return {"message": "LlamaIndex ReActAgent API is running. Go to /docs "
            "to see the interactive API documentation."}


# 8. Add a main block to run the app with uvicorn
if __name__ == "__main__":
    print("To run this app, use the following command in your terminal:")
    print("uvicorn main:app --reload")
    print("Make sure your OPENAI_API_KEY environment variable is set.")
