"""Fetch web pages and return raw HTML."""

from __future__ import annotations

import httpx

from app.config import REQUEST_TIMEOUT, USER_AGENT


async def fetch_url(url: str) -> str:
    """Fetch a URL and return the HTML body."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    async with httpx.AsyncClient(
        follow_redirects=True, timeout=REQUEST_TIMEOUT
    ) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        return resp.text


async def check_page_exists(url: str) -> bool:
    """Return True if a URL returns 200."""
    try:
        async with httpx.AsyncClient(
            follow_redirects=True, timeout=10
        ) as client:
            resp = await client.head(url, headers={"User-Agent": USER_AGENT})
            return resp.status_code == 200
    except Exception:
        return False


async def probe_site_pages(base_url: str) -> dict[str, bool]:
    """Check for common trust pages on a domain."""
    paths = {
        "about": ["/about", "/about-us", "/our-firm", "/our-team"],
        "contact": ["/contact", "/contact-us"],
        "privacy": ["/privacy", "/privacy-policy"],
        "terms": ["/terms", "/terms-of-service", "/terms-of-use"],
        "editorial": ["/editorial-policy", "/editorial-guidelines"],
        "corrections": ["/corrections", "/corrections-policy"],
        "attorneys": ["/attorneys", "/our-attorneys", "/team", "/lawyers"],
    }
    results: dict[str, bool] = {}
    for key, variants in paths.items():
        found = False
        for path in variants:
            url = base_url.rstrip("/") + path
            if await check_page_exists(url):
                found = True
                break
        results[key] = found
    return results
