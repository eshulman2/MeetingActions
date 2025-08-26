"""
Base agent server module providing common FastAPI functionality for all agents.
"""
from abc import ABC, abstractmethod
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from llama_index.core.agent.workflow import ReActAgent
from llama_index.core.llms import ChatMessage


class ChatQuery(BaseModel):
    """The request model for a user's query."""
    query: str


class ChatResponse(BaseModel):
    """The response model for the agent's answer."""
    response: str


class BaseAgentServer(ABC):
    """Base class for agent servers with common FastAPI functionality."""

    def __init__(self, agent: ReActAgent, title: str, description: str,
                 additional_routes=None):
        self.agent = agent
        self.app = FastAPI(
            title=title,
            description=description,
            version="1.0.0",
        )
        self._setup_routes()
        if additional_routes:
            self._register_additional_routes(additional_routes)

    def _setup_routes(self):
        """Setup common routes for all agent servers."""

        @self.app.post("/test", response_model=ChatResponse)
        async def test_endpoint(request: ChatQuery):
            """Test endpoint with no additional context."""
            try:
                agent_response = await self.agent.run(request.query)
                return ChatResponse(response=str(agent_response))
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Error processing query: {e}"
                ) from e

        @self.app.post("/agent", response_model=ChatResponse)
        async def chat_with_agent(request: ChatQuery):
            """Main agent endpoint with context."""
            try:
                agent_context = ChatMessage(
                    role='system',
                    content=self.get_agent_context()
                )
                agent_response = await self.agent.run(
                    request.query,
                    chat_history=[agent_context]
                )
                return ChatResponse(response=str(agent_response))
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Error processing query: {e}"
                ) from e

        @self.app.get("/")
        async def root():
            """Root endpoint to confirm API is running."""
            return {
                "message": f"{self.app.title}, "
                "API is running. Go to /docs for interactive documentation."
            }

    def _register_additional_routes(self, routes):
        """Register additional routes from a list of route definitions."""
        for route in routes:
            self.app.add_api_route(**route)

    @abstractmethod
    def get_agent_context(self) -> str:
        """Return the agent-specific context string."""
