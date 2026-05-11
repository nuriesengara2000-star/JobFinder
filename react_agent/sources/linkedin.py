"""LinkedIn jobs via the public 'guest' search endpoint.

This is the same endpoint LinkedIn's own marketing widget uses — it returns
a chunk of HTML cards without any auth. Will rate-limit (HTTP 429 / 999) on
heavy use, so OK for personal/low-volume bots only.
"""

from __future__ import annotations

import html as _html
import logging
import re
from typing import Any

import requests

LOG = logging.getLogger(__name__)

URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}

_URL_RE = re.compile(
    r'<a[^>]*class="[^"]*base-card__full-link[^"]*"[^>]*href="([^"]+)"',
    re.DOTALL,
)
_TITLE_RE = re.compile(
    r'<span class="sr-only">\s*([^<]+?)\s*</span>',
    re.DOTALL,
)
_COMPANY_RE = re.compile(
    r'<h4[^>]*class="[^"]*base-search-card__subtitle[^"]*"[^>]*>\s*<a[^>]*>\s*([^<]+?)\s*</a>',
    re.DOTALL,
)
_LOCATION_RE = re.compile(
    r'<span[^>]*class="[^"]*job-search-card__location[^"]*"[^>]*>\s*([^<]+?)\s*</span>',
    re.DOTALL,
)
_DATE_RE = re.compile(
    r'<time[^>]*datetime="([^"]+)"',
    re.DOTALL,
)


def search(query: str, location: str = "Kazakhstan", per_page: int = 15) -> list[dict[str, Any]]:
    """Fetch LinkedIn job cards. ``location`` is a free-text area string."""
    if not query or not query.strip():
        return []
    per_page = max(1, min(int(per_page), 25))

    params = {"keywords": query.strip(), "location": location, "start": 0}
    LOG.info("LinkedIn GET keywords=%r location=%r", query, location)
    try:
        resp = requests.get(URL, params=params, headers=HEADERS, timeout=20)
    except requests.RequestException as exc:
        LOG.error("LinkedIn request failed: %s", exc)
        return []

    if resp.status_code in (429, 999):
        LOG.warning("LinkedIn rate-limited us (HTTP %s)", resp.status_code)
        return []
    if resp.status_code != 200:
        LOG.error("LinkedIn returned %s", resp.status_code)
        return []

    # Each card is a separate <li>. Splitting first makes per-card parsing reliable.
    chunks = resp.text.split("<li")
    out: list[dict[str, Any]] = []
    for chunk in chunks[1:]:
        url_m = _URL_RE.search(chunk)
        title_m = _TITLE_RE.search(chunk)
        if not url_m or not title_m:
            continue
        company_m = _COMPANY_RE.search(chunk)
        location_m = _LOCATION_RE.search(chunk)
        date_m = _DATE_RE.search(chunk)

        url = _html.unescape(url_m.group(1)).split("?", 1)[0]
        title = _html.unescape(title_m.group(1).strip())
        company = _html.unescape(company_m.group(1).strip()) if company_m else "—"
        loc = _html.unescape(location_m.group(1).strip()) if location_m else ""
        posted = date_m.group(1) if date_m else ""

        bits = [b for b in (loc, f"posted {posted}" if posted else "") if b]
        out.append({
            "title": title,
            "company": company,
            "salary": None,  # LinkedIn rarely exposes salary on guest cards
            "requirements": " · ".join(bits) or "—",
            "url": url,
            "source": "linkedin",
        })
        if len(out) >= per_page:
            break

    LOG.info("LinkedIn parsed %d cards for query=%r", len(out), query)
    return out
