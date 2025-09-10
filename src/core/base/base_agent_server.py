from uuid import uuid4

from fastapi import HTTPException
from langfuse import get_client as get_langfuse_client
from llama_index.core.memory import Memory
from llama_index.core.workflow import Context
from pydantic import BaseModel

from src.core.base.base_server import BaseServer
from src.infrastructure.logging.logging_config import get_logger
from src.infrastructure.observability.observability import set_up_langfuse

set_up_langfuse()
logger = get_logger("agents.base")


class ChatQuery(BaseModel):
    """The request model for a user's query."""

    query: str


class ChatResponse(BaseModel):
    """The response model for the agent's answer."""

    response: str


class BaseAgentServer(BaseServer):
    def __init__(self, llm, title, description):
        super().__init__(llm, title, description)
        self._setup_agent_routes()

    def _setup_agent_routes(self):
        """Setup common routes for all agent servers."""

        @self.app.post("/agent", response_model=ChatResponse)
        async def chat_with_agent(request: ChatQuery):
            """Main agent endpoint with context and memory.

            This endpoint processes user queries using the configured ReActAgent
            with persistent memory and full observability tracking. The response
            handling prioritizes structured_response when available, falling back
            to the raw agent response for compatibility with different agent types.

            Response Handling Logic:
            - Extracts 'structured_response' attribute from agent response if present
            - Falls back to raw agent_response if structured_response is not available
            - This ensures compatibility with agents that return structured formats
              while maintaining backward compatibility with simple string responses
            """
            logger.info(f"Agent endpoint called with query: {request.query[:100]}...")
            try:
                session_id = f"{getattr(
                    self.service, 'name', 'agent')}-endpoint-{uuid4()}"

                mem = Memory.from_defaults(session_id=session_id)

                langfuse_client = get_langfuse_client()

                with langfuse_client.start_as_current_span(name=session_id) as span:

                    agent_response = await self.service.run(
                        request.query, ctx=Context(self.service), memory=mem
                    )

                    # Extract structured response if available, fallback to raw response
                    # This handles agents with output_cls that return structured formats
                    res = getattr(
                        agent_response,
                        "structured_response",
                        agent_response,
                    )

                    span.update_trace(
                        session_id=session_id,
                        input=request.query,
                        output=str(res),
                    )
                langfuse_client.flush()

                logger.info("Agent request processed successfully")
                return ChatResponse(response=str(res))
            # pylint: disable=duplicate-code
            except Exception as e:
                logger.error(f"Error in agent endpoint: {e}")
                raise HTTPException(
                    status_code=500, detail=f"Error processing query: {e}"
                ) from e
