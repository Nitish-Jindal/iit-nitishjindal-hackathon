"""
Generate sample data files for offline/demo mode.
Run: python data/generate_sample_data.py
"""
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).parent

TICKERS = {
    "AAPL": "Apple", "MSFT": "Microsoft", "GOOGL": "Alphabet",
    "AMZN": "Amazon", "NVDA": "Nvidia", "META": "Meta",
    "TSLA": "Tesla", "JPM": "JPMorgan", "JNJ": "Johnson & Johnson",
    "V": "Visa", "PG": "P&G", "UNH": "UnitedHealth",
    "HD": "Home Depot", "BAC": "Bank of America", "MA": "Mastercard",
    "XOM": "ExxonMobil", "CVX": "Chevron", "ABBV": "AbbVie",
    "COST": "Costco", "MRK": "Merck",
}

NEWS_TEMPLATES = [
    ("{company} reports record quarterly earnings, beating consensus by {pct}%.",
     "Earnings & Guidance", "positive"),
    ("{company} announces layoffs of {n},000 employees amid restructuring.",
     "Management Change", "negative"),
    ("Federal Reserve signals {n} rate hikes — {company} shares under pressure.",
     "Macroeconomic", "negative"),
    ("{company} and {target} confirm merger talks worth {val}B USD.",
     "Merger & Acquisition", "positive"),
    ("EU antitrust probe targets {company} over market dominance concerns.",
     "Regulatory & Legal", "negative"),
    ("{company} launches revolutionary AI-powered platform, stock surges {pct}%.",
     "Product Launch", "positive"),
    ("Geopolitical tensions in Eastern Europe send {company} supply chain into disarray.",
     "Geopolitical", "negative"),
    ("{company} CFO resigns suddenly; board launches external search.",
     "Management Change", "negative"),
    ("Moody's upgrades {company} bonds to investment grade — credit outlook improving.",
     "Credit Event", "positive"),
    ("Inflation data at {pct}% YoY — higher than expected, {company} bonds hit.",
     "Macroeconomic", "negative"),
    ("{company} buyback program of \${val}B announced — shareholder value play.",
     "Earnings & Guidance", "positive"),
    ("{company} ESG score drops to D — institutional investors react.",
     "Environmental & ESG", "negative"),
    ("Strong US jobs report supports risk-on sentiment; {company} rallies {pct}%.",
     "Market Sentiment", "positive"),
    ("{company} faces class-action lawsuit over misleading financial disclosures.",
     "Regulatory & Legal", "negative"),
    ("{company} credit downgrade by S&P — elevated leverage flagged.",
     "Credit Event", "negative"),
]

TWEET_TEMPLATES = [
    ("${ticker} absolutely crushing it this quarter! Revenue +{pct}% 🚀📈 Bullish!",
     "Earnings & Guidance", "positive"),
    ("Bad news for ${ticker}. Massive layoffs incoming. Management disaster. 📉",
     "Management Change", "negative"),
    ("Geopolitical risk is real. ${ticker} supply chain exposed. Be careful. ⚠️",
     "Geopolitical", "negative"),
    ("${ticker} M&A deal confirmed! Price target raised to \${val}. Let's go! 💪",
     "Merger & Acquisition", "positive"),
    ("Fed rate hike hurting ${ticker} valuations. DCF crushed by higher rates.",
     "Macroeconomic", "negative"),
    ("${ticker} new product line is INCREDIBLE. Preorders sold out. 🔥",
     "Product Launch", "positive"),
    ("ESG dumping ${ticker} after environmental violations. Not a good look. 🌱",
     "Environmental & ESG", "negative"),
    ("Credit markets pricing in default risk for ${ticker}. Spreads widening badly.",
     "Credit Event", "negative"),
    ("${ticker} buyback signals confidence — management buying the dip! 💎",
     "Market Sentiment", "positive"),
    ("Regulatory crackdown incoming for ${ticker}. EU fines could be massive. 😬",
     "Regulatory & Legal", "negative"),
]

def generate_ts(i: int) -> str:
    base = datetime.utcnow() - timedelta(hours=6)
    offset = timedelta(minutes=i * 4 + random.randint(0, 3))
    return (base + offset).isoformat()

def fill_template(tmpl: str, ticker: str, company: str, target: str) -> str:
    return tmpl.format(
        ticker=ticker, company=company, target=target,
        pct=random.randint(5, 35),
        n=random.randint(2, 15),
        val=random.randint(5, 80),
    )

def make_uid(text: str, source: str) -> str:
    import hashlib
    return hashlib.md5(f"{source}:{text}".encode()).hexdigest()

rng = random.Random(2026)
tickers = list(TICKERS.keys())

# News
news = []
for i in range(60):
    ticker = rng.choice(tickers)
    company = TICKERS[ticker]
    target = TICKERS[rng.choice([t for t in tickers if t != ticker])]
    tmpl, event, sentiment_hint = rng.choice(NEWS_TEMPLATES)
    text = fill_template(tmpl, ticker, company, target)
    news.append({
        "source": f"RSS:FinancialNews",
        "headline": text,
        "full_text": text,
        "url": f"https://example-news.com/article/{i}",
        "timestamp": generate_ts(i),
        "ticker": ticker,
        "uid": make_uid(text, "news"),
        "_hint_event": event,
        "_hint_sentiment": sentiment_hint,
    })

# Tweets
tweets = []
for i in range(60):
    ticker = rng.choice(tickers)
    company = TICKERS[ticker]
    target = TICKERS[rng.choice([t for t in tickers if t != ticker])]
    tmpl, event, sentiment_hint = rng.choice(TWEET_TEMPLATES)
    text = fill_template(tmpl, ticker, company, target)
    tweets.append({
        "source": "SocialMedia:Synthetic",
        "headline": text[:120],
        "full_text": text,
        "url": f"https://x.com/user/status/{1000000 + i}",
        "timestamp": generate_ts(i),
        "ticker": ticker,
        "uid": make_uid(text, "twitter"),
        "_hint_event": event,
        "_hint_sentiment": sentiment_hint,
    })

(HERE / "sample_news.json").write_text(json.dumps(news, indent=2))
(HERE / "sample_tweets.json").write_text(json.dumps(tweets, indent=2))
print(f"Generated {len(news)} news articles → sample_news.json")
print(f"Generated {len(tweets)} tweets → sample_tweets.json")
