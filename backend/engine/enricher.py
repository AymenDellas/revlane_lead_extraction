"""
Phase 3 — The Identity Lab
When no email was found, generate plausible email permutations from a
person's name + company domain.
"""


def _normalise(name_part: str) -> str:
    """Lowercase, strip accents (basic), remove non-alpha."""
    import unicodedata

    nfkd = unicodedata.normalize("NFKD", name_part)
    ascii_only = nfkd.encode("ascii", "ignore").decode("ascii")
    return "".join(c for c in ascii_only if c.isalpha()).lower()


def generate_email_permutations(full_name: str, domain: str) -> list[str]:
    """
    Generate common B2B email variations from a full name and domain.

    Parameters
    ----------
    full_name : str – e.g. "John Doe"
    domain : str – e.g. "acme.com"

    Returns
    -------
    list[str] – e.g. ["john@acme.com", "john.doe@acme.com", ...]
    """
    if not full_name or not domain:
        return []

    parts = full_name.strip().split()
    if len(parts) < 2:
        first = _normalise(parts[0]) if parts else ""
        if first:
            return [f"{first}@{domain}"]
        return []

    first = _normalise(parts[0])
    last = _normalise(parts[-1])

    if not first or not last:
        return []

    fi = first[0]  # first initial
    li = last[0]   # last initial

    permutations = [
        f"{first}@{domain}",
        f"{first}.{last}@{domain}",
        f"{first}{last}@{domain}",
        f"{fi}{last}@{domain}",
        f"{first}{li}@{domain}",
        f"{first}_{last}@{domain}",
        f"{last}@{domain}",
        f"{last}.{first}@{domain}",
        f"{fi}.{last}@{domain}",
        f"{first}-{last}@{domain}",
    ]
    return permutations


def enrich_leads(leads: list[dict]) -> list[dict]:
    """
    For each lead that has no email, fill in generated permutations.
    Modifies leads in place and returns the same list.
    """
    for lead in leads:
        if lead.get("emails"):
            continue
        name = lead.get("name", "")
        domain = lead.get("domain", "")
        if name and domain:
            lead["generated_emails"] = generate_email_permutations(name, domain)
        else:
            lead["generated_emails"] = []
    return leads
