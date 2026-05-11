from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from backend.app.core.rate_limit import InMemoryRateLimiter
from backend.app.schemas.chat import ChatRequest
from backend.app.services.job_matching import build_search_queries, format_ranked_answer, rank_jobs

router = APIRouter(tags=["chat"])
logger = logging.getLogger(__name__)
rate_limiter = InMemoryRateLimiter(max_requests=5, window_seconds=60)


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _run_agent_stream(resume_text: str) -> AsyncGenerator[str, None]:
    """Run the existing ReAct agent and expose the result through SSE.

    The current agent returns the final answer after its full ReAct loop. This
    endpoint already uses StreamingResponse, so the frontend can consume it as a
    stream. Later we can improve it to stream every ReAct step token-by-token.
    """
    yield _sse_event("status", {"message": "Agent started analyzing the resume."})

    try:
        from react_agent.agent import JobSearchAgent

        agent = JobSearchAgent()
        answer = await asyncio.to_thread(agent.run, resume_text)
        await _add_focused_searches(agent)
    except RuntimeError as exc:
        logger.warning("Configuration error while running agent: %s", exc)
        yield _sse_event("error", {"message": str(exc)})
        return
    except Exception as exc:  # noqa: BLE001
        logger.exception("Agent failed")
        yield _sse_event("error", {"message": "Agent failed while searching jobs."})
        return

    ranked_jobs = rank_jobs(agent.collected_jobs, agent.parsed_resume, limit=12)
    ranked_answer = format_ranked_answer(ranked_jobs, agent.parsed_resume)

    payload = {
        "answer": ranked_answer or answer,
        "raw_answer": answer,
        "parsed_resume": agent.parsed_resume,
        "jobs_count": len(ranked_jobs),
        "raw_jobs_count": len(agent.collected_jobs),
        "jobs": ranked_jobs,
    }
    yield _sse_event("final", payload)


async def _add_focused_searches(agent: object) -> None:
    """Add deterministic, profile-focused searches after the ReAct loop.

    The LLM agent is still responsible for autonomous tool usage, but this
    safeguard improves practical quality: if the model searched too broadly
    (for example just "AI"), we add several focused queries from the parsed
    resume and let the ranking layer remove irrelevant senior/sales/legal jobs.
    """
    try:
        from react_agent.tools import hh_search_jobs, linkedin_search_jobs, remoteok_search_jobs, wwr_search_jobs
    except Exception:  # noqa: BLE001
        logger.exception("Could not import search tools for focused search")
        return

    parsed_resume = getattr(agent, "parsed_resume", {}) or {}
    collected_jobs = getattr(agent, "collected_jobs", [])
    seen_urls = {str(job.get("url")) for job in collected_jobs if isinstance(job, dict) and job.get("url")}

    queries = build_search_queries(parsed_resume)
    if not queries:
        return

    def add_jobs(new_jobs: list[dict]) -> None:
        for job in new_jobs:
            if not isinstance(job, dict):
                continue
            url = str(job.get("url") or "")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            collected_jobs.append(job)

    for query in queries[:5]:
        try:
            add_jobs(await asyncio.to_thread(hh_search_jobs, query, 40, 8))
        except Exception:  # noqa: BLE001
            logger.exception("Focused HH search failed for query=%s", query)

    # Add remote sources for AI/backend profiles, where local HH can be too narrow.
    for query in queries[:3]:
        try:
            add_jobs(await asyncio.to_thread(linkedin_search_jobs, query, "Kazakhstan", 5))
        except Exception:  # noqa: BLE001
            logger.exception("Focused LinkedIn search failed for query=%s", query)
        try:
            add_jobs(await asyncio.to_thread(remoteok_search_jobs, query, 5))
        except Exception:  # noqa: BLE001
            logger.exception("Focused RemoteOK search failed for query=%s", query)
        try:
            add_jobs(await asyncio.to_thread(wwr_search_jobs, query, 5))
        except Exception:  # noqa: BLE001
            logger.exception("Focused WWR search failed for query=%s", query)

    setattr(agent, "collected_jobs", collected_jobs)


@router.post("/chat")
async def chat(
    request: ChatRequest,
    _: None = Depends(rate_limiter),
) -> StreamingResponse:
    if not request.resume_text.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="resume_text cannot be empty.",
        )

    return StreamingResponse(
        _run_agent_stream(request.resume_text),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
