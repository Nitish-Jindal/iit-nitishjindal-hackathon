"""
Module A - Index Configuration
Defines the mock S&P 100 index with 20 stocks.
"""

from typing import Dict

# Mock index: 20 stocks from S&P 100 with initial equal weights
# Weights are fractions that sum to 1.0
MOCK_INDEX: Dict[str, Dict] = {
    "AAPL": {"name": "Apple Inc.",             "sector": "Technology",      "init_weight": 0.08},
    "MSFT": {"name": "Microsoft Corp.",         "sector": "Technology",      "init_weight": 0.08},
    "GOOGL":{"name": "Alphabet Inc.",           "sector": "Technology",      "init_weight": 0.07},
    "AMZN": {"name": "Amazon.com Inc.",         "sector": "Consumer Disc.",  "init_weight": 0.07},
    "NVDA": {"name": "Nvidia Corp.",            "sector": "Technology",      "init_weight": 0.06},
    "META": {"name": "Meta Platforms Inc.",     "sector": "Communication",   "init_weight": 0.06},
    "TSLA": {"name": "Tesla Inc.",              "sector": "Consumer Disc.",  "init_weight": 0.05},
    "JPM":  {"name": "JPMorgan Chase & Co.",   "sector": "Financials",      "init_weight": 0.05},
    "JNJ":  {"name": "Johnson & Johnson",       "sector": "Health Care",     "init_weight": 0.05},
    "V":    {"name": "Visa Inc.",               "sector": "Financials",      "init_weight": 0.05},
    "PG":   {"name": "Procter & Gamble Co.",   "sector": "Consumer Staples","init_weight": 0.04},
    "UNH":  {"name": "UnitedHealth Group",      "sector": "Health Care",     "init_weight": 0.04},
    "HD":   {"name": "Home Depot Inc.",         "sector": "Consumer Disc.",  "init_weight": 0.04},
    "BAC":  {"name": "Bank of America Corp.",   "sector": "Financials",      "init_weight": 0.04},
    "MA":   {"name": "Mastercard Inc.",         "sector": "Financials",      "init_weight": 0.04},
    "XOM":  {"name": "Exxon Mobil Corp.",       "sector": "Energy",          "init_weight": 0.04},
    "CVX":  {"name": "Chevron Corp.",           "sector": "Energy",          "init_weight": 0.04},
    "ABBV": {"name": "AbbVie Inc.",             "sector": "Health Care",     "init_weight": 0.04},
    "COST": {"name": "Costco Wholesale Corp.",  "sector": "Consumer Staples","init_weight": 0.03},
    "MRK":  {"name": "Merck & Co. Inc.",        "sector": "Health Care",     "init_weight": 0.03},
}

# Rebalancing parameters
REBALANCE_CONFIG = {
    # Maximum weight a single stock can hold (20%)
    "max_weight":  0.20,
    # Minimum weight a single stock can hold (1%)
    "min_weight":  0.01,
    # Sensitivity: how much sentiment shifts a weight per unit score
    # Δw = SENTIMENT_ALPHA * sentiment_score * current_weight
    "sentiment_alpha": 0.15,
    # Momentum dampening: re-normalize slowly over N steps
    "smoothing_window": 5,
}
