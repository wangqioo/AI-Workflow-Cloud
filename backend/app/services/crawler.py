"""Web crawler service.

Ported from v0.7.5 crawl_server.py (port 8092).
Cloud mode: uses httpx for async HTTP, simple HTML stripping.
"""

from __future__ import annotations

import re
from xml.etree import ElementTree

import httpx

_TAG_RE = re.compile(r"<(script|style|noscript)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
_HTML_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\n{3,}")


async def crawl_page(url: str, max_chars: int = 8000) -> dict:
    """Fetch a web page and extract plain text."""
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "AI-Workflow-Crawler/0.8"})
            resp.raise_for_status()
            html = resp.text

        # Extract title
        title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        title = title_match.group(1).strip() if title_match else ""

        # Strip scripts, styles, then tags
        text = _TAG_RE.sub("", html)
        text = _HTML_RE.sub("\n", text)
        text = _WS_RE.sub("\n\n", text).strip()

        if len(text) > max_chars:
            text = text[:max_chars] + "..."

        return {"url": url, "title": title, "text": text, "length": len(text)}
    except Exception as e:
        return {"url": url, "error": str(e)}


async def parse_rss(url: str) -> dict:
    """Parse an RSS/Atom feed."""
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "AI-Workflow-Crawler/0.8"})
            resp.raise_for_status()

        root = ElementTree.fromstring(resp.text)
        items = []

        # RSS 2.0
        for item in root.findall(".//item"):
            items.append({
                "title": _el_text(item, "title"),
                "link": _el_text(item, "link"),
                "description": _el_text(item, "description")[:500],
                "pubDate": _el_text(item, "pubDate"),
            })

        # Atom
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        for entry in root.findall(".//atom:entry", ns):
            link_el = entry.find("atom:link", ns)
            items.append({
                "title": _el_text(entry, "atom:title", ns),
                "link": link_el.get("href", "") if link_el is not None else "",
                "description": _el_text(entry, "atom:summary", ns)[:500],
                "pubDate": _el_text(entry, "atom:updated", ns),
            })

        return {"url": url, "items": items[:50], "count": len(items)}
    except Exception as e:
        return {"url": url, "error": str(e)}


def _el_text(parent, tag, ns=None) -> str:
    el = parent.find(tag, ns) if ns else parent.find(tag)
    return el.text.strip() if el is not None and el.text else ""
