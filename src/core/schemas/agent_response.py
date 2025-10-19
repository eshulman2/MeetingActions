"""Unified response model for all agents and API responses."""

from pydantic import BaseModel, Field


class AgentResponse(BaseModel):
    """Unified response model for all agents and API responses.

    This model is used both as the output_cls for ReActAgents and as the
    FastAPI response model for agent endpoints, ensuring consistency across
    the system.
    """

    response: str = Field(
        description="Agent response content or error description if an error occurred"
    )
    error: bool = Field(description="Field indicating whether or not an error occurred")
    additional_info_required: bool = Field(
        default=False,
        description=(
            "Field indicating whether or not additional info is "
            "required to fulfill the request"
        ),
    )
