"""
FinSight AI - AI/NLP Risk Engine
Database layer: SQLite storage for risk signals
"""

import sqlite3
import json
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from pathlib import Path
from loguru import logger


DB_PATH = Path(__file__).parent.parent.parent / "data" / "finsight.db"


def get_connection() -> sqlite3.Connection:
    """Get a database connection with row factory."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def initialize_db() -> None:
    """Create all tables if they don't exist."""
    conn = get_connection()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS risk_signals (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp   TEXT NOT NULL,
                source      TEXT NOT NULL,
                ticker      TEXT,
                headline    TEXT NOT NULL,
                full_text   TEXT,
                sentiment_score   REAL NOT NULL,
                sentiment_label   TEXT NOT NULL,
                event_type        TEXT NOT NULL,
                impact_score      REAL NOT NULL,
                confidence        REAL,
                raw_metadata      TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_signals_ticker    ON risk_signals(ticker);
            CREATE INDEX IF NOT EXISTS idx_signals_timestamp ON risk_signals(timestamp);
            CREATE INDEX IF NOT EXISTS idx_signals_event     ON risk_signals(event_type);

            CREATE TABLE IF NOT EXISTS rebalance_snapshots (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp   TEXT NOT NULL,
                snapshot    TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS stress_test_results (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp       TEXT NOT NULL,
                trigger_signal  INTEGER,
                scenario        TEXT NOT NULL,
                pre_value       REAL NOT NULL,
                post_value      REAL NOT NULL,
                pnl_impact      REAL NOT NULL,
                details         TEXT,
                FOREIGN KEY (trigger_signal) REFERENCES risk_signals(id)
            );
        """)
        conn.commit()
        logger.info(f"Database initialized at {DB_PATH}")
    finally:
        conn.close()


def insert_signal(signal: Dict[str, Any]) -> int:
    """Insert a risk signal and return its rowid."""
    conn = get_connection()
    try:
        cur = conn.execute(
            """
            INSERT INTO risk_signals
                (timestamp, source, ticker, headline, full_text,
                 sentiment_score, sentiment_label, event_type,
                 impact_score, confidence, raw_metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                signal.get("timestamp", datetime.now(timezone.utc).replace(tzinfo=None).isoformat()),
                signal["source"],
                signal.get("ticker"),
                signal["headline"],
                signal.get("full_text", ""),
                signal["sentiment_score"],
                signal["sentiment_label"],
                signal["event_type"],
                signal["impact_score"],
                signal.get("confidence"),
                json.dumps(signal.get("raw_metadata", {})),
            ),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_recent_signals(limit: int = 50, ticker: Optional[str] = None) -> List[Dict]:
    """Fetch recent risk signals, optionally filtered by ticker."""
    conn = get_connection()
    try:
        if ticker:
            rows = conn.execute(
                "SELECT * FROM risk_signals WHERE ticker=? ORDER BY timestamp DESC LIMIT ?",
                (ticker.upper(), limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM risk_signals ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def save_rebalance_snapshot(snapshot: Dict[str, Any]) -> None:
    """Persist a rebalance snapshot."""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO rebalance_snapshots (timestamp, snapshot) VALUES (?, ?)",
            (datetime.now(timezone.utc).replace(tzinfo=None).isoformat(), json.dumps(snapshot)),
        )
        conn.commit()
    finally:
        conn.close()


def get_rebalance_history(limit: int = 100) -> List[Dict]:
    """Fetch rebalance history."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM rebalance_snapshots ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def save_stress_test(result: Dict[str, Any]) -> int:
    """Persist a stress test result."""
    conn = get_connection()
    try:
        cur = conn.execute(
            """
            INSERT INTO stress_test_results
                (timestamp, trigger_signal, scenario, pre_value,
                 post_value, pnl_impact, details)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
                result.get("trigger_signal_id"),
                result["scenario"],
                result["pre_value"],
                result["post_value"],
                result["pnl_impact"],
                json.dumps(result.get("details", {})),
            ),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_stress_test_history(limit: int = 50) -> List[Dict]:
    """Fetch stress test result history."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM stress_test_results ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
