"""
Pipeline — orchestrates the four engine phases and pushes SSE events.
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone

from .searcher import search
from .crawler import crawl
from .enricher import enrich_leads
from .verifier import verify_email, EmailStatus

# ---------------------------------------------------------------------------
# In-memory store  (swap for Redis / DB in production)
# ---------------------------------------------------------------------------
scans: dict[str, dict] = {}
# scan_id → {status, leads, queue, started_at, finished_at, niche, location}


def create_scan(niche: str, location: str) -> str:
    """Register a new scan and return its ID."""
    scan_id = uuid.uuid4().hex[:12]
    scans[scan_id] = {
        "status": "pending",
        "niche": niche,
        "location": location,
        "leads": [],
        "queue": asyncio.Queue(),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": None,
    }
    return scan_id


def _sse_event(event: str, data: dict) -> dict:
    return {"event": event, "data": json.dumps(data)}


async def run_pipeline(scan_id: str) -> None:
    """
    Run the full 4-phase pipeline for a given scan_id.
    Pushes SSE events into the scan's asyncio.Queue.
    """
    scan = scans[scan_id]
    q: asyncio.Queue = scan["queue"]
    scan["status"] = "running"

    async def push(msg: str):
        print(f"[PIPELINE] {msg}")
        await q.put(_sse_event("progress", {"message": msg}))

    async def push_lead(lead: dict):
        await q.put(_sse_event("lead", lead))

    try:
        # ------ Phase 1: Search ------ #
        print(f"[PIPELINE] === Phase 1: The Searcher ===")
        await q.put(_sse_event("phase", {"phase": 1, "name": "The Searcher", "status": "running"}))
        urls = await search(
            niche=scan["niche"],
            location=scan["location"],
            on_progress=push,
        )
        await q.put(_sse_event("phase", {"phase": 1, "name": "The Searcher", "status": "done", "count": len(urls)}))

        if not urls:
            await push("No URLs found — try adjusting your niche or location.")
            scan["status"] = "done"
            scan["finished_at"] = datetime.now(timezone.utc).isoformat()
            await q.put(_sse_event("done", {"total": 0}))
            return

        # ------ Phase 2: Crawl ------ #
        print(f"[PIPELINE] === Phase 2: The Crawler ({len(urls)} URLs) ===")
        await q.put(_sse_event("phase", {"phase": 2, "name": "The Crawler", "status": "running"}))
        leads = await crawl(urls, on_progress=push, on_lead=push_lead)
        await q.put(_sse_event("phase", {"phase": 2, "name": "The Crawler", "status": "done", "count": len(leads)}))

        # ------ Phase 3: Enrich ------ #
        print(f"[PIPELINE] === Phase 3: The Identity Lab ===")
        await q.put(_sse_event("phase", {"phase": 3, "name": "The Identity Lab", "status": "running"}))
        leads = enrich_leads(leads)
        await push(f"🧬 Enriched {sum(1 for l in leads if l.get('generated_emails'))} leads with email permutations.")
        await q.put(_sse_event("phase", {"phase": 3, "name": "The Identity Lab", "status": "done"}))

        # ------ Phase 4: Verify ------ #
        print(f"[PIPELINE] === Phase 4: The Verifier ===")
        await q.put(_sse_event("phase", {"phase": 4, "name": "The Verifier", "status": "running"}))
        for lead in leads:
            all_emails = lead.get("emails", []) + lead.get("generated_emails", [])
            best_status = EmailStatus.UNKNOWN.value
            best_email = ""
            for email in all_emails[:5]:  # cap at 5 to be polite
                try:
                    status = await verify_email(email, timeout=8.0)
                    await push(f"📧 {email} → {status.value}")
                    if status == EmailStatus.VALID:
                        best_status = status.value
                        best_email = email
                        break
                    elif status == EmailStatus.CATCH_ALL and best_status != EmailStatus.VALID.value:
                        best_status = status.value
                        best_email = email
                except Exception:
                    pass

            lead["verified_email"] = best_email or (lead["emails"][0] if lead.get("emails") else "")
            lead["email_status"] = best_status

            # Push updated lead
            await push_lead(lead)

        await q.put(_sse_event("phase", {"phase": 4, "name": "The Verifier", "status": "done"}))

        # ------ Done ------ #
        scan["leads"] = leads
        scan["status"] = "done"
        scan["finished_at"] = datetime.now(timezone.utc).isoformat()
        await q.put(_sse_event("done", {"total": len(leads)}))

    except Exception as exc:
        print(f"[PIPELINE] ❌ ERROR: {exc}")
        scan["status"] = "error"
        await q.put(_sse_event("error", {"message": str(exc)}))
