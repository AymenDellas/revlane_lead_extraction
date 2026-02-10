"""
Revlane Engine — FastAPI entry point.
"""

import asyncio
import io
import json
import sys

# Fix for Playwright subprocess spawning on Windows
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from engine.pipeline import create_scan, run_pipeline, scans

load_dotenv()

app = FastAPI(
    title="Revlane Engine",
    version="1.0.0",
    description="B2B Lead Scraping & Enrichment API",
)

# CORS — allow the React dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ----- Schemas ----- #
class ScanRequest(BaseModel):
    niche: str
    location: str = "Remote/Global"


class ScanResponse(BaseModel):
    scan_id: str
    message: str


# ----- Routes ----- #
@app.get("/")
async def root():
    return {"app": "Revlane Engine", "status": "online"}


@app.post("/api/scan", response_model=ScanResponse)
async def start_scan(req: ScanRequest):
    """Launch a new scan pipeline."""
    scan_id = create_scan(req.niche, req.location)
    # Fire and forget the pipeline
    asyncio.create_task(run_pipeline(scan_id))
    return ScanResponse(scan_id=scan_id, message="Scan started")


@app.get("/api/scan/{scan_id}/stream")
async def scan_stream(scan_id: str):
    """SSE stream of scan progress and lead data."""
    if scan_id not in scans:
        raise HTTPException(404, "Scan not found")

    scan = scans[scan_id]
    q: asyncio.Queue = scan["queue"]

    async def event_generator():
        while True:
            try:
                event = await asyncio.wait_for(q.get(), timeout=120)
                yield event
                # Stop streaming on terminal events
                parsed = json.loads(event["data"])
                if event["event"] in ("done", "error"):
                    break
            except asyncio.TimeoutError:
                # Keep-alive
                yield {"event": "ping", "data": "{}"}

    return EventSourceResponse(event_generator())


@app.get("/api/scan/{scan_id}/results")
async def scan_results(scan_id: str):
    """Return all leads for a completed scan."""
    if scan_id not in scans:
        raise HTTPException(404, "Scan not found")
    scan = scans[scan_id]
    return {
        "scan_id": scan_id,
        "status": scan["status"],
        "total": len(scan["leads"]),
        "leads": scan["leads"],
    }


@app.get("/api/scan/{scan_id}/export")
async def export_scan(scan_id: str, format: str = "csv"):
    """Export leads as CSV or JSON file download."""
    if scan_id not in scans:
        raise HTTPException(404, "Scan not found")
    scan = scans[scan_id]
    leads = scan["leads"]
    if not leads:
        raise HTTPException(400, "No leads to export")

    # Flatten for export
    rows = []
    for lead in leads:
        rows.append({
            "Name": lead.get("name", ""),
            "Title": lead.get("title", ""),
            "Description": lead.get("description", ""),
            "Domain": lead.get("domain", ""),
            "URL": lead.get("url", ""),
            "Email": lead.get("verified_email", ""),
            "Email Status": lead.get("email_status", ""),
            "LinkedIn": lead.get("linkedin", ""),
            "Twitter": lead.get("twitter", ""),
            "Instagram": lead.get("instagram", ""),
            "H1": lead.get("h1", ""),
        })

    df = pd.DataFrame(rows)

    if format.lower() == "json":
        content = df.to_json(orient="records", indent=2)
        return StreamingResponse(
            io.BytesIO(content.encode()),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=revlane_{scan_id}.json"},
        )

    # Default CSV
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return StreamingResponse(
        io.BytesIO(buf.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=revlane_{scan_id}.csv"},
    )
