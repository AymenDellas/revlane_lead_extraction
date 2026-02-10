"""URL filtering helpers for search quality."""

import re
from urllib.parse import urlparse

BLOCKED_DOMAINS = {
    "linkedin.com",
    "facebook.com",
    "twitter.com",
    "x.com",
    "instagram.com",
    "youtube.com",
    "tiktok.com",
    "pinterest.com",
    "reddit.com",
    "wikipedia.org",
    "medium.com",
    "github.com",
    "docs.google.com",
    "drive.google.com",
    "webcache.googleusercontent.com",
    "bing.com",
    "duckduckgo.com",
    "yahoo.com",
}

BLOCKED_EXTENSIONS = (
    ".pdf",
    ".doc",
    ".docx",
    ".ppt",
    ".pptx",
    ".xls",
    ".xlsx",
    ".zip",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".webp",
)


def is_probably_lead_url(url: str) -> bool:
    if not url or not url.startswith(("http://", "https://")):
        return False

    parsed = urlparse(url)
    host = parsed.netloc.lower().replace("www.", "")
    if not host:
        return False

    if any(host == blocked or host.endswith(f".{blocked}") for blocked in BLOCKED_DOMAINS):
        return False

    path = parsed.path.lower()
    if path.endswith(BLOCKED_EXTENSIONS):
        return False

    if any(token in path for token in ("/search", "/tag/", "/category/", "/feed", "/wp-json/")):
        return False

    return True


def canonical_url(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.lower().replace("www.", "")
    path = re.sub(r"/+", "/", parsed.path or "/").rstrip("/")
    if not path:
        path = "/"
    return f"{parsed.scheme.lower()}://{host}{path}"


def dedup_urls(urls: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for url in urls:
        if not is_probably_lead_url(url):
            continue
        norm = canonical_url(url)
        if norm not in seen:
            seen.add(norm)
            unique.append(norm)
    return unique
