"""
Phase 2 — The Crawler
Visit each discovered URL and extract lead data with better quality controls.
"""

import asyncio
import random
import re
import time
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

try:
    import lxml  # noqa: F401

    BS4_PARSER = "lxml"
except ImportError:
    BS4_PARSER = "html.parser"

from .anti_block import get_browser_args, get_proxy_settings, get_random_ua

EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
PHONE_RE = re.compile(r"(?:\+?\d[\d\s\-().]{7,}\d)")

SOCIAL_PATTERNS = {
    "linkedin": re.compile(r"https?://(?:www\.)?linkedin\.com/(?:in|company)/[^\s\"'<>]+", re.I),
    "twitter": re.compile(r"https?://(?:www\.)?(?:twitter\.com|x\.com)/[^\s\"'<>]+", re.I),
    "instagram": re.compile(r"https?://(?:www\.)?instagram\.com/[^\s\"'<>]+", re.I),
}

CONTACT_PATH_HINTS = (
    "contact",
    "about",
    "team",
    "book",
    "demo",
    "get-in-touch",
)

GENERIC_EMAIL_PREFIXES = {
    "example",
    "yourname",
    "test",
    "noreply",
    "no-reply",
    "donotreply",
}


def _clean_url(raw: str) -> str:
    return raw.rstrip("/").split("?")[0].split("#")[0]


def _extract_name_from_linkedin(url: str) -> str | None:
    m = re.search(r"linkedin\.com/in/([^/?#]+)", url)
    if not m:
        return None
    slug = m.group(1)
    slug = re.sub(r"-[0-9a-f]{5,}$", "", slug)
    parts = slug.split("-")
    return " ".join(p.capitalize() for p in parts if p)


def _normalise_email(email: str) -> str:
    cleaned = email.strip().strip(".,;:()[]<>").lower()
    if cleaned.startswith("mailto:"):
        cleaned = cleaned[len("mailto:") :]
    return cleaned


def _is_valid_business_email(email: str) -> bool:
    if not email or "@" not in email:
        return False
    if any(email.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".svg", ".webp", ".gif")):
        return False

    local, domain = email.split("@", 1)
    if not local or not domain or "." not in domain:
        return False

    if local in GENERIC_EMAIL_PREFIXES:
        return False

    if domain in ("example.com", "domain.com"):
        return False

    return True


def _extract_emails_from_html(soup: BeautifulSoup) -> list[str]:
    candidates = set()

    text = soup.get_text(" ", strip=True)
    for email in EMAIL_RE.findall(text):
        candidates.add(_normalise_email(email))

    for a in soup.select("a[href^='mailto:']"):
        href = a.get("href", "")
        candidates.add(_normalise_email(href))

    return sorted(e for e in candidates if _is_valid_business_email(e))


def _extract_contact_links(soup: BeautifulSoup, page_url: str, limit: int = 2) -> list[str]:
    base_domain = urlparse(page_url).netloc.lower().replace("www.", "")
    links: list[str] = []

    for a in soup.select("a[href]"):
        href = a.get("href", "")
        if not href:
            continue

        lower_href = href.lower()
        anchor_text = a.get_text(" ", strip=True).lower()

        if not any(hint in lower_href or hint in anchor_text for hint in CONTACT_PATH_HINTS):
            continue

        absolute = urljoin(page_url, href)
        parsed = urlparse(absolute)
        domain = parsed.netloc.lower().replace("www.", "")
        if domain != base_domain:
            continue

        cleaned = _clean_url(absolute)
        if cleaned not in links:
            links.append(cleaned)
        if len(links) >= limit:
            break

    return links


