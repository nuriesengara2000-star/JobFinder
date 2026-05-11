"""We Work Remotely RSS feeds (programming categories)."""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from typing import Any

import requests

LOG = logging.getLogger(__name__)

FEEDS = [
    "https://weworkremotely.com/categories/remote-programming-jobs.rss",
    "https://weworkremotely.com/categories/remote-back-end-programming-jobs.rss",
    "https://weworkremotely.com/categories/remote-full-stack-programming-jobs.rss",
    "https://weworkremotely.com/categories/remote-front-end-programming-jobs.rss",
    "https://weworkremotely.com/categories/remote-devops-sysadmin-jobs.rss",
]
HEADERS = {"User-Agent": "JobFinder/1.0 (ilyasnursultancode@gmail.com)"}
_TAG_RE = re.compile(r"<[^>]+>")


def search(query: str, per_page: int = 15) -> list[dict[str, Any]]:
    """Pull all programming-category RSS feeds, filter by `query` substring match."""
    if not query or not query.strip():
        return []

    tokens = [t for t in re.split(r"[\s,;/]+", query.lower()) if len(t) > 2]
    if not tokens:
        tokens = [query.lower().strip()]

    items: list[tuple[str, str, str]] = []
    for feed_url in FEEDS:
        LOG.info("WWR GET %s", feed_url)
        try:
            resp = requests.get(feed_url, headers=HEADERS, timeout=15)
        except requests.RequestException as exc:
            LOG.warning("WWR feed %s failed: %s", feed_url, exc)
            continue
        if resp.status_code != 200:
            continue
        try:
            root = ET.fromstring(resp.content)
        except ET.ParseError:
            continue
        for item in root.iter("item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            desc = (item.findtext("description") or "").strip()
            if title and link:
                items.append((title, link, desc))

    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for title, link, desc in items:
        if link in seen:
            continue
        haystack = (title + " " + desc).lower()
        if not any(t in haystack for t in tokens):
            continue
        seen.add(link)
        company, role = _split_title(title)
        clean_desc = re.sub(r"\s+", " ", _TAG_RE.sub(" ", desc)).strip()[:300] or "—"
        out.append({
            "title": role,
            "company": company,
            "salary": None,
            "requirements": clean_desc,
            "url": link,
            "source": "wwr",
        })
        if len(out) >= per_page:
            break

    LOG.info("WWR matched %d items for query=%r", len(out), query)
    return out


def _split_title(title: str) -> tuple[str, str]:
    """WWR titles look like 'Acme Corp: Senior Backend Engineer' or '... at Acme Corp'."""
    if ":" in title:
        co, _, rest = title.partition(":")
        return co.strip(), rest.strip()
    if " at " in title:
        rest, _, co = title.rpartition(" at ")
        return co.strip(), rest.strip()
    return "—", title
