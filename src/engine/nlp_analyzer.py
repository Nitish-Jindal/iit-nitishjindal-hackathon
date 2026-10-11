"""
FinSight AI - NLP Analyzer
Core AI processing pipeline for financial text.

Pipeline:
  1. Sentiment Analysis   → FinBERT (domain-tuned BERT for finance)
  2. Event Classification → Zero-shot classification (BART-MNLI)
  3. Impact Scoring       → Rule-augmented heuristic calibrated on sentiment + event type

Models used:
  - ProsusAI/finbert          : Finance-specific sentiment (positive/negative/neutral)
  - facebook/bart-large-mnli  : Zero-shot multi-label event classification

Both models are loaded lazily and cached.
"""

from __future__ import annotations

import re
import math
from typing import Dict, Any, List, Tuple, Optional
from functools import lru_cache
from datetime import datetime, timezone

from loguru import logger

# ---------------------------------------------------------------------------
# Model loading (lazy, cached)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _load_sentiment_pipeline():
    """Load FinBERT sentiment pipeline (loaded once, reused)."""
    try:
        from transformers import pipeline
        logger.info("Loading FinBERT sentiment model …")
        pipe = pipeline(
            "text-classification",
            model="ProsusAI/finbert",
            top_k=None,
            truncation=True,
            max_length=512,
        )
        logger.info("FinBERT loaded ✓")
        return pipe
    except Exception as exc:
        logger.warning(f"FinBERT load failed ({exc}); using lexicon fallback.")
        return None


@lru_cache(maxsize=1)
def _load_zeroshot_pipeline():
    """Load BART-MNLI zero-shot classification pipeline."""
    try:
        from transformers import pipeline
        logger.info("Loading zero-shot classification model …")
        pipe = pipeline(
            "zero-shot-classification",
            model="facebook/bart-large-mnli",
            multi_label=False,
        )
        logger.info("Zero-shot classifier loaded ✓")
        return pipe
    except Exception as exc:
        logger.warning(f"Zero-shot load failed ({exc}); using keyword fallback.")
        return None


# ---------------------------------------------------------------------------
# Event taxonomy
# ---------------------------------------------------------------------------

EVENT_LABELS: List[str] = [
    "Geopolitical",
    "Macroeconomic",
    "Credit Event",
    "Merger & Acquisition",
    "Product Launch",
    "Regulatory & Legal",
    "Earnings & Guidance",
    "Management Change",
    "Environmental & ESG",
    "Market Sentiment",
]

# Base-impact modifiers per event type (1-10 scale anchors)
EVENT_IMPACT_BASE: Dict[str, float] = {
    "Geopolitical":          8.5,
    "Macroeconomic":         7.5,
    "Credit Event":          8.0,
    "Merger & Acquisition":  7.0,
    "Product Launch":        5.0,
    "Regulatory & Legal":    6.5,
    "Earnings & Guidance":   5.5,
    "Management Change":     5.0,
    "Environmental & ESG":   4.5,
    "Market Sentiment":      4.0,
}

# ---------------------------------------------------------------------------
# Lexicon-based fallbacks (used when models unavailable)
# ---------------------------------------------------------------------------

POSITIVE_WORDS = {
    "beat", "surge", "soar", "gain", "rise", "profit", "record", "strong",
    "growth", "bullish", "upgrade", "outperform", "rally", "boost", "launch",
    "success", "partnership", "buyback", "dividend", "efficient", "innovative",
    "breakthrough", "approved", "expand", "win", "deal", "milestone",
}

NEGATIVE_WORDS = {
    "miss", "drop", "fall", "loss", "cut", "layoff", "downturn", "bearish",
    "downgrade", "underperform", "decline", "crash", "probe", "lawsuit",
    "resign", "fraud", "recall", "bankruptcy", "deficit", "warning", "risk",
    "sanction", "tariff", "inflation", "rate hike", "breach", "hack", "fine",
    "penalty", "downgrade", "violation", "delay", "cancel",
}

EVENT_KEYWORD_MAP: Dict[str, List[str]] = {
    "Geopolitical":         ["war", "sanction", "tension", "geopolitical", "conflict", "military"],
    "Macroeconomic":        ["inflation", "rate", "fed", "gdp", "recession", "unemployment", "cpi"],
    "Credit Event":         ["downgrade", "credit", "default", "bond", "debt", "leverage", "rating"],
    "Merger & Acquisition": ["merger", "acquisition", "takeover", "buyout", "deal", "m&a"],
    "Product Launch":       ["launch", "release", "unveil", "announce product", "new product", "ship"],
    "Regulatory & Legal":   ["regulation", "lawsuit", "probe", "antitrust", "sec", "fine", "penalty"],
    "Earnings & Guidance":  ["earnings", "eps", "revenue", "guidance", "quarterly", "beat", "miss"],
    "Management Change":    ["ceo", "cfo", "resign", "appoint", "leadership", "executive", "board"],
    "Environmental & ESG":  ["esg", "carbon", "climate", "environmental", "sustainability", "green"],
    "Market Sentiment":     ["sentiment", "momentum", "technical", "rally", "correction"],
}


