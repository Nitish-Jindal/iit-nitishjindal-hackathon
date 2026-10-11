"""
Module B - Portfolio Definition & Asset Pricing
Defines a synthetic wholesale banking portfolio comprising loans, bonds, and derivatives.
Implements mark-to-model pricing for stress test simulations.

Asset types:
  - Corporate Loan    : priced via credit spread + base rate
  - Government Bond   : priced via duration-based rate sensitivity
  - Corporate Bond    : duration + credit spread sensitivity
  - Interest Rate Swap: DV01-based sensitivity to rate shifts
  - Equity Derivative : delta + vega exposure to equity prices
  - CDS               : protection leg value vs. credit spread
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict

import pandas as pd
import numpy as np


# ---------------------------------------------------------------------------
# Asset dataclasses
# ---------------------------------------------------------------------------

@dataclass
class Asset:
    id: str
    name: str
    asset_type: str          # loan | gov_bond | corp_bond | irs | equity_deriv | cds
    notional: float          # USD millions
    base_value: float        # current mark-to-model value (USD millions)
    ticker: Optional[str] = None
    rating: str = "BBB"      # credit rating
    maturity_years: float = 5.0
    duration: float = 4.5    # modified duration for bonds
    coupon: float = 0.045    # annual coupon / spread
    delta: float = 0.0       # equity delta for derivatives
    vega: float = 0.0        # equity vega for derivatives
    dv01: float = 0.0        # dollar value per 1bp rate move (IRS)
    spread_bps: float = 0.0  # credit spread in basis points
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Stress shock library
# ---------------------------------------------------------------------------

SHOCK_SCENARIOS: Dict[str, Dict[str, float]] = {
    "Geopolitical": {
        "equity_shock":       -0.12,   # -12% equity prices
        "rate_shock_bps":      50,     # +50bps rates
        "credit_spread_bps":   75,     # +75bps credit spreads
        "vol_shock":           0.08,   # +8 vol points
        "description": "Geopolitical escalation: equity sell-off, rate/credit spike",
    },
    "Macroeconomic": {
        "equity_shock":       -0.08,
        "rate_shock_bps":      100,
        "credit_spread_bps":   50,
        "vol_shock":           0.05,
        "description": "Macro downturn: rate hike cycle, moderate credit stress",
    },
    "Credit Event": {
        "equity_shock":       -0.06,
        "rate_shock_bps":      25,
        "credit_spread_bps":   200,
        "vol_shock":           0.06,
        "description": "Credit market stress: significant spread widening",
    },
    "Merger & Acquisition": {
        "equity_shock":        0.05,
        "rate_shock_bps":      0,
        "credit_spread_bps":   -20,
        "vol_shock":           0.03,
        "description": "M&A activity: modest equity uptick, tighter spreads",
    },
    "Regulatory & Legal": {
        "equity_shock":       -0.05,
        "rate_shock_bps":      0,
        "credit_spread_bps":   40,
        "vol_shock":           0.04,
        "description": "Regulatory shock: sector re-pricing, mild spread widening",
    },
    "Market Sentiment": {
        "equity_shock":       -0.04,
        "rate_shock_bps":      15,
        "credit_spread_bps":   25,
        "vol_shock":           0.03,
        "description": "Negative sentiment shock: mild broad-based repricing",
    },
    # ── Extreme scenario (always available)
    "Severe Stress": {
        "equity_shock":       -0.25,
        "rate_shock_bps":      200,
        "credit_spread_bps":   400,
        "vol_shock":           0.20,
        "description": "Severe stress (2008-like): extreme equity crash & credit crunch",
    },
}

# Impact score threshold to trigger a stress test automatically
AUTO_TRIGGER_THRESHOLD = 7.0


# ---------------------------------------------------------------------------
# Portfolio class
# ---------------------------------------------------------------------------

class SyntheticPortfolio:
    """
    Synthetic wholesale banking portfolio with mark-to-model pricing.

    Stress testing methodology follows Basel III / EBA stress-test frameworks:
    - Rate sensitivity via DV01 and duration
    - Credit sensitivity via spread duration
    - Equity sensitivity via delta/vega
    """

    def __init__(self, assets: Optional[List[Asset]] = None):
        self.assets: List[Asset] = assets or _build_default_portfolio()
        self._validate()

    def _validate(self):
        assert all(isinstance(a, Asset) for a in self.assets), \
            "All items must be Asset instances"

    @property
    def total_value(self) -> float:
        """Total portfolio NAV (USD millions)."""
        return sum(a.base_value for a in self.assets)

    @property
    def by_type(self) -> Dict[str, float]:
        """Value breakdown by asset type."""
        result: Dict[str, float] = {}
        for a in self.assets:
            result[a.asset_type] = result.get(a.asset_type, 0.0) + a.base_value
        return result

    @property
    def by_rating(self) -> Dict[str, float]:
        result: Dict[str, float] = {}
        for a in self.assets:
            result[a.rating] = result.get(a.rating, 0.0) + a.base_value
        return result

    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame([a.to_dict() for a in self.assets])

    def apply_stress(
        self,
        scenario_name: str,
        custom_shocks: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """
        Apply a stress scenario to the portfolio.

        Args:
            scenario_name:  Name of the scenario from SHOCK_SCENARIOS.
            custom_shocks:  Override/augment shocks dict.

        Returns:
            Dict with pre/post values, PnL, and per-asset breakdown.
        """
        shocks = dict(SHOCK_SCENARIOS.get(scenario_name, SHOCK_SCENARIOS["Market Sentiment"]))
        if custom_shocks:
            shocks.update(custom_shocks)

        pre_value  = self.total_value
        asset_results = []

        for asset in self.assets:
            stressed = _price_asset_stressed(asset, shocks)
            asset_results.append({
                "id":          asset.id,
                "name":        asset.name,
                "type":        asset.asset_type,
                "rating":      asset.rating,
                "pre_value":   asset.base_value,
                "post_value":  stressed,
                "pnl":         stressed - asset.base_value,
                "pnl_pct":     (stressed - asset.base_value) / asset.base_value * 100
                               if asset.base_value != 0 else 0.0,
            })

        post_value = sum(r["post_value"] for r in asset_results)
        pnl        = post_value - pre_value

        return {
            "scenario":         scenario_name,
            "description":      shocks.get("description", ""),
            "shocks_applied":   {k: v for k, v in shocks.items() if k != "description"},
            "pre_value":        round(pre_value,  2),
            "post_value":       round(post_value, 2),
            "pnl_impact":       round(pnl, 2),
            "pnl_pct":          round(pnl / pre_value * 100, 3) if pre_value else 0.0,
            "asset_breakdown":  asset_results,
            "by_type_pre":      {k: round(v, 2) for k, v in self.by_type.items()},
            "by_type_post":     _post_by_type(asset_results),
        }


# ---------------------------------------------------------------------------
# Asset pricing under stress
# ---------------------------------------------------------------------------

def _price_asset_stressed(asset: Asset, shocks: Dict[str, float]) -> float:
    """
    Mark-to-model asset re-pricing under stress shocks.
    Returns stressed value in USD millions.
    """
    eq  = shocks.get("equity_shock",       0.0)
    rbp = shocks.get("rate_shock_bps",     0.0)
    sbp = shocks.get("credit_spread_bps",  0.0)
    vol = shocks.get("vol_shock",          0.0)

    v = asset.base_value

    if asset.asset_type == "gov_bond":
        # Duration-based rate sensitivity
        # ΔP ≈ -D * Δr * P
        delta_r = rbp / 10_000
        v = v * (1 - asset.duration * delta_r)

    elif asset.asset_type == "corp_bond":
        # Rate + credit spread sensitivity
        delta_r = rbp / 10_000
        delta_s = sbp / 10_000
        v = v * (1 - asset.duration * (delta_r + delta_s))

    elif asset.asset_type == "loan":
        # Corporate loans: re-priced via credit spread widening
        # Simplified: spread duration ≈ maturity/2
        spread_duration = asset.maturity_years / 2
        delta_s = sbp / 10_000
        v = v * (1 - spread_duration * delta_s)

    elif asset.asset_type == "irs":
        # Interest Rate Swap: DV01 * rate shock
        # DV01 expressed per 1bp
        v = v - asset.dv01 * rbp  # if receive-fixed, losses when rates rise

    elif asset.asset_type == "equity_deriv":
        # Delta + Vega exposure
        equity_pnl = asset.delta * eq * asset.notional
        vega_pnl   = asset.vega  * vol * asset.notional
        v = v + equity_pnl + vega_pnl

    elif asset.asset_type == "cds":
        # CDS protection seller: losses when spreads widen
        # Simplified: ΔV ≈ -notional * spread_dur * Δspread
        spread_duration = asset.maturity_years * 0.9
        delta_s = sbp / 10_000
        v = v - asset.notional * spread_duration * delta_s

    return max(0.0, round(v, 4))


def _post_by_type(asset_results: List[Dict]) -> Dict[str, float]:
    result: Dict[str, float] = {}
    for r in asset_results:
        result[r["type"]] = result.get(r["type"], 0.0) + r["post_value"]
    return {k: round(v, 2) for k, v in result.items()}


# ---------------------------------------------------------------------------
# Default synthetic portfolio builder
# ---------------------------------------------------------------------------

def _build_default_portfolio() -> List[Asset]:
    """Build a realistic synthetic wholesale banking portfolio."""
    return [
        # ── Corporate Loans ────────────────────────────────────────────────
        Asset("L001", "TechCorp Revolving Credit Facility",
              "loan", notional=500, base_value=498.5, ticker="AAPL",
              rating="A",   maturity_years=3.0, coupon=0.035, spread_bps=80),
        Asset("L002", "EnergyFirm Term Loan B",
              "loan", notional=300, base_value=295.0, ticker="XOM",
              rating="BBB", maturity_years=5.0, coupon=0.055, spread_bps=150),
        Asset("L003", "RetailGroup Leveraged Loan",
              "loan", notional=200, base_value=188.0, ticker="HD",
              rating="BB",  maturity_years=7.0, coupon=0.075, spread_bps=350),
        Asset("L004", "PharmaCo Acquisition Finance",
              "loan", notional=400, base_value=402.1, ticker="JNJ",
              rating="AA",  maturity_years=4.0, coupon=0.030, spread_bps=60),
        Asset("L005", "AutoMaker Working Capital Loan",
              "loan", notional=150, base_value=147.3, ticker="TSLA",
              rating="BB+", maturity_years=2.0, coupon=0.065, spread_bps=280),

        # ── Government Bonds ───────────────────────────────────────────────
        Asset("GB001", "US Treasury 10Y Note",
              "gov_bond", notional=600, base_value=598.0,
              rating="AAA", maturity_years=10.0, duration=8.7, coupon=0.042),
        Asset("GB002", "US Treasury 5Y Note",
              "gov_bond", notional=400, base_value=400.5,
              rating="AAA", maturity_years=5.0,  duration=4.5, coupon=0.038),
        Asset("GB003", "UK Gilt 7Y",
              "gov_bond", notional=200, base_value=197.8,
              rating="AA+", maturity_years=7.0,  duration=6.1, coupon=0.040),

        # ── Corporate Bonds ────────────────────────────────────────────────
        Asset("CB001", "Microsoft Senior Unsecured 5Y",
              "corp_bond", notional=250, base_value=252.3, ticker="MSFT",
              rating="AAA", maturity_years=5.0,  duration=4.6, coupon=0.039, spread_bps=35),
        Asset("CB002", "Amazon Investment-Grade Bond 7Y",
              "corp_bond", notional=300, base_value=301.0, ticker="AMZN",
              rating="AA",  maturity_years=7.0,  duration=6.2, coupon=0.043, spread_bps=55),
        Asset("CB003", "Bank of America Subordinated Debt",
              "corp_bond", notional=200, base_value=196.5, ticker="BAC",
              rating="A-",  maturity_years=10.0, duration=8.1, coupon=0.062, spread_bps=120),
        Asset("CB004", "High-Yield Energy Bond",
              "corp_bond", notional=150, base_value=139.0, ticker="CVX",
              rating="BB",  maturity_years=6.0,  duration=5.0, coupon=0.085, spread_bps=400),

        # ── Interest Rate Swaps ────────────────────────────────────────────
        Asset("IRS001", "USD 5Y Pay-Fixed Swap (Receive Float)",
              "irs", notional=500, base_value=3.2,
              rating="N/A", maturity_years=5.0, dv01=0.25,
              metadata={"pay_leg": "fixed", "receive_leg": "SOFR"}),
        Asset("IRS002", "USD 10Y Receive-Fixed Swap",
              "irs", notional=300, base_value=-1.8,
              rating="N/A", maturity_years=10.0, dv01=-0.45,
              metadata={"pay_leg": "SOFR", "receive_leg": "fixed"}),
        Asset("IRS003", "EUR 3Y Pay-Fixed Swap",
              "irs", notional=200, base_value=1.1,
              rating="N/A", maturity_years=3.0, dv01=0.12),

        # ── Equity Derivatives ─────────────────────────────────────────────
        Asset("ED001", "S&P 500 Call Spread (Delta-hedged Book)",
              "equity_deriv", notional=100, base_value=8.5,
              rating="N/A", delta=0.35, vega=2.1,
              metadata={"underlying": "SPX", "expiry": "3M"}),
        Asset("ED002", "Tech Sector Put Options Portfolio",
              "equity_deriv", notional=80, base_value=12.3,
              rating="N/A", delta=-0.60, vega=3.8, ticker="QQQ",
              metadata={"underlying": "QQQ", "expiry": "6M"}),

        # ── Credit Default Swaps ───────────────────────────────────────────
        Asset("CDS001", "CDS Protection Sold on HY Basket",
              "cds", notional=250, base_value=15.0,
              rating="N/A", maturity_years=5.0, spread_bps=350,
              metadata={"position": "protection_seller"}),
        Asset("CDS002", "CDS Protection Bought on IG Index",
              "cds", notional=400, base_value=-8.5,
              rating="N/A", maturity_years=5.0, spread_bps=80,
              metadata={"position": "protection_buyer"}),
    ]


def load_portfolio_from_csv(path: str) -> SyntheticPortfolio:
    """Load portfolio from a CSV file (must match Asset field names)."""
    df = pd.read_csv(path)
    assets = []
    for _, row in df.iterrows():
        row_dict = row.to_dict()
        # Parse JSON metadata if present
        if "metadata" in row_dict and isinstance(row_dict["metadata"], str):
            try:
                row_dict["metadata"] = json.loads(row_dict["metadata"])
            except Exception:
                row_dict["metadata"] = {}
        assets.append(Asset(**row_dict))
    return SyntheticPortfolio(assets)
