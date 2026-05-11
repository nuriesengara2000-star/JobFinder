"""Tools available to the ReAct job-search agent.

Five tools total:

* ``parse_resume(resume_text)`` — LLM-backed structured extraction.
* ``hh_search_jobs(query, area=40, per_page=15)`` — HeadHunter (KZ default).
* ``linkedin_search_jobs(query, location='Kazakhstan', per_page=15)`` — LinkedIn guest endpoint.
* ``remoteok_search_jobs(query, per_page=15)`` — RemoteOK public JSON feed.
* ``wwr_search_jobs(query, per_page=15)`` — We Work Remotely RSS feeds.

Every search tool returns the same dict shape:
``{title, company, salary, requirements, url, source}``.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from openai import OpenAI

try:  # package-style import
    from .sources import hh as _hh
    from .sources import linkedin as _linkedin
    from .sources import remoteok as _remoteok
    from .sources import wwr as _wwr
except ImportError:  # script-style import (python main.py from inside react_agent/)
    from sources import hh as _hh
    from sources import linkedin as _linkedin
    from sources import remoteok as _remoteok
    from sources import wwr as _wwr

LOG = logging.getLogger(__name__)

_VALID_LEVELS = {"junior", "middle", "senior"}
_openai_client: OpenAI | None = None


def _client() -> OpenAI:
    global _openai_client
    if _openai_client is None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set in the environment")
        _openai_client = OpenAI(api_key=api_key)
    return _openai_client


# ---------------------------------------------------------------------------
# Resume parser
# ---------------------------------------------------------------------------

def parse_resume(resume_text: str) -> dict[str, Any]:
    """Extract skills, desired role, and experience level from a resume."""
    if not resume_text or not resume_text.strip():
        LOG.warning("parse_resume called with empty text")
        return {"skills": [], "desired_role": "", "experience_level": "junior"}

    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    system = (
        "You are a resume parser. Read the resume and return STRICT JSON with "
        "exactly these keys:\n"
        '  "skills":            array of short technical keywords\n'
        '  "desired_role":      one short job title in English (e.g. "Python Developer")\n'
        '  "experience_level":  one of "junior", "middle", "senior"\n'
        "Output JSON only."
    )
    LOG.info("parse_resume: calling %s on %d chars", model, len(resume_text))
    resp = _client().chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": resume_text},
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )
    raw = resp.choices[0].message.content or "{}"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        LOG.warning("parse_resume: bad JSON %r", raw)
        data = {}

    skills = data.get("skills") or []
    if not isinstance(skills, list):
        skills = [str(skills)]
    skills = [str(s).strip() for s in skills if str(s).strip()]

    role = str(data.get("desired_role") or "").strip()
    level = str(data.get("experience_level") or "junior").strip().lower()
    if level not in _VALID_LEVELS:
        level = "junior"

    return {"skills": skills, "desired_role": role, "experience_level": level}


# ---------------------------------------------------------------------------
# Source wrappers — each delegates to the matching sources/* module
# ---------------------------------------------------------------------------

def hh_search_jobs(query: str, area: int = 40, per_page: int = 15) -> list[dict[str, Any]]:
    return _hh.search(query, area=area, per_page=per_page)


def linkedin_search_jobs(query: str, location: str = "Kazakhstan", per_page: int = 15) -> list[dict[str, Any]]:
    return _linkedin.search(query, location=location, per_page=per_page)


def remoteok_search_jobs(query: str, per_page: int = 15) -> list[dict[str, Any]]:
    return _remoteok.search(query, per_page=per_page)


def wwr_search_jobs(query: str, per_page: int = 15) -> list[dict[str, Any]]:
    return _wwr.search(query, per_page=per_page)
