"""Lead quality ranking helpers."""


def dedup_and_rank(leads: list[dict]) -> list[dict]:
    """Keep the best lead per domain, then sort by quality and email confidence."""
    best_by_domain: dict[str, dict] = {}

    for lead in leads:
        domain = lead.get("domain", "")
        current = best_by_domain.get(domain)
        if not current:
            best_by_domain[domain] = lead
            continue

        score = lead.get("quality_score", 0) + (3 if lead.get("emails") else 0)
        current_score = current.get("quality_score", 0) + (3 if current.get("emails") else 0)
        if score > current_score:
            best_by_domain[domain] = lead

    ranked = list(best_by_domain.values())
    ranked.sort(key=lambda l: (bool(l.get("emails")), l.get("quality_score", 0)), reverse=True)
    return ranked
