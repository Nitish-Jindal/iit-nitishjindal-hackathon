"""
Module B - Strategic Portfolio Stress Testing Engine

Subscribes to event_type and impact_score from the NLP Risk Engine.
When a high-impact event is detected (impact > threshold), triggers
a stress test on the synthetic wholesale banking portfolio.

Design follows EBA / Fed DFAST stress-testing methodology:
  - Scenario-based shocks (not historical simulation for this prototype)
  - Asset-level mark-to-model repricing
  - Aggregated portfolio P&L reporting
  - VaR approximation using shocked portfolio distribution
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path

from loguru import logger

from .portfolio import (
    SyntheticPortfolio, SHOCK_SCENARIOS, AUTO_TRIGGER_THRESHOLD
)
from src.engine.database import save_stress_test


# ---------------------------------------------------------------------------
# Stress Test Engine
# ---------------------------------------------------------------------------

class StressTestEngine:
    """
    Event-driven stress test engine.

    Usage:
        engine = StressTestEngine()
        for signal in signals:
            result = engine.process_signal(signal)
            if result:
                print(result["pnl_impact"])
    """

    def __init__(self, portfolio: Optional[SyntheticPortfolio] = None):
        self.portfolio = portfolio or SyntheticPortfolio()
        self.results: List[Dict[str, Any]] = []
        self.threshold = AUTO_TRIGGER_THRESHOLD

    # ------------------------------------------------------------------
    def process_signal(self, signal: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Evaluate a risk signal and trigger stress test if warranted.

        A test is triggered when:
          impact_score >= threshold  OR
          event_type is in ['Geopolitical', 'Credit Event', 'Macroeconomic']
            AND sentiment_score < -0.3

        Returns stress test result dict if triggered, else None.
        """
        impact     = signal.get("impact_score", 0.0)
        event_type = signal.get("event_type", "Market Sentiment")
        sentiment  = signal.get("sentiment_score", 0.0)
        signal_id  = signal.get("id")

        high_impact_events = {"Geopolitical", "Credit Event", "Macroeconomic"}

        should_trigger = (
            impact >= self.threshold
            or (event_type in high_impact_events and sentiment < -0.3)
        )

        if not should_trigger:
            return None

        logger.info(
            f"[StressTest] Triggered | event={event_type} | "
            f"impact={impact:.1f} | sentiment={sentiment:+.3f}"
        )

        # Choose scenario; augment shocks based on sentiment magnitude
        scenario, shocks = self._select_scenario(event_type, impact, sentiment)
        result = self.portfolio.apply_stress(scenario, custom_shocks=shocks)

        result.update({
            "triggered_at":    datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
            "trigger_event":   event_type,
            "trigger_impact":  impact,
            "trigger_sentiment": sentiment,
            "trigger_ticker":  signal.get("ticker"),
            "trigger_headline": signal.get("headline", ""),
            "signal_id":       signal_id,
        })

        self.results.append(result)

        # Persist to DB
        try:
            save_stress_test({
                "trigger_signal_id": signal_id,
                "scenario":          scenario,
                "pre_value":         result["pre_value"],
                "post_value":        result["post_value"],
                "pnl_impact":        result["pnl_impact"],
                "details":           result,
            })
        except Exception as exc:
            logger.warning(f"Failed to persist stress test: {exc}")

        return result

    def process_signals_batch(
        self, signals: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Process a batch of signals and return all triggered stress test results."""
        results = []
        for sig in signals:
            r = self.process_signal(sig)
            if r is not None:
                results.append(r)
        logger.info(
            f"Batch processing complete: {len(results)}/{len(signals)} signals triggered stress tests."
        )
        return results

    # ------------------------------------------------------------------
    def _select_scenario(
        self,
        event_type: str,
        impact: float,
        sentiment: float,
    ) -> Tuple[str, Optional[Dict[str, float]]]:
        """
        Select the stress scenario and compute dynamic shock amplifiers.

        High-impact signals get amplified shocks (up to 1.5x base).
        """
        # Map event_type to closest available scenario
        scenario = event_type if event_type in SHOCK_SCENARIOS else "Market Sentiment"

        # Amplify shocks for extreme impact
        amplifier = 1.0 + max(0, (impact - self.threshold) / 10.0) * 0.5
        base = SHOCK_SCENARIOS[scenario]

        custom: Dict[str, float] = {}
        for k in ["equity_shock", "rate_shock_bps", "credit_spread_bps", "vol_shock"]:
            if k in base:
                custom[k] = base[k] * amplifier

        return scenario, custom

    # ------------------------------------------------------------------
    def run_scenario(self, scenario_name: str) -> Dict[str, Any]:
        """Manually trigger any named scenario."""
        if scenario_name not in SHOCK_SCENARIOS:
            raise ValueError(
                f"Unknown scenario '{scenario_name}'. "
                f"Available: {list(SHOCK_SCENARIOS.keys())}"
            )
        result = self.portfolio.apply_stress(scenario_name)
        result["triggered_at"] = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        result["trigger_event"] = scenario_name
        result["trigger_impact"] = 10.0
        self.results.append(result)
        return result

    def summary_dataframe(self):
        """Return stress test results as a pandas DataFrame."""
        import pandas as pd
        if not self.results:
            return pd.DataFrame()
        rows = []
        for r in self.results:
            rows.append({
                "timestamp":    r.get("triggered_at", ""),
                "scenario":     r["scenario"],
                "trigger_event": r.get("trigger_event", ""),
                "pre_value":    r["pre_value"],
                "post_value":   r["post_value"],
                "pnl_impact":   r["pnl_impact"],
                "pnl_pct":      r["pnl_pct"],
                "trigger_impact": r.get("trigger_impact", ""),
            })
        return pd.DataFrame(rows)

    def latest_result(self) -> Optional[Dict[str, Any]]:
        return self.results[-1] if self.results else None


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
_engine: Optional[StressTestEngine] = None


def get_stress_engine() -> StressTestEngine:
    global _engine
    if _engine is None:
        _engine = StressTestEngine()
    return _engine


def run_stress_tests(signals: List[Dict[str, Any]]) -> StressTestEngine:
    """Run stress tests against a list of signals and return the engine."""
    engine = get_stress_engine()
    engine.process_signals_batch(signals)
    return engine
