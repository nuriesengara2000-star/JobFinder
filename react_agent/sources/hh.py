"""HeadHunter source: official API first, public-search HTML fallback.

The HTML fallback is needed because hh.ru frequently 403's anonymous
``/vacancies`` calls from residential IPs; the public ``hh.kz/search/vacancy``
page embeds the same data in an HH-Lux-InitialState JSON island.
"""

from __future__ import annotations

import html as _html
import json
import logging
import os
import re
from typing import Any

import requests

LOG = logging.getLogger(__name__)

API_URL = "https://api.hh.ru/vacancies"
HTML_URL = "https://hh.kz/search/vacancy"

DEFAULT_USER_AGENT = "JobFinder/1.0 (ilyasnursultancode@gmail.com)"
_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}
_INITIAL_STATE_ID = 'id="HH-Lux-InitialState"'
_TAG_RE = re.compile(r"<[^>]+>")


def search(query: str, area: int = 40, per_page: int = 15) -> list[dict[str, Any]]:
    """Public entry: tries the API, falls back to the HTML data island on 403."""
    if not query or not query.strip():
        return []
    per_page = max(1, min(int(per_page), 50))

    api = _via_api(query, area, per_page)
    if api is not None:
        return api
    LOG.info("HH: falling back to HTML scrape")
    return _via_html(query, area, per_page)


def _via_api(query: str, area: int, per_page: int) -> list[dict[str, Any]] | None:
    """Returns list on success, None when the caller should fall back, [] on hard error."""
    params = {
        "text": query.strip(),
        "area": int(area),
        "per_page": per_page,
        "order_by": "publication_time",
    }
    headers = {
        "User-Agent": os.environ.get("HH_USER_AGENT", DEFAULT_USER_AGENT),
        "Accept": "application/json",
    }
    token = os.environ.get("HH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    LOG.info("HH API GET text=%r area=%s per_page=%s", query, area, per_page)
    try:
        resp = requests.get(API_URL, params=params, headers=headers, timeout=20)
    except requests.RequestException as exc:
        LOG.error("HH API request failed: %s", exc)
        return None

    if resp.status_code in (401, 403):
        LOG.warning("HH API returned %s — fallback", resp.status_code)
        return None
    if resp.status_code != 200:
        LOG.error("HH API returned %s: %s", resp.status_code, resp.text[:200])
        return []

    try:
        items = (resp.json().get("items") or [])
    except ValueError:
        return []

    out: list[dict[str, Any]] = []
    for item in items:
        snip = item.get("snippet") or {}
        req = (snip.get("requirement") or "").strip()
        resp_text = (snip.get("responsibility") or "").strip()
        desc = " ".join(p for p in (req, resp_text) if p) or "—"
        out.append({
            "title": (item.get("name") or "").strip(),
            "company": ((item.get("employer") or {}).get("name") or "").strip(),
            "salary": _format_api_salary(item.get("salary")),
            "requirements": desc,
            "url": item.get("alternate_url") or "",
            "source": "hh",
        })
    return out


def _via_html(query: str, area: int, per_page: int) -> list[dict[str, Any]]:
    params = {
        "text": query.strip(),
        "area": int(area),
        "items_on_page": per_page,
        "enable_snippets": "true",
        "order_by": "publication_time",
    }
    LOG.info("HH HTML GET text=%r area=%s per_page=%s", query, area, per_page)
    try:
        resp = requests.get(HTML_URL, params=params, headers=_BROWSER_HEADERS, timeout=20)
    except requests.RequestException as exc:
        LOG.error("HH HTML request failed: %s", exc)
        return []
    if resp.status_code != 200:
        LOG.error("HH HTML returned %s", resp.status_code)
        return []

    page = resp.text
    start = page.find(_INITIAL_STATE_ID)
    if start < 0:
        LOG.error("HH HTML: HH-Lux-InitialState template not found")
        return []
    open_close = page.find(">", start)
    end = page.find("</template>", open_close)
    raw = _html.unescape(page[open_close + 1 : end])
    try:
        state = json.loads(raw)
    except json.JSONDecodeError as exc:
        LOG.error("HH HTML: cannot parse embedded JSON: %s", exc)
        return []

    vacancies = ((state.get("vacancySearchResult") or {}).get("vacancies")) or []
    LOG.info("HH HTML returned %d items for query=%r", len(vacancies), query)

    out: list[dict[str, Any]] = []
    for v in vacancies[:per_page]:
        company = v.get("company") or {}
        name = (company.get("visibleName") or company.get("name") or "").strip()
        snip = v.get("snippet") or {}
        req = _strip_html(snip.get("req") or snip.get("requirement") or "")
        resp_text = _strip_html(snip.get("resp") or snip.get("responsibility") or "")
        desc = " ".join(p for p in (req, resp_text) if p) or "—"
        link = ((v.get("links") or {}).get("desktop")) or (
            f"https://hh.kz/vacancy/{v.get('vacancyId')}" if v.get("vacancyId") else ""
        )
        out.append({
            "title": (v.get("name") or "").strip(),
            "company": name,
            "salary": _format_compensation(v.get("compensation")),
            "requirements": desc,
            "url": link,
            "source": "hh",
        })
    return out


def _strip_html(text: str) -> str:
    return _TAG_RE.sub("", text or "").strip()


def _format_api_salary(salary: dict[str, Any] | None) -> str | None:
    if not salary:
        return None
    frm, to, cur = salary.get("from"), salary.get("to"), (salary.get("currency") or "").strip()
    if frm and to:
        return f"{frm}-{to} {cur}".strip()
    if frm:
        return f"from {frm} {cur}".strip()
    if to:
        return f"up to {to} {cur}".strip()
    return None


def _format_compensation(comp: dict[str, Any] | None) -> str | None:
    if not comp or "noCompensation" in comp:
        return None
    cur = (comp.get("currencyCode") or comp.get("currency") or "").strip()
    frm, to = comp.get("from"), comp.get("to")
    if frm and to:
        return f"{frm}-{to} {cur}".strip()
    if frm:
        return f"from {frm} {cur}".strip()
    if to:
        return f"up to {to} {cur}".strip()
    return None
