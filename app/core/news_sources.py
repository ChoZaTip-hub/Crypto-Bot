"""Default news source URLs and provider identifiers."""

# RSS feeds (crypto + macro context)
DEFAULT_NEWS_RSS_URLS: tuple[str, ...] = (
    "https://thedefiant.io/feed/",
    "https://www.coindesk.com/arc/outboundfeeds/rss/?outputType=xml",
    "https://cointelegraph.com/rss",
    "https://cryptopotato.com/feed/",
    "https://cryptoslate.com/feed/",
    "https://cryptonews.com/news/feed/",
    "https://decrypt.co/feed",
    "https://smartliquidity.info/feed/",
    "https://finance.yahoo.com/news/rssindex",
    "https://www.cnbc.com/id/10000664/device/rss/rss.html",
    "https://time.com/nextadvisor/feed/",
    "https://benjaminion.xyz/newineth2/rss_feed.xml",
)

# Known RSS sources (for labeling / docs)
RSS_SOURCE_LABELS: dict[str, str] = {
    "thedefiant.io": "The Defiant",
    "coindesk.com": "CoinDesk",
    "cointelegraph.com": "Cointelegraph",
    "cryptopotato.com": "CryptoPotato",
    "cryptoslate.com": "CryptoSlate",
    "cryptonews.com": "CryptoNews",
    "decrypt.co": "Decrypt",
    "smartliquidity.info": "Smart Liquidity",
    "finance.yahoo.com": "Yahoo Finance",
    "cnbc.com": "CNBC",
    "time.com": "TIME NextAdvisor",
    "benjaminion.xyz": "Benjaminion Eth2",
}

PROVIDER_RSS = "rss"
PROVIDER_BYBIT_ANNOUNCEMENTS = "bybit_announcements"
PROVIDER_CRYPTO_NEWS_API = "crypto_news_api"

# Bybit announcement types that should block or elevate risk
BYBIT_HIGH_IMPACT_TYPE_KEYS: frozenset[str] = frozenset(
    {
        "new_crypto",
        "delistings",
        "maintenance",
        "latest_bybit_news",
    }
)
