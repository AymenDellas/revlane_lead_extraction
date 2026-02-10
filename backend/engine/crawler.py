"""
Phase 2 — The Crawler
Visit each discovered URL and extract lead data:
title, meta description, H1 tags, social links, and email addresses.
Uses SYNC Playwright API in a thread to avoid Windows asyncio subprocess issues.
"""

import asyncio
import re
import time
import random
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

# Use lxml if available, otherwise fall back to built-in html.parser
try:
    import lxml  # noqa: F401
    BS4_PARSER = "lxml"
except ImportError:
    BS4_PARSER = "html.parser"

from .anti_block import (
    get_browser_args,
    get_proxy_settings,
    get_random_ua,
)

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------
EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")

SOCIAL_PATTERNS = {
    "linkedin": re.compile(r"https?://(?:www\.)?linkedin\.com/(?:in|company)/[^\s\"'<>]+", re.I),
    "twitter": re.compile(r"https?://(?:www\.)?(?:twitter\.com|x\.com)/[^\s\"'<>]+", re.I),
    "instagram": re.compile(r"https?://(?:www\.)?instagram\.com/[^\s\"'<>]+", re.I),
}


def _clean_url(raw: str) -> str:
    """Normalise a URL — remove trailing junk."""
    return raw.rstrip("/").split("?")[0].split("#")[0]


def _extract_name_from_linkedin(url: str) -> str | None:
    """
    Try to extract a human name from a LinkedIn profile URL.
    e.g. linkedin.com/in/john-doe-12345 → John Doe
    """
    m = re.search(r"linkedin\.com/in/([^/?#]+)", url)
    if not m:
        return None
    slug = m.group(1)
    slug = re.sub(r"-[0-9a-f]{5,}$", "", slug)
    parts = slug.split("-")
    return " ".join(p.capitalize() for p in parts if p)


def _extract_data(html: str, page_url: str) -> dict:
    """Parse a single page's HTML and pull structured lead data."""
    soup = BeautifulSoup(html, BS4_PARSER)

    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""

    meta = soup.find("meta", attrs={"name": re.compile(r"description", re.I)})
    description = meta["content"].strip() if meta and meta.get("content") else ""

    h1_tags = [h.get_text(strip=True) for h in soup.find_all("h1")]

    text = soup.get_text(" ", strip=True)
    emails = list(set(EMAIL_RE.findall(text)))
    emails = [e for e in emails if not e.endswith((".png", ".jpg", ".gif", ".svg", ".webp"))]

    socials: dict[str, str | None] = {"linkedin": None, "twitter": None, "instagram": None}
    all_links_html = str(soup)
    for platform, pattern in SOCIAL_PATTERNS.items():
        matches = pattern.findall(all_links_html)
        if matches:
            socials[platform] = _clean_url(matches[0])

    parsed = urlparse(page_url)
    domain = parsed.netloc.replace("www.", "")
    name = _extract_name_from_linkedin(page_url)

    return {
        "url": page_url,
        "domain": domain,
        "name": name or "",
        "title": title[:200],
        "description": description[:300],
        "h1": "; ".join(h1_tags[:3]),
        "emails": emails,
        "linkedin": socials["linkedin"] or "",
        "twitter": socials["twitter"] or "",
        "instagram": socials["instagram"] or "",
    }


def _sync_delay(min_sec: float = 1.0, max_sec: float = 4.0):
    """Blocking sleep with jitter."""
    time.sleep(random.uniform(min_sec, max_sec))


def _crawl_sync(urls: list[str], results: list[dict], log_messages: list[str]) -> None:
    """
    Sync version of the crawl — runs inside a thread.
    Appends leads to results and progress messages to log_messages.
    """
    with Stealth().use_sync(sync_playwright()) as pw:
        proxy = get_proxy_settings()
        browser = pw.chromium.launch(
            headless=True,
            args=get_browser_args(),
            proxy=proxy,
        )
        context = browser.new_context(
            user_agent=get_random_ua(),
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
        )
        page = context.new_page()

        for idx, url in enumerate(urls):
            msg = f"Crawling ({idx+1}/{len(urls)}): {url[:80]}…"
            print(f"[CRAWLER] {msg}")
            log_messages.append(msg)

            try:
                context.set_extra_http_headers({"User-Agent": get_random_ua()})
                page.goto(url, wait_until="domcontentloaded", timeout=25000)
                _sync_delay(1, 4)

                html = page.content()
                data = _extract_data(html, url)
                results.append(data)

            except Exception as exc:
                msg = f"⚠ Crawl error on {url[:60]}: {exc}"
                print(f"[CRAWLER] {msg}")
                log_messages.append(msg)

            _sync_delay(1, 3)

        browser.close()

    msg = f"🕷 Crawl complete — {len(results)} leads extracted."
    print(f"[CRAWLER] {msg}")
    log_messages.append(msg)


async def crawl(
    urls: list[str],
    on_progress=None,
    on_lead=None,
) -> list[dict]:
    """
    Crawl a list of URLs, extract lead data from each.
    Runs Playwright in a sync thread to avoid Windows subprocess issues.
    """
    results: list[dict] = []
    log_messages: list[str] = []

    await asyncio.to_thread(_crawl_sync, urls, results, log_messages)

    # Replay logged messages and leads to SSE
    if on_progress:
        for msg in log_messages:
            await on_progress(msg)

    if on_lead:
        for lead in results:
            await on_lead(lead)

    return results
