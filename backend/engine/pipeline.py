"""
Pipeline — orchestrates the four engine phases and pushes SSE events.
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone

from .crawler import crawl
from .enricher import enrich_leads
from .searcher import search
from .quality import dedup_and_rank
from .verifier import EmailStatus, verify_email

scans: dict[str, dict] = {}


def create_scan(niche: str, location: str) -> str:
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
    scan = scans[scan_id]
    q: asyncio.Queue = scan["queue"]
    scan["status"] = "running"

    async def push(msg: str):
        print(f"[PIPELINE] {msg}")
        await q.put(_sse_event("progress", {"message": msg}))

    async def push_lead(lead: dict):
        await q.put(_sse_event("lead", lead))

    try:
        await q.put(_sse_event("phase", {"phase": 1, "name": "The Searcher", "status": "running"}))
        urls = await search(niche=scan["niche"], location=scan["location"], on_progress=push)
        await q.put(_sse_event("phase", {"phase": 1, "name": "The Searcher", "status": "done", "count": len(urls)}))

        if not urls:
            await push("No URLs found — try adjusting your niche or location.")
            scan["status"] = "done"
            scan["finished_at"] = datetime.now(timezone.utc).isoformat()
            await q.put(_sse_event("done", {"total": 0}))
            return

        await q.put(_sse_event("phase", {"phase": 2, "name": "The Crawler", "status": "running"}))
        leads = await crawl(urls, on_progress=push, on_lead=push_lead)
        leads = dedup_and_rank(leads)
        await push(f"🧹 Quality filter kept {len(leads)} high-confidence unique-domain leads.")
        await q.put(_sse_event("phase", {"phase": 2, "name": "The Crawler", "status": "done", "count": len(leads)}))

        await q.put(_sse_event("phase", {"phase": 3, "name": "The Identity Lab", "status": "running"}))
        leads = enrich_leads(leads)
        await push(f"🧬 Enriched {sum(1 for l in leads if l.get('generated_emails'))} leads with email permutations.")
        await q.put(_sse_event("phase", {"phase": 3, "name": "The Identity Lab", "status": "done"}))

        await q.put(_sse_event("phase", {"phase": 4, "name": "The Verifier", "status": "running"}))
        for lead in leads:
            all_emails = lead.get("emails", []) + lead.get("generated_emails", [])
            best_status = EmailStatus.UNKNOWN.value
            best_email = ""
            for email in all_emails[:5]:
                try:
                    status = await verify_email(email, timeout=8.0)
                    await push(f"📧 {email} → {status.value}")
                    if status == EmailStatus.VALID:
                        best_status = status.value
                        best_email = email
                        break
                    if status == EmailStatus.CATCH_ALL and best_status != EmailStatus.VALID.value:
                        best_status = status.value
                        best_email = email
                except Exception:
                    continue

            lead["verified_email"] = best_email or (lead["emails"][0] if lead.get("emails") else "")
            lead["email_status"] = best_status
            await push_lead(lead)

        await q.put(_sse_event("phase", {"phase": 4, "name": "The Verifier", "status": "done"}))

        scan["leads"] = leads
        scan["status"] = "done"
        scan["finished_at"] = datetime.now(timezone.utc).isoformat()
        await q.put(_sse_event("done", {"total": len(leads)}))

    except Exception as exc:
        print(f"[PIPELINE] ❌ ERROR: {exc}")
        scan["status"] = "error"
        await q.put(_sse_event("error", {"message": str(exc)}))