def _extract_data(html: str, page_url: str) -> dict:
    soup = BeautifulSoup(html, BS4_PARSER)

    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""

    meta = soup.find("meta", attrs={"name": re.compile(r"description", re.I)})
    description = meta["content"].strip() if meta and meta.get("content") else ""

    h1_tags = [h.get_text(strip=True) for h in soup.find_all("h1")]

    emails = _extract_emails_from_html(soup)
    phones = sorted(set(PHONE_RE.findall(soup.get_text(" ", strip=True))))

    socials: dict[str, str | None] = {"linkedin": None, "twitter": None, "instagram": None}
    all_links_html = str(soup)
    for platform, pattern in SOCIAL_PATTERNS.items():
        matches = pattern.findall(all_links_html)
        if matches:
            socials[platform] = _clean_url(matches[0])

    parsed = urlparse(page_url)
    domain = parsed.netloc.replace("www.", "")
    name = _extract_name_from_linkedin(page_url)

    quality_score = 0
    if title:
        quality_score += 2
    if description:
        quality_score += 2
    if h1_tags:
        quality_score += 2
    if emails:
        quality_score += 4
    if phones:
        quality_score += 2

    return {
        "url": page_url,
        "domain": domain,
        "name": name or "",
        "title": title[:200],
        "description": description[:300],
        "h1": "; ".join(h1_tags[:3]),
        "emails": emails,
        "phones": phones[:5],
        "linkedin": socials["linkedin"] or "",
        "twitter": socials["twitter"] or "",
        "instagram": socials["instagram"] or "",
        "quality_score": quality_score,
        "contact_links": _extract_contact_links(soup, page_url),
    }


def _sync_delay(min_sec: float = 1.0, max_sec: float = 4.0):
    time.sleep(random.uniform(min_sec, max_sec))


def _merge_emails(primary: list[str], extra: list[str]) -> list[str]:
    seen = set(primary)
    merged = list(primary)
    for email in extra:
        if email not in seen:
            seen.add(email)
            merged.append(email)
    return merged


def _crawl_sync(urls: list[str], results: list[dict], log_messages: list[str]) -> None:
    with Stealth().use_sync(sync_playwright()) as pw:
        proxy = get_proxy_settings()
        browser = pw.chromium.launch(headless=True, args=get_browser_args(), proxy=proxy)
        context = browser.new_context(
            user_agent=get_random_ua(),
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
        )
        page = context.new_page()

        for idx, url in enumerate(urls):
            msg = f"Crawling ({idx + 1}/{len(urls)}): {url[:80]}…"
            print(f"[CRAWLER] {msg}")
            log_messages.append(msg)

            try:
                context.set_extra_http_headers({"User-Agent": get_random_ua()})
                page.goto(url, wait_until="domcontentloaded", timeout=25000)
                _sync_delay(1, 3)

                html = page.content()
                data = _extract_data(html, url)

                if not data["emails"] and data["contact_links"]:
                    for link in data["contact_links"]:
                        try:
                            page.goto(link, wait_until="domcontentloaded", timeout=20000)
                            _sync_delay(0.8, 1.8)
                            contact_html = page.content()
                            contact_soup = BeautifulSoup(contact_html, BS4_PARSER)
                            data["emails"] = _merge_emails(data["emails"], _extract_emails_from_html(contact_soup))
                        except Exception:
                            continue

                # Recompute with stronger weight if emails found on follow-up page
                if data["emails"]:
                    data["quality_score"] = max(data["quality_score"], 6)

                results.append(data)

            except Exception as exc:
                msg = f"⚠ Crawl error on {url[:60]}: {exc}"
                print(f"[CRAWLER] {msg}")
                log_messages.append(msg)

            _sync_delay(1, 2.5)

        browser.close()

    msg = f"🕷 Crawl complete — {len(results)} leads extracted."
    print(f"[CRAWLER] {msg}")
    log_messages.append(msg)


async def crawl(urls: list[str], on_progress=None, on_lead=None) -> list[dict]:
    results: list[dict] = []
    log_messages: list[str] = []

    await asyncio.to_thread(_crawl_sync, urls, results, log_messages)

    if on_progress:
        for msg in log_messages:
            await on_progress(msg)

    if on_lead:
        for lead in results:
            await on_lead(lead)

    return results
