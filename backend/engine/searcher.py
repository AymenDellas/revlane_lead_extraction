"""
Phase 1 — The Searcher
Hybrid searcher using:
1. duckduckgo-search library (primary)
2. PowerShell Bridge (fallback) - uses native Windows networking to bypass Python TLS blocks

This module now performs heavier URL quality filtering to reduce junk inputs
for the crawler.
"""

import asyncio
import base64
import random
import re
import subprocess
import time
from urllib.parse import parse_qs, urlparse

from .url_filters import dedup_urls

from bs4 import BeautifulSoup
from duckduckgo_search import DDGS

# ---------------------------------------------------------------------------
# Search query templates
# ---------------------------------------------------------------------------
SEARCH_QUERIES = [
    '"{niche}" "{location}" official website',
    '"{niche}" "{location}" "contact us"',
    '"{niche}" "{location}" "about us"',
    '"{niche}" "{location}" "book a call"',
]


def _build_queries(niche: str, location: str) -> list[str]:
    """Generate search queries."""
    loc = "" if location.lower() in ("remote", "global", "remote/global") else location
    queries = []
    for tpl in SEARCH_QUERIES:
        q = tpl.format(niche=niche, location=loc).replace('""', "").strip()
        q = re.sub(r"\s{2,}", " ", q)
        queries.append(q)
    return queries


def _sync_delay(min_sec: float = 1.0, max_sec: float = 3.0):
    time.sleep(random.uniform(min_sec, max_sec))


# ---------------------------------------------------------------------------
# Method 1: duckduckgo-search library
# ---------------------------------------------------------------------------
def _search_ddg_lib(query: str) -> list[str]:
    """Use the official duckduckgo-search library."""
    urls = []
    try:
        results = DDGS().text(query, max_results=20)
        if results:
            for r in results:
                href = r.get("href", "")
                if href:
                    urls.append(href)
    except Exception as exc:
        print(f"[SEARCHER] DDG Library error: {exc}")
    return urls


# ---------------------------------------------------------------------------
# Method 2: PowerShell Bridge (The "Sledgehammer" Approach)
# ---------------------------------------------------------------------------
def _extract_bing_url(bing_url: str) -> str | None:
    """Extract real URL from Bing redirect (u= parameter is base64 encoded)."""
    try:
        parsed = urlparse(bing_url)
        if "bing.com/ck/a" not in bing_url:
            return bing_url

        qs = parse_qs(parsed.query)
        u_param = qs.get("u", [])
        if not u_param:
            return None

        u_val = u_param[0]
        if u_val.startswith("a1"):
            u_val = u_val[2:]

        missing_padding = len(u_val) % 4
        if missing_padding:
            u_val += "=" * (4 - missing_padding)

        decoded_bytes = base64.urlsafe_b64decode(u_val)
        return decoded_bytes.decode("utf-8")
    except Exception:
        return None


def _search_via_powershell(query: str) -> list[str]:
    """Executes a Bing search via PowerShell's System.Net.WebClient."""
    urls = []
    try:
        search_url = f"https://www.bing.com/search?q={query}"
        ps_command = [
            "powershell",
            "-NoProfile",
            "-Command",
            (
                "$web = New-Object System.Net.WebClient; "
                "$web.Encoding = [System.Text.Encoding]::UTF8; "
                f"$web.DownloadString('{search_url}')"
            ),
        ]

        result = subprocess.run(
            ps_command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
        )

        if result.returncode != 0:
            print(f"[SEARCHER] PowerShell error: {result.stderr[:100]}")
            return urls

        html = result.stdout
        if not html:
            return urls

        soup = BeautifulSoup(html, "html.parser")
        for a in soup.select("li.b_algo h2 a"):
            href = a.get("href")
            if not href:
                continue
            if "bing.com" in href:
                real_url = _extract_bing_url(href)
                if real_url and real_url.startswith("http"):
                    urls.append(real_url)
            elif href.startswith("http"):
                urls.append(href)

    except Exception as exc:
        print(f"[SEARCHER] PowerShell bridge error: {exc}")

    return urls


def _search_sync(niche: str, location: str, log_messages: list[str]) -> list[str]:
    all_urls: list[str] = []
    queries = _build_queries(niche, location)

    for qi, query in enumerate(queries):
        msg = f"🔎 Searching ({qi + 1}/{len(queries)}): {query[:80]}…"
        print(f"[SEARCHER] {msg}")
        log_messages.append(msg)

        found = _search_ddg_lib(query)
        source = "DuckDuckGo"

        if not found:
            print("[SEARCHER] DDG failed/empty, trying PowerShell Bridge (Bing)...")
            found = _search_via_powershell(query)
            source = "Bing (via PowerShell)"

        msg = f"   → {source}: {len(found)} URLs (raw)"
        print(f"[SEARCHER] {msg}")
        log_messages.append(msg)

        all_urls.extend(found)
        _sync_delay(1, 3)

    unique = dedup_urls(all_urls)

    if not unique:
        msg = "⚠ No results found via any method. Trying broad fallback..."
        print(f"[SEARCHER] {msg}")
        log_messages.append(msg)
        fallback_found = _search_via_powershell(f"{niche} {location} official website")
        unique = dedup_urls(fallback_found)
        log_messages.append(f"   → Fallback found: {len(unique)} URLs")

    msg = f"🔍 Search complete — {len(unique)} unique filtered URLs found."
    print(f"[SEARCHER] {msg}")
    log_messages.append(msg)
    return unique


async def search(
    niche: str,
    location: str,
    on_progress=None,
) -> list[str]:
    log_messages: list[str] = []
    urls = await asyncio.to_thread(_search_sync, niche, location, log_messages)
    if on_progress:
        for msg in log_messages:
            await on_progress(msg)
    return urls
