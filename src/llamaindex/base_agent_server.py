"""
Base agent server module providing common FastAPI functionality for all agents.
"""

from abc import ABC, abstractmethod
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from langfuse import get_client as get_langfuse_client
from llama_index.core.agent.workflow import ReActAgent
from llama_index.core.memory import Memory
from llama_index.core.workflow import Context
from pydantic import BaseModel

from src.configs.logging_config import get_logger

logger = get_logger("agents.base")
langfuse_client = get_langfuse_client()


class ChatQuery(BaseModel):
    """The request model for a user's query."""

    query: str


class ChatResponse(BaseModel):
    """The response model for the agent's answer."""

    response: str


class BaseAgentServer(ABC):
    """Base class for agent servers with common FastAPI functionality."""

    def __init__(self, llm, title: str, description: str):
        logger.info(f"Initializing {title} agent server")
        self.agent = self.create_agent(llm)
        self.ctx = Context(self.agent)
        self.app = FastAPI(
            title=title,
            description=description,
            version="1.0.0",
        )
        self._setup_routes()
        self.additional_routes()
        logger.info(f"{title} agent server initialized successfully")

    def _setup_routes(self):
        """Setup common routes for all agent servers."""

        @self.app.get("/description")
        async def description_endpoint():
            return self.app.description

        @self.app.post("/test", response_model=ChatResponse)
        async def test_endpoint(request: ChatQuery):
            """Test endpoint with no additional context."""
            logger.info(
                f"Test endpoint called with query: {request.query[:100]}..."
            )
            try:
                session_id = (
                    f"{getattr(self.agent, 'name', 'agent')}-test-{uuid4()}"
                )

                with langfuse_client.start_as_current_span(
                    name=session_id
                ) as span:

                    agent_response = await self.agent.run(
                        request.query, ctx=self.ctx
                    )

                    span.update_trace(
                        session_id=session_id,
                        input=request.query,
                        output=str(agent_response),
                    )

                logger.info("Test endpoint request processed successfully")

                return ChatResponse(response=str(agent_response))
            except Exception as e:
                logger.error(f"Error in test endpoint: {e}")
                raise HTTPException(
                    status_code=500, detail=f"Error processing request: {e}"
                ) from e

        @self.app.post("/agent", response_model=ChatResponse)
        async def chat_with_agent(request: ChatQuery):
            """Main agent endpoint with context."""
            logger.info(
                f"Agent endpoint called with query: {request.query[:100]}..."
            )
            try:
                session_id = (
                    f"{getattr(
                        self.agent, 'name', 'agent')}-endpoint-{uuid4()}",
                )
                mem = Memory.from_defaults(session_id=session_id)

                with langfuse_client.start_as_current_span(
                    name=session_id
                ) as span:

                    agent_response = await self.agent.run(
                        request.query, ctx=self.ctx, memory=mem
                    )

                    span.update_trace(
                        session_id=session_id,
                        input=request.query,
                        output=str(
                            getattr(
                                agent_response,
                                "structured_response",
                                agent_response,
                            )
                        ),
                    )
                langfuse_client.flush()

                logger.info("Agent request processed successfully")
                return ChatResponse(response=str(agent_response))
            # pylint: disable=duplicate-code
            except Exception as e:
                logger.error(f"Error in agent endpoint: {e}")
                raise HTTPException(
                    status_code=500, detail=f"Error processing query: {e}"
                ) from e

        @self.app.get("/")
        async def root():
            """Root endpoint to confirm API is running."""
            logger.debug("Root endpoint accessed")
            return {
                "message": f"{self.app.title}, "
                "API is running. Go to /docs for interactive documentation."
            }

    @abstractmethod
    def create_agent(self, llm) -> ReActAgent:
        """Returns a generic react agent"""

    @abstractmethod
    def additional_routes(self):
        """Additional routes"""
