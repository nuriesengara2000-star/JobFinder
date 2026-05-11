from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Request body for the AI job-search endpoint."""

    resume_text: str = Field(
        ...,
        min_length=30,
        max_length=20000,
        description="Plain text resume or CV content used by the agent to search jobs.",
    )


class HealthResponse(BaseModel):
    status: str
    service: str
