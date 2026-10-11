"""
Module A - Tactical Index Rebalancer

Subscribes to NLP Risk Engine sentiment signals and dynamically adjusts
stock weights in the mock S&P 100 index.

Algorithm:
  1. For each incoming signal with a ticker in the index:
       Δw_i = α * sentiment_score_i * current_weight_i
       new_weight_i = current_weight_i + Δw_i
  2. Clip all weights to [min_weight, max_weight]
  3. Re-normalize so all weights sum to 1.0
  4. Persist snapshot to database

The approach is inspired by momentum-based factor tilting used in
quantitative portfolio management (e.g., BlackRock's Aladdin, AQR).
"""

from __future__ import annotations

import json
import copy
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any
from collections import deque

from loguru import logger

from .index_config import MOCK_INDEX, REBALANCE_CONFIG


# ---------------------------------------------------------------------------
# Weight state
# ---------------------------------------------------------------------------

class IndexRebalancer:
    """
    Stateful index rebalancer driven by NLP sentiment signals.

    Usage:
        rb = IndexRebalancer()
        for signal in signals:
            rb.apply_signal(signal)
        weights = rb.current_weights
    """

    def __init__(self):
        self.weights: Dict[str, float] = {
            ticker: meta["init_weight"]
            for ticker, meta in MOCK_INDEX.items()
        }
        self.cfg = REBALANCE_CONFIG
        self.history: List[Dict[str, Any]] = []
        self._signal_buffer: deque = deque(maxlen=200)

    # ------------------------------------------------------------------
    def apply_signal(self, signal: Dict[str, Any]) -> Optional[Dict[str, float]]:
        """
        Apply a single risk signal to update index weights.

        Returns updated weights dict if a ticker was affected, else None.
        """
        ticker = signal.get("ticker")
        if ticker not in self.weights:
            return None

        sentiment = signal.get("sentiment_score", 0.0)
        impact    = signal.get("impact_score", 5.0)

        # Scale adjustment by impact (higher-impact events move weights more)
        alpha     = self.cfg["sentiment_alpha"] * (impact / 10.0)
        delta     = alpha * sentiment * self.weights[ticker]

        self.weights[ticker] = max(
            self.cfg["min_weight"],
            min(self.cfg["max_weight"], self.weights[ticker] + delta),
        )

        # Re-normalize
        self._normalize()

        # Record
        snapshot = self._snapshot(signal)
        self.history.append(snapshot)
        self._signal_buffer.append(signal)

        logger.info(
            f"[Rebalancer] {ticker} | sentiment={sentiment:+.3f} | "
            f"new_weight={self.weights[ticker]:.4f} | impact={impact:.1f}"
        )
        return dict(self.weights)

    def apply_signals_batch(
        self, signals: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Apply a batch of signals, returning all snapshots generated."""
        snapshots = []
        for sig in signals:
            result = self.apply_signal(sig)
            if result is not None:
                snapshots.append(self.history[-1])
        return snapshots

    # ------------------------------------------------------------------
    def _normalize(self) -> None:
        """Re-normalize weights to sum to 1.0."""
        total = sum(self.weights.values())
        if total > 0:
            self.weights = {k: v / total for k, v in self.weights.items()}

    def _snapshot(self, trigger_signal: Dict[str, Any]) -> Dict[str, Any]:
        """Create a serializable snapshot of current state."""
        return {
            "timestamp":       datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
            "trigger_ticker":  trigger_signal.get("ticker"),
            "trigger_sentiment": trigger_signal.get("sentiment_score"),
            "trigger_event":   trigger_signal.get("event_type"),
            "trigger_impact":  trigger_signal.get("impact_score"),
            "weights":         dict(self.weights),
            "top5":            self._top_n(5),
            "bottom5":         self._bottom_n(5),
        }

    def _top_n(self, n: int) -> Dict[str, float]:
        return dict(
            sorted(self.weights.items(), key=lambda x: x[1], reverse=True)[:n]
        )

    def _bottom_n(self, n: int) -> Dict[str, float]:
        return dict(
            sorted(self.weights.items(), key=lambda x: x[1])[:n]
        )

    @property
    def current_weights(self) -> Dict[str, float]:
        return dict(self.weights)

    @property
    def sector_weights(self) -> Dict[str, float]:
        """Aggregate weights by sector."""
        sectors: Dict[str, float] = {}
        for ticker, weight in self.weights.items():
            sector = MOCK_INDEX[ticker]["sector"]
            sectors[sector] = sectors.get(sector, 0.0) + weight
        return sectors

    def weight_dataframe(self):
        """Return a pandas DataFrame of current weights with metadata."""
        import pandas as pd
        rows = []
        for ticker, weight in self.weights.items():
            meta = MOCK_INDEX[ticker]
            rows.append({
                "Ticker": ticker,
                "Name":   meta["name"],
                "Sector": meta["sector"],
                "Weight": weight,
                "InitWeight": meta["init_weight"],
                "WeightChange": weight - meta["init_weight"],
            })
        return pd.DataFrame(rows).sort_values("Weight", ascending=False)

    def history_dataframe(self):
        """Return a pandas DataFrame of the rebalance history."""
        import pandas as pd
        if not self.history:
            return pd.DataFrame()
        rows = []
        for snap in self.history:
            for ticker, w in snap["weights"].items():
                rows.append({
                    "timestamp":  snap["timestamp"],
                    "ticker":     ticker,
                    "weight":     w,
                    "trigger":    snap["trigger_ticker"],
                    "sentiment":  snap["trigger_sentiment"],
                    "event_type": snap["trigger_event"],
                })
        return pd.DataFrame(rows)

    def reset(self) -> None:
        """Reset to initial weights."""
        self.weights = {
            ticker: meta["init_weight"]
            for ticker, meta in MOCK_INDEX.items()
        }
        self.history.clear()
        logger.info("Rebalancer reset to initial weights.")


# ---------------------------------------------------------------------------
# Module-level singleton for use by dashboard
# ---------------------------------------------------------------------------
_rebalancer: Optional[IndexRebalancer] = None


def get_rebalancer() -> IndexRebalancer:
    global _rebalancer
    if _rebalancer is None:
        _rebalancer = IndexRebalancer()
    return _rebalancer


def run_rebalancer(signals: List[Dict[str, Any]]) -> IndexRebalancer:
    """
    Run the rebalancer against a list of signals and return it.
    Persists snapshots to DB.
    """
    from src.engine.database import save_rebalance_snapshot
    rb = get_rebalancer()
    relevant = [s for s in signals if s.get("ticker") in MOCK_INDEX]
    logger.info(f"Rebalancing with {len(relevant)} relevant signals …")
    for sig in relevant:
        rb.apply_signal(sig)
        if rb.history:
            save_rebalance_snapshot(rb.history[-1])
    return rb
