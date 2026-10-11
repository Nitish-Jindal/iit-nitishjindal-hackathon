"""
FinSight AI - Data Ingestion Module
Fetches text from two sources:
  1. RSS/News feeds (Financial Times, Reuters, etc.)
  2. Synthetic social media posts (Twitter/X-like)

In production, replace synthetic source with real API (Twitter v2, Stocktwits, etc.)
"""

import json
import random
import hashlib
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from pathlib import Path

import feedparser
import requests
from loguru import logger


# ---------------------------------------------------------------------------
# Ticker → company name mapping for the mock S&P 100 index
# ---------------------------------------------------------------------------
TICKER_KEYWORDS: Dict[str, List[str]] = {
    "AAPL":  ["Apple", "iPhone", "Mac", "Tim Cook", "iOS"],
    "MSFT":  ["Microsoft", "Azure", "Windows", "Satya Nadella", "Teams"],
    "GOOGL": ["Google", "Alphabet", "Sundar Pichai", "Search", "YouTube"],
    "AMZN":  ["Amazon", "AWS", "Jeff Bezos", "Prime", "Alexa"],
    "NVDA":  ["Nvidia", "GPU", "CUDA", "Jensen Huang", "AI chips"],
    "META":  ["Meta", "Facebook", "Instagram", "WhatsApp", "Zuckerberg"],
    "TSLA":  ["Tesla", "Elon Musk", "EV", "Autopilot", "Cybertruck"],
    "JPM":   ["JPMorgan", "Jamie Dimon", "Chase", "investment bank"],
    "JNJ":   ["Johnson & Johnson", "J&J", "pharma", "healthcare"],
    "V":     ["Visa", "payment network", "credit card"],
    "PG":    ["Procter & Gamble", "P&G", "consumer goods"],
    "UNH":   ["UnitedHealth", "insurance", "healthcare plan"],
    "HD":    ["Home Depot", "home improvement", "retail"],
    "BAC":   ["Bank of America", "BofA", "banking"],
    "MA":    ["Mastercard", "payment", "card network"],
    "XOM":   ["ExxonMobil", "Exxon", "oil", "energy"],
    "CVX":   ["Chevron", "oil", "energy", "petroleum"],
    "ABBV":  ["AbbVie", "pharma", "biopharmaceutical", "Humira"],
    "COST":  ["Costco", "warehouse", "retail", "membership"],
    "MRK":   ["Merck", "pharmaceutical", "vaccine"],
}

