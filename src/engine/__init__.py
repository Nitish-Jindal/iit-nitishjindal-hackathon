"""FinSight AI - Engine package init."""
from .database import initialize_db, insert_signal, get_recent_signals
from .ingestion import ingest_all
from .nlp_analyzer import analyze, analyze_batch

__all__ = [
    "initialize_db", "insert_signal", "get_recent_signals",
    "ingest_all", "analyze", "analyze_batch",
]
