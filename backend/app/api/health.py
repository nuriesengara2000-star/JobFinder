from __future__ import annotations

from fastapi import APIRouter

from backend.app.schemas.chat import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(status="ok", service="job-ai-agent")