RSS_FEEDS: List[Dict[str, str]] = [
    {
        "name": "Reuters Business",
        "url":  "https://feeds.reuters.com/reuters/businessNews",
    },
    {
        "name": "MarketWatch",
        "url":  "http://feeds.marketwatch.com/marketwatch/topstories/",
    },
    {
        "name": "Yahoo Finance",
        "url":  "https://finance.yahoo.com/news/rssindex",
    },
    {
        "name": "Seeking Alpha",
        "url":  "https://seekingalpha.com/feed.xml",
    },
    {
        "name": "CNBC",
        "url":  "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    },
]

# ---------------------------------------------------------------------------
# Synthetic social-media posts (mimics Twitter/X financial discourse)
# Used as a second data source; replace with real API in production.
# ---------------------------------------------------------------------------
SYNTHETIC_TWEET_TEMPLATES: List[str] = [
    "{company} Q3 earnings crush estimates — revenue up {pct}% YoY. Bullish on {ticker}! 🚀",
    "Breaking: {company} announces major layoffs, cutting {n}k jobs. Bad sign for {ticker}? 📉",
    "Fed rate hike fears hit {ticker} hard. Rates up = growth stocks hurt. $QQQ also dropping.",
    "{ticker} just announced partnership with NVDA for AI integration. Game changer! 🔥",
    "Geopolitical tensions escalating — oil surging past ${price}. Energy sector on fire. $XOM $CVX",
    "{company} faces antitrust probe by EU. Could cost billions. {ticker} down after-hours.",
    "BREAKING: {company} CFO resigns citing 'personal reasons.' Accountability red flag for {ticker}.",
    "{ticker} buyback program worth ${buyback}B announced. Shareholders rejoice! 📈",
    "Supply chain disruptions hitting {company} margins. Watch {ticker} guidance closely.",
    "{company} drug trial succeeds with 94% efficacy rate. {ticker} up 18% pre-market! 💊",
    "Credit downgrade warning on {ticker} bonds — S&P flags elevated leverage ratio.",
    "Merger talks between {company} and {target} confirmed. Regulatory risk remains. $M&A",
    "Inflation data hotter than expected — all financial stocks under pressure. $JPM $BAC $GS",
    "ESG funds dumping {ticker} after environmental violation disclosure. ESG risk rising.",
    "{company} beats on EPS but misses revenue. Mixed signals — {ticker} flat after-hours.",
]


def _dedupe_id(text: str, source: str) -> str:
    return hashlib.md5(f"{source}:{text}".encode()).hexdigest()


def _detect_ticker(text: str) -> Optional[str]:
    """Heuristic: find which ticker's keywords appear in the text."""
    text_lower = text.lower()
    for ticker, keywords in TICKER_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in text_lower:
                return ticker
    # also match explicit $TICKER mentions
    import re
    m = re.search(r"\$([A-Z]{1,5})\b", text)
    if m and m.group(1) in TICKER_KEYWORDS:
        return m.group(1)
    return None


# ---------------------------------------------------------------------------
# Source 1: RSS / News feeds
# ---------------------------------------------------------------------------

def ingest_rss(max_per_feed: int = 10) -> List[Dict[str, Any]]:
    """
    Fetch articles from a curated list of financial RSS feeds.
    Falls back gracefully to an empty list if a feed is unreachable.
    """
    articles: List[Dict[str, Any]] = []
    for feed_cfg in RSS_FEEDS:
        try:
            logger.info(f"Fetching RSS: {feed_cfg['name']}")
            parsed = feedparser.parse(feed_cfg["url"])
            for entry in parsed.entries[:max_per_feed]:
                title   = getattr(entry, "title", "")
                summary = getattr(entry, "summary", "")
                link    = getattr(entry, "link",  "")
                pub     = getattr(entry, "published", datetime.now(timezone.utc).replace(tzinfo=None).isoformat())
                text    = f"{title}. {summary}"
                articles.append(
                    {
                        "source":    f"RSS:{feed_cfg['name']}",
                        "headline":  title,
                        "full_text": text,
                        "url":       link,
                        "timestamp": pub,
                        "ticker":    _detect_ticker(text),
                        "uid":       _dedupe_id(title, feed_cfg["name"]),
                    }
                )
        except Exception as exc:
            logger.warning(f"RSS fetch failed for {feed_cfg['name']}: {exc}")

    logger.info(f"RSS ingestion complete — {len(articles)} articles fetched.")
    return articles


# ---------------------------------------------------------------------------
# Source 2: Synthetic social-media stream
# ---------------------------------------------------------------------------

def _generate_synthetic_post(rng: random.Random) -> Dict[str, Any]:
    ticker  = rng.choice(list(TICKER_KEYWORDS.keys()))
    company = TICKER_KEYWORDS[ticker][0]
    target  = rng.choice([t for t in TICKER_KEYWORDS if t != ticker])

    text = rng.choice(SYNTHETIC_TWEET_TEMPLATES).format(
        ticker=ticker,
        company=company,
        target=TICKER_KEYWORDS[target][0],
        pct=rng.randint(5, 40),
        n=rng.randint(2, 20),
        price=rng.randint(80, 130),
        buyback=rng.randint(5, 50),
    )
    ts = (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=rng.randint(0, 120))).isoformat()
    return {
        "source":    "SocialMedia:Synthetic",
        "headline":  text[:120],
        "full_text": text,
        "url":       f"https://x.com/synthetic/{_dedupe_id(text, 'x')}",
        "timestamp": ts,
        "ticker":    ticker,
        "uid":       _dedupe_id(text, "synthetic"),
    }


def ingest_synthetic_social(n: int = 30, seed: int = 42) -> List[Dict[str, Any]]:
    """
    Generate a deterministic yet varied synthetic stream of social-media posts.
    Seed is overridden with current-minute to get fresh data each run window.
    """
    rng = random.Random(seed ^ (datetime.now(timezone.utc).replace(tzinfo=None).minute * 37))
    posts = [_generate_synthetic_post(rng) for _ in range(n)]
    logger.info(f"Synthetic social-media ingestion complete — {len(posts)} posts generated.")
    return posts


# ---------------------------------------------------------------------------
# Unified ingestion entry-point
# ---------------------------------------------------------------------------

def load_sample_data_from_disk() -> List[Dict[str, Any]]:
    """Load pre-saved sample data for offline / demo mode."""
    base = Path(__file__).parent.parent.parent / "data"
    items: List[Dict[str, Any]] = []
    for fname in ["sample_news.json", "sample_tweets.json"]:
        fpath = base / fname
        if fpath.exists():
            try:
                items.extend(json.loads(fpath.read_text()))
            except Exception as exc:
                logger.warning(f"Could not load {fpath}: {exc}")
    return items


def ingest_all(
    rss: bool = True,
    social: bool = True,
    from_disk: bool = False,
    max_rss: int = 10,
    n_social: int = 30,
) -> List[Dict[str, Any]]:
    """
    Aggregate ingestion from all enabled sources.

    Args:
        rss:       Fetch live RSS articles.
        social:    Generate synthetic social-media posts.
        from_disk: Load pre-saved sample data instead of hitting networks.
        max_rss:   Max articles per RSS feed.
        n_social:  Number of synthetic posts.
    """
    if from_disk:
        return load_sample_data_from_disk()

    items: List[Dict[str, Any]] = []
    if rss:
        items.extend(ingest_rss(max_per_feed=max_rss))
    if social:
        items.extend(ingest_synthetic_social(n=n_social))

    # Deduplicate by uid
    seen, unique = set(), []
    for item in items:
        if item["uid"] not in seen:
            seen.add(item["uid"])
            unique.append(item)

    logger.info(f"Total unique items after dedup: {len(unique)}")
    return unique
