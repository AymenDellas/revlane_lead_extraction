from bs4 import BeautifulSoup

from engine.crawler import _extract_emails_from_html
from engine.quality import dedup_and_rank
from engine.url_filters import dedup_urls


def test_search_dedup_filters_social_and_binary_urls():
    urls = [
        "https://www.linkedin.com/company/acme",
        "https://acme.com/contact",
        "https://acme.com/contact?utm_source=test",
        "https://acme.com/brochure.pdf",
    ]

    filtered = dedup_urls(urls)
    assert filtered == ["https://acme.com/contact"]


def test_extract_emails_from_html_prefers_real_business_emails():
    html = """
    <html><body>
      Contact us at Sales@Acme.com.
      <a href='mailto:hello@acme.com'>Email</a>
      <span>example@example.com</span>
      <span>test@domain.com</span>
    </body></html>
    """

    soup = BeautifulSoup(html, "html.parser")
    emails = _extract_emails_from_html(soup)
    assert "sales@acme.com" in emails
    assert "hello@acme.com" in emails
    assert "example@example.com" not in emails


def test_dedup_and_rank_keeps_best_domain_candidate():
    leads = [
        {"domain": "acme.com", "quality_score": 4, "emails": []},
        {"domain": "acme.com", "quality_score": 6, "emails": ["founder@acme.com"]},
        {"domain": "beta.com", "quality_score": 3, "emails": []},
    ]

    ranked = dedup_and_rank(leads)
    assert len(ranked) == 2
    assert ranked[0]["domain"] == "acme.com"
    assert ranked[0]["emails"] == ["founder@acme.com"]
