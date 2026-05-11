"""RemoteOK public JSON feed (no auth, no rate-limit headaches)."""

from __future__ import annotations

import logging
import re
from typing import Any

import requests

LOG = logging.getLogger(__name__)

URL = "https://remoteok.com/api"
HEADERS = {"User-Agent": "JobFinder/1.0 (ilyasnursultancode@gmail.com)"}
_TAG_RE = re.compile(r"<[^>]+>")


def search(query: str, per_page: int = 15) -> list[dict[str, Any]]:
    """Filter RemoteOK's full feed for postings whose title/tags/company match `query`.

    The whole feed is a single ~500-job JSON dump — fetching once and filtering
    client-side is faster than a paginated search would be.
    """
    if not query or not query.strip():
        return []

    LOG.info("RemoteOK GET (filter=%r)", query)
    try:
        resp = requests.get(URL, headers=HEADERS, timeout=20)
    except requests.RequestException as exc:
        LOG.error("RemoteOK request failed: %s", exc)
        return []

    if resp.status_code != 200:
        LOG.error("RemoteOK returned %s", resp.status_code)
        return []

    try:
        feed = resp.json()
    except ValueError:
        LOG.error("RemoteOK returned non-JSON")
        return []

    # First entry is a legal/disclaimer dict; real jobs have "position".
    jobs = [j for j in feed if isinstance(j, dict) and j.get("position")]

    tokens = [t for t in re.split(r"[\s,;/]+", query.lower()) if len(t) > 2]
    if not tokens:
        tokens = [query.lower().strip()]

    out: list[dict[str, Any]] = []
    for j in jobs:
        haystack = " ".join([
            (j.get("position") or "").lower(),
            (j.get("company") or "").lower(),
            " ".join(j.get("tags") or []).lower(),
        ])
        if not any(t in haystack for t in tokens):
            continue
        out.append(_normalize(j))
        if len(out) >= per_page:
            break

    LOG.info("RemoteOK matched %d / %d jobs for query=%r", len(out), len(jobs), query)
    return out


def _normalize(j: dict[str, Any]) -> dict[str, Any]:
    salary = None
    smin, smax = j.get("salary_min"), j.get("salary_max")
    if smin and smax:
        salary = f"${smin:,}-${smax:,}/yr"
    elif smin:
        salary = f"from ${smin:,}/yr"

    desc = _TAG_RE.sub(" ", j.get("description") or "").strip()
    desc = re.sub(r"\s+", " ", desc)[:300] or "—"

    return {
        "title": (j.get("position") or "").strip(),
        "company": (j.get("company") or "").strip(),
        "salary": salary,
        "requirements": desc,
        "url": j.get("url") or j.get("apply_url") or "",
        "source": "remoteok",
    }
