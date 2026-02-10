"""
Phase 4 — The Verifier
Basic SMTP handshake email verification (does NOT send any email).
"""

import asyncio
import socket
from enum import Enum

import dns.resolver
import aiosmtplib


class EmailStatus(str, Enum):
    VALID = "valid"
    INVALID = "invalid"
    CATCH_ALL = "catch-all"
    UNKNOWN = "unknown"


def _get_mx_host(domain: str) -> str | None:
    """Resolve the primary MX record for a domain."""
    try:
        answers = dns.resolver.resolve(domain, "MX")
        # Pick the lowest-priority (highest preference) MX
        records = sorted(answers, key=lambda r: r.preference)
        if records:
            return str(records[0].exchange).rstrip(".")
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.resolver.NoNameservers, Exception):
        return None
    return None


async def verify_email(email: str, timeout: float = 10.0) -> EmailStatus:
    """
    Verify a single email address via SMTP handshake.

    Steps:
    1. DNS MX lookup.
    2. Connect to the MX server.
    3. EHLO → MAIL FROM → RCPT TO.
    4. Interpret response code.

    Returns EmailStatus enum value.
    """
    if not email or "@" not in email:
        return EmailStatus.INVALID

    domain = email.split("@")[1]
    mx_host = _get_mx_host(domain)
    if not mx_host:
        return EmailStatus.UNKNOWN

    try:
        smtp = aiosmtplib.SMTP(
            hostname=mx_host,
            port=25,
            timeout=timeout,
            use_tls=False,
        )
        await smtp.connect()
        await smtp.ehlo("revlane-engine.local")

        # MAIL FROM with a probe address
        await smtp.execute_command(b"MAIL FROM:<verify@revlane-engine.local>")

        # RCPT TO — the key check
        code, message = await smtp.execute_command(
            f"RCPT TO:<{email}>".encode()
        )

        await smtp.quit()

        if 200 <= code < 300:
            return EmailStatus.VALID
        elif code == 550:
            return EmailStatus.INVALID
        elif code == 252:
            return EmailStatus.CATCH_ALL
        else:
            return EmailStatus.UNKNOWN

    except (aiosmtplib.SMTPException, socket.error, asyncio.TimeoutError, OSError):
        return EmailStatus.UNKNOWN


async def verify_emails_batch(
    emails: list[str],
    on_progress=None,
) -> dict[str, str]:
    """
    Verify a batch of emails. Returns {email: status_string}.
    """
    results: dict[str, str] = {}
    total = len(emails)

    for idx, email in enumerate(emails):
        if on_progress:
            await on_progress(f"Verifying email ({idx+1}/{total}): {email}")

        status = await verify_email(email)
        results[email] = status.value

        # Small delay between SMTP checks
        await asyncio.sleep(1.5)

    if on_progress:
        await on_progress(f"✅ Verification complete — {total} emails checked.")
    return results
