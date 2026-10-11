"""
FinSight AI - FastAPI Risk Engine API
Exposes risk signals and trigger endpoints.

Endpoints:
  GET  /health              → health check
  GET  /signals             → list recent signals (optional ?ticker=&limit=)
  POST /analyze             → analyze a single text payload on-demand
  POST /ingest              → trigger full ingestion + analysis cycle
  GET  /rebalance/latest    → latest index weights
  GET  /stress-tests        → recent stress test results
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .database import (
    initialize_db, insert_signal, get_recent_signals,
    get_rebalance_history, get_stress_test_history,
)
from .ingestion import ingest_all
from .nlp_analyzer import analyze, analyze_batch

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="FinSight AI — Risk Engine API",
    description="Real-time NLP-driven financial risk signal generator",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    initialize_db()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    text: str = Field(..., min_length=5, description="Text to analyze")
    source: str = Field("API:OnDemand", description="Source identifier")
    ticker: Optional[str] = Field(None, description="Company ticker symbol")


class AnalyzeResponse(BaseModel):
    source: str
    ticker: Optional[str]
    headline: str
    sentiment_score: float
    sentiment_label: str
    event_type: str
    impact_score: float
    confidence: float
    analyzed_at: str
    signal_id: int


class SignalResponse(BaseModel):
    id: int
    timestamp: str
    source: str
    ticker: Optional[str]
    headline: str
    sentiment_score: float
    sentiment_label: str
    event_type: str
    impact_score: float
    confidence: Optional[float]


class IngestResponse(BaseModel):
    status: str
    signals_generated: int
    started_at: str


# ---------------------------------------------------------------------------
# Background ingestion task
# ---------------------------------------------------------------------------

async def _run_ingestion_cycle(rss: bool, social: bool, from_disk: bool):
    """Run a full ingest → analyze → store cycle."""
    loop = asyncio.get_running_loop()
    items = await loop.run_in_executor(
        None,
        lambda: ingest_all(rss=rss, social=social, from_disk=from_disk),
    )
    signals = await loop.run_in_executor(None, lambda: analyze_batch(items, verbose=False))
    for sig in signals:
        insert_signal(sig)
    return len(signals)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health", tags=["Utility"])
def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).replace(tzinfo=None).isoformat()}


@app.get("/signals", response_model=List[SignalResponse], tags=["Signals"])
def list_signals(
    limit: int = Query(50, ge=1, le=500),
    ticker: Optional[str] = Query(None),
):
    """Return recent risk signals, optionally filtered by ticker."""
    return get_recent_signals(limit=limit, ticker=ticker)


@app.post("/analyze", response_model=AnalyzeResponse, tags=["Signals"])
def analyze_text(body: AnalyzeRequest):
    """Analyze a single text payload and persist the resulting signal."""
    item = {
        "source":    body.source,
        "headline":  body.text[:200],
        "full_text": body.text,
        "ticker":    body.ticker,
        "timestamp": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        "uid":       "api-" + str(hash(body.text)),
    }
    signal = analyze(item)
    signal_id = insert_signal(signal)
    return AnalyzeResponse(signal_id=signal_id, **{
        k: signal[k]
        for k in [
            "source", "ticker", "headline",
            "sentiment_score", "sentiment_label",
            "event_type", "impact_score",
            "confidence", "analyzed_at",
        ]
        if k in signal
    })


@app.post("/ingest", response_model=IngestResponse, tags=["Ingestion"])
async def trigger_ingestion(
    background_tasks: BackgroundTasks,
    rss: bool = True,
    social: bool = True,
    from_disk: bool = False,
):
    """
    Trigger a full ingestion + analysis cycle (runs in background).
    Returns immediately with a status message.
    """
    started_at = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    background_tasks.add_task(_run_ingestion_cycle, rss, social, from_disk)
    return IngestResponse(
        status="ingestion_started",
        signals_generated=0,  # actual count logged asynchronously
        started_at=started_at,
    )


@app.get("/rebalance/latest", tags=["Module A"])
def get_latest_rebalance():
    """Return the most recent index rebalance snapshot."""
    history = get_rebalance_history(limit=1)
    if not history:
        raise HTTPException(404, "No rebalance data yet. Run the rebalancer first.")
    import json
    snap = history[0]
    snap["snapshot"] = json.loads(snap["snapshot"])
    return snap


@app.get("/stress-tests", tags=["Module B"])
def get_stress_tests(limit: int = Query(20, ge=1, le=100)):
    """Return recent stress test results."""
    return get_stress_test_history(limit=limit)
