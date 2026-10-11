"""
FinSight AI - Main Entry Point

Orchestrates the full pipeline:
  1. Initialize DB
  2. Ingest data (RSS + synthetic social)
  3. Run NLP analysis
  4. Run Module A: Tactical Index Rebalancer
  5. Run Module B: Portfolio Stress Testing
  6. Optionally start FastAPI server
  7. Launch Streamlit dashboard

Usage:
  # Full pipeline + dashboard (recommended)
  python main.py

  # API server only
  python main.py --api-only

  # Use offline sample data (no network required)
  python main.py --offline

  # Skip dashboard (pipeline only)
  python main.py --no-dashboard
"""

import argparse
import subprocess
import sys
import os
from pathlib import Path

from loguru import logger

# Ensure src/ is importable
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from src.engine.database import initialize_db, insert_signal
from src.engine.ingestion import ingest_all
from src.engine.nlp_analyzer import analyze_batch
from src.module_a.rebalancer import run_rebalancer
from src.module_b.stress_test import run_stress_tests


def setup_logging():
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>",
        level="INFO",
    )
    logger.add(
        ROOT / "data" / "finsight.log",
        rotation="10 MB",
        retention=3,
        level="DEBUG",
    )


def run_pipeline(offline: bool = False) -> list:
    """Run the full ingestion → analysis pipeline. Returns signal list."""
    logger.info("=" * 60)
    logger.info("  FinSight AI — NLP Risk Engine")
    logger.info("=" * 60)

    # 1. Initialize DB
    initialize_db()

    # 2. Ingest
    logger.info("Step 1/4 — Data Ingestion …")
    items = ingest_all(
        rss=not offline,
        social=True,
        from_disk=offline,
        max_rss=8,
        n_social=40,
    )
    logger.info(f"  → {len(items)} items ingested")

    # 3. NLP Analysis
    logger.info("Step 2/4 — NLP Analysis …")
    signals = analyze_batch(items, verbose=True)
    logger.info(f"  → {len(signals)} signals generated")

    # 4. Persist signals
    logger.info("Step 3/4 — Persisting signals …")
    for sig in signals:
        insert_signal(sig)
    logger.info(f"  → {len(signals)} signals stored in DB")

    return signals


def run_modules(signals: list):
    """Run both downstream modules."""
    # Module A
    logger.info("Step 4a/4 — Module A: Tactical Index Rebalancer …")
    rb = run_rebalancer(signals)
    top = sorted(rb.current_weights.items(), key=lambda x: x[1], reverse=True)[:5]
    logger.info(f"  → Top 5 weights: {top}")

    # Module B
    logger.info("Step 4b/4 — Module B: Portfolio Stress Testing …")
    engine = run_stress_tests(signals)
    if engine.results:
        latest = engine.latest_result()
        logger.info(
            f"  → {len(engine.results)} stress tests triggered | "
            f"Latest: {latest['scenario']} | "
            f"P&L: ${latest['pnl_impact']:+.1f}M ({latest['pnl_pct']:+.2f}%)"
        )
    else:
        logger.info("  → No high-impact events triggered stress tests.")

    logger.info("=" * 60)
    logger.info("  Pipeline complete! Launching dashboard …")
    logger.info("=" * 60)


def launch_dashboard():
    """Launch the Streamlit dashboard."""
    dashboard_path = ROOT / "src" / "dashboard" / "app.py"
    logger.info(f"Launching dashboard: {dashboard_path}")
    try:
        subprocess.run(
            [
                sys.executable, "-m", "streamlit", "run",
                str(dashboard_path),
                "--server.port", "8501",
                "--server.headless", "false",
                "--browser.gatherUsageStats", "false",
            ],
            check=True,
        )
    except KeyboardInterrupt:
        logger.info("Dashboard stopped.")


def launch_api():
    """Launch the FastAPI server."""
    import uvicorn
    uvicorn.run(
        "src.engine.api:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
    )


def main():
    parser = argparse.ArgumentParser(
        description="FinSight AI — Real-Time Financial Risk Intelligence Platform"
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Use offline sample data (no network calls)",
    )
    parser.add_argument(
        "--api-only",
        action="store_true",
        help="Start FastAPI server only (no pipeline or dashboard)",
    )
    parser.add_argument(
        "--no-dashboard",
        action="store_true",
        help="Run pipeline without launching the dashboard",
    )
    parser.add_argument(
        "--skip-pipeline",
        action="store_true",
        help="Skip ingestion/analysis, go straight to dashboard",
    )
    args = parser.parse_args()

    setup_logging()

    if args.api_only:
        logger.info("Starting FastAPI server on http://localhost:8000")
        launch_api()
        return

    if not args.skip_pipeline:
        signals = run_pipeline(offline=args.offline)
        run_modules(signals)
    else:
        initialize_db()

    if not args.no_dashboard:
        launch_dashboard()


if __name__ == "__main__":
    main()