def _lexicon_sentiment(text: str) -> Tuple[float, str, float]:
    """
    Simple lexicon-based sentiment scorer.
    Returns (score [-1,1], label, confidence).
    """
    words = re.findall(r"\b\w+\b", text.lower())
    pos = sum(1 for w in words if w in POSITIVE_WORDS)
    neg = sum(1 for w in words if w in NEGATIVE_WORDS)
    total = pos + neg
    if total == 0:
        return 0.0, "neutral", 0.5
    score = (pos - neg) / total
    label = "positive" if score > 0.1 else ("negative" if score < -0.1 else "neutral")
    confidence = min(0.9, 0.5 + abs(score) * 0.5)
    return round(score, 4), label, round(confidence, 4)


def _keyword_event_classify(text: str) -> Tuple[str, float]:
    """Keyword-based event classifier (fallback)."""
    text_lower = text.lower()
    scores: Dict[str, int] = {}
    for event, keywords in EVENT_KEYWORD_MAP.items():
        scores[event] = sum(1 for kw in keywords if kw in text_lower)
    best = max(scores, key=scores.get)
    total = sum(scores.values())
    confidence = scores[best] / total if total > 0 else 0.3
    if scores[best] == 0:
        best = "Market Sentiment"
        confidence = 0.3
    return best, round(min(confidence, 0.95), 4)


# ---------------------------------------------------------------------------
# Sentiment analysis
# ---------------------------------------------------------------------------

def analyze_sentiment(text: str) -> Tuple[float, str, float]:
    """
    Analyze sentiment using FinBERT, falling back to lexicon.

    Returns:
        (score, label, confidence)
        score  : float in [-1.0, 1.0]
        label  : "positive" | "negative" | "neutral"
        confidence : float in [0.0, 1.0]
    """
    pipe = _load_sentiment_pipeline()
    if pipe is not None:
        try:
            # FinBERT returns list of label/score dicts
            results = pipe(text[:512])[0]  # top_k=None → list
            label_map = {r["label"].lower(): r["score"] for r in results}
            pos = label_map.get("positive", 0.0)
            neg = label_map.get("negative", 0.0)
            neu = label_map.get("neutral",  0.0)

            score = pos - neg          # range [-1, 1]
            best_label = max(label_map, key=label_map.get)
            confidence = label_map[best_label]
            return round(score, 4), best_label, round(confidence, 4)
        except Exception as exc:
            logger.debug(f"FinBERT inference failed: {exc}; using lexicon.")

    return _lexicon_sentiment(text)


# ---------------------------------------------------------------------------
# Event classification
# ---------------------------------------------------------------------------

def classify_event(text: str) -> Tuple[str, float]:
    """
    Classify event type using zero-shot classification.

    Returns:
        (event_label, confidence)
    """
    pipe = _load_zeroshot_pipeline()
    if pipe is not None:
        try:
            result = pipe(
                text[:1024],
                candidate_labels=EVENT_LABELS,
                hypothesis_template="This financial news is about {}.",
            )
            return result["labels"][0], round(result["scores"][0], 4)
        except Exception as exc:
            logger.debug(f"Zero-shot inference failed: {exc}; using keywords.")

    return _keyword_event_classify(text)


# ---------------------------------------------------------------------------
# Impact scoring
# ---------------------------------------------------------------------------

def compute_impact_score(
    sentiment_score: float,
    event_type: str,
    sentiment_confidence: float,
    event_confidence: float,
) -> float:
    """
    Compute a market impact score from 1.0 to 10.0.

    Formula:
      base     = EVENT_IMPACT_BASE[event_type]
      polarity = |sentiment_score| (magnitude of sentiment)
      boost    = polarity * 2 * avg_confidence
      impact   = clip(base * 0.6 + boost * base * 0.4, 1, 10)

    This rewards extreme sentiment for high-impact event types.
    """
    base = EVENT_IMPACT_BASE.get(event_type, 5.0)
    polarity = abs(sentiment_score)
    avg_conf = (sentiment_confidence + event_confidence) / 2
    # Weighted combination
    impact = base * 0.55 + polarity * base * 0.35 * avg_conf + avg_conf * 1.5
    impact = max(1.0, min(10.0, impact))
    return round(impact, 2)


# ---------------------------------------------------------------------------
# Main analysis function
# ---------------------------------------------------------------------------

def analyze(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Full NLP analysis of a single ingested item.

    Args:
        item: dict with keys: source, headline, full_text, ticker, timestamp, …

    Returns:
        Enriched dict with risk signal fields added.
    """
    text = f"{item.get('headline', '')}. {item.get('full_text', '')}"
    text = text.strip()

    # Run NLP pipeline
    sentiment_score, sentiment_label, sent_conf = analyze_sentiment(text)
    event_type, event_conf = classify_event(text)
    impact_score = compute_impact_score(
        sentiment_score, event_type, sent_conf, event_conf
    )

    signal = {
        **item,
        "sentiment_score":  sentiment_score,
        "sentiment_label":  sentiment_label,
        "event_type":       event_type,
        "impact_score":     impact_score,
        "confidence":       round((sent_conf + event_conf) / 2, 4),
        "analyzed_at":      datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
    }
    return signal


def analyze_batch(items: List[Dict[str, Any]], verbose: bool = True) -> List[Dict[str, Any]]:
    """Analyze a list of ingested items."""
    results = []
    for i, item in enumerate(items):
        try:
            results.append(analyze(item))
            if verbose and (i + 1) % 10 == 0:
                logger.info(f"Analyzed {i+1}/{len(items)} items …")
        except Exception as exc:
            logger.error(f"Analysis failed for item {i}: {exc}")
    logger.info(f"Batch analysis complete — {len(results)} signals generated.")
    return results
