from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.chat import router as chat_router
from backend.app.api.health import router as health_router
from backend.app.core.logging import request_logging_middleware, setup_logging

setup_logging()

app = FastAPI(
    title="JobFinder AI Agent API",
    description="FastAPI backend for an autonomous AI job-search agent.",
    version="0.1.0",
)

app.middleware("http")(request_logging_middleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["root"])
async def root() -> dict[str, str]:
    """Public landing endpoint for Railway health checks and quick API discovery."""
    return {
        "name": "JobFinder AI Agent",
        "status": "running",
        "message": "Backend API is running successfully.",
        "health": "/health",
        "docs": "/docs",
    }


app.include_router(health_router)
app.include_router(chat_router)
