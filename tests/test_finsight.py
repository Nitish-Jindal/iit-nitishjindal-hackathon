"""
Tests for FinSight AI
Run with: pytest tests/ -v
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

# ---------------------------------------------------------------------------
# Engine Tests
# ---------------------------------------------------------------------------

class TestIngestion:
    def test_synthetic_social_returns_expected_count(self):
        from src.engine.ingestion import ingest_synthetic_social
        posts = ingest_synthetic_social(n=10, seed=42)
        assert len(posts) == 10

    def test_synthetic_post_has_required_fields(self):
        from src.engine.ingestion import ingest_synthetic_social
        posts = ingest_synthetic_social(n=1, seed=1)
        post = posts[0]
        for field in ["source", "headline", "full_text", "timestamp", "ticker", "uid"]:
            assert field in post, f"Missing field: {field}"

    def test_ticker_detection(self):
        from src.engine.ingestion import _detect_ticker
        assert _detect_ticker("Apple announces record iPhone sales") == "AAPL"
        assert _detect_ticker("Microsoft Azure revenue surges") == "MSFT"
        assert _detect_ticker("random unrelated text") is None

    def test_deduplication(self):
        from src.engine.ingestion import ingest_all
        items = ingest_all(rss=False, social=True, n_social=20)
        uids = [i["uid"] for i in items]
        assert len(uids) == len(set(uids)), "Duplicate UIDs found"


class TestNLPAnalyzer:
    def test_lexicon_sentiment_positive(self):
        from src.engine.nlp_analyzer import _lexicon_sentiment
        score, label, conf = _lexicon_sentiment(
            "Apple beats earnings; revenue surges record profit growth"
        )
        assert score > 0, f"Expected positive, got {score}"
        assert label == "positive"
        assert 0 <= conf <= 1

    def test_lexicon_sentiment_negative(self):
        from src.engine.nlp_analyzer import _lexicon_sentiment
        score, label, conf = _lexicon_sentiment(
            "JPMorgan faces massive lawsuit loss bankruptcy warning downgrade"
        )
        assert score < 0, f"Expected negative, got {score}"
        assert label == "negative"

    def test_lexicon_sentiment_neutral(self):
        from src.engine.nlp_analyzer import _lexicon_sentiment
        score, label, _ = _lexicon_sentiment("The company held its annual meeting today.")
        assert label == "neutral"

    def test_keyword_event_classify_geopolitical(self):
        from src.engine.nlp_analyzer import _keyword_event_classify
        evt, _ = _keyword_event_classify("Military conflict and war escalation geopolitical")
        assert evt == "Geopolitical"

    def test_keyword_event_classify_ma(self):
        from src.engine.nlp_analyzer import _keyword_event_classify
        evt, _ = _keyword_event_classify("Company announces major acquisition merger takeover deal")
        assert evt == "Merger & Acquisition"

    def test_impact_score_range(self):
        from src.engine.nlp_analyzer import compute_impact_score
        for event in ["Geopolitical", "Macroeconomic", "Product Launch", "Market Sentiment"]:
            score = compute_impact_score(-1.0, event, 0.9, 0.8)
            assert 1.0 <= score <= 10.0, f"Impact {score} out of range for {event}"

    def test_analyze_full_pipeline(self):
        from src.engine.nlp_analyzer import analyze
        item = {
            "source": "test",
            "headline": "Federal Reserve raises rates by 75bps amid inflation surge",
            "full_text": "The Federal Reserve announced a 75 basis point rate hike today to combat inflation.",
            "ticker": "JPM",
            "timestamp": "2026-01-01T00:00:00",
            "uid": "test-001",
        }
        result = analyze(item)
        assert "sentiment_score" in result
        assert "event_type" in result
        assert "impact_score" in result
        assert -1.0 <= result["sentiment_score"] <= 1.0
        assert 1.0 <= result["impact_score"] <= 10.0


class TestDatabase:
    def test_initialize_and_insert(self, tmp_path, monkeypatch):
        """Test DB init and signal insert."""
        import src.engine.database as db_module
        monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "test.db")

        db_module.initialize_db()

        signal = {
            "source": "test",
            "ticker": "AAPL",
            "headline": "Test headline",
            "full_text": "Test full text",
            "sentiment_score": 0.5,
            "sentiment_label": "positive",
            "event_type": "Product Launch",
            "impact_score": 5.5,
            "confidence": 0.85,
            "timestamp": "2026-01-01T00:00:00",
        }
        row_id = db_module.insert_signal(signal)
        assert row_id is not None and row_id > 0

        signals = db_module.get_recent_signals(limit=5)
        assert len(signals) >= 1
        assert signals[0]["ticker"] == "AAPL"


# ---------------------------------------------------------------------------
# Module A Tests
# ---------------------------------------------------------------------------

class TestIndexRebalancer:
    def test_initial_weights_sum_to_one(self):
        from src.module_a.rebalancer import IndexRebalancer
        rb = IndexRebalancer()
        assert abs(sum(rb.weights.values()) - 1.0) < 1e-9

    def test_positive_sentiment_increases_weight(self):
        from src.module_a.rebalancer import IndexRebalancer
        rb = IndexRebalancer()
        initial_weight = rb.weights["AAPL"]
        signal = {"ticker": "AAPL", "sentiment_score": 1.0, "impact_score": 8.0}
        rb.apply_signal(signal)
        assert rb.weights["AAPL"] > initial_weight

    def test_negative_sentiment_decreases_weight(self):
        from src.module_a.rebalancer import IndexRebalancer
        rb = IndexRebalancer()
        initial_weight = rb.weights["TSLA"]
        signal = {"ticker": "TSLA", "sentiment_score": -1.0, "impact_score": 8.0}
        rb.apply_signal(signal)
        assert rb.weights["TSLA"] < initial_weight

    def test_weights_always_sum_to_one_after_signals(self):
        from src.module_a.rebalancer import IndexRebalancer
        rb = IndexRebalancer()
        signals = [
            {"ticker": "AAPL", "sentiment_score": 0.8, "impact_score": 7.0},
            {"ticker": "MSFT", "sentiment_score": -0.6, "impact_score": 9.0},
            {"ticker": "NVDA", "sentiment_score": 1.0, "impact_score": 8.5},
            {"ticker": "JPM", "sentiment_score": -0.9, "impact_score": 8.0},
        ]
        for sig in signals:
            rb.apply_signal(sig)
        assert abs(sum(rb.weights.values()) - 1.0) < 1e-6

    def test_min_max_weight_bounds(self):
        from src.module_a.rebalancer import IndexRebalancer, REBALANCE_CONFIG
        rb = IndexRebalancer()
        # Apply extreme negative signal many times
        for _ in range(50):
            rb.apply_signal({"ticker": "TSLA", "sentiment_score": -1.0, "impact_score": 10.0})
        assert rb.weights["TSLA"] >= REBALANCE_CONFIG["min_weight"]
        assert all(w <= REBALANCE_CONFIG["max_weight"] for w in rb.weights.values())

    def test_unknown_ticker_returns_none(self):
        from src.module_a.rebalancer import IndexRebalancer
        rb = IndexRebalancer()
        result = rb.apply_signal({"ticker": "UNKNOWN", "sentiment_score": 0.5, "impact_score": 5.0})
        assert result is None

    def test_reset(self):
        from src.module_a.rebalancer import IndexRebalancer
        from src.module_a.index_config import MOCK_INDEX
        rb = IndexRebalancer()
        rb.apply_signal({"ticker": "AAPL", "sentiment_score": 1.0, "impact_score": 9.0})
        rb.reset()
        assert rb.weights["AAPL"] == MOCK_INDEX["AAPL"]["init_weight"]
        assert len(rb.history) == 0


# ---------------------------------------------------------------------------
# Module B Tests
# ---------------------------------------------------------------------------

class TestPortfolio:
    def test_portfolio_total_value(self):
        from src.module_b.portfolio import SyntheticPortfolio
        p = SyntheticPortfolio()
        assert p.total_value > 0

    def test_stress_test_returns_required_fields(self):
        from src.module_b.portfolio import SyntheticPortfolio
        p = SyntheticPortfolio()
        result = p.apply_stress("Geopolitical")
        for field in ["pre_value", "post_value", "pnl_impact", "pnl_pct",
                      "asset_breakdown", "scenario", "shocks_applied"]:
            assert field in result, f"Missing: {field}"

    def test_negative_scenario_reduces_value(self):
        from src.module_b.portfolio import SyntheticPortfolio
        p = SyntheticPortfolio()
        result = p.apply_stress("Geopolitical")
        assert result["post_value"] < result["pre_value"]

    def test_all_scenarios_valid(self):
        from src.module_b.portfolio import SyntheticPortfolio, SHOCK_SCENARIOS
        p = SyntheticPortfolio()
        for scenario in SHOCK_SCENARIOS:
            result = p.apply_stress(scenario)
            assert result["pre_value"] > 0
            assert result["post_value"] >= 0


class TestStressTestEngine:
    def test_high_impact_triggers_stress_test(self):
        from src.module_b.stress_test import StressTestEngine
        engine = StressTestEngine()
        signal = {
            "id": 1,
            "ticker": "XOM",
            "sentiment_score": -0.9,
            "event_type": "Geopolitical",
            "impact_score": 9.0,
            "headline": "War escalation collapses oil markets",
        }
        result = engine.process_signal(signal)
        assert result is not None
        assert result["pnl_impact"] < 0  # Geopolitical = negative shock

    def test_low_impact_does_not_trigger(self):
        from src.module_b.stress_test import StressTestEngine
        engine = StressTestEngine()
        signal = {
            "id": 2,
            "ticker": "AAPL",
            "sentiment_score": 0.1,
            "event_type": "Product Launch",
            "impact_score": 3.0,
            "headline": "Minor product update",
        }
        result = engine.process_signal(signal)
        assert result is None

    def test_manual_scenario_run(self):
        from src.module_b.stress_test import StressTestEngine
        engine = StressTestEngine()
        result = engine.run_scenario("Severe Stress")
        assert result["pnl_pct"] < -5.0  # Severe stress must be > 5% loss
