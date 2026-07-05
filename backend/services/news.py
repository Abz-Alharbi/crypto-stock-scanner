import logging
import os
import re
from datetime import datetime, timedelta

import requests

from backend.clients.polygon import polygon
from backend.services.cache import cache_get, cache_set
from backend.symbols import canonicalize_symbol

logger = logging.getLogger(__name__)

class SentimentAnalyzer:
    """Financial sentiment analyzer using FinBERT or lexicon fallback"""

    def __init__(self):
        self.model = None
        self.tokenizer = None
        self.use_finbert = False
        self._init_finbert()

    def _init_finbert(self):
        """Try to load FinBERT model. Falls back to lexicon if unavailable."""
        try:
            from transformers import AutoTokenizer, AutoModelForSequenceClassification
            import torch
            logger.info("Loading FinBERT model (first run may download ~500MB)...")
            model_name = "ProsusAI/finbert"
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
            self.model.eval()
            self.use_finbert = True
            logger.info("✓ FinBERT loaded successfully")
        except ImportError:
            logger.warning("transformers/torch not installed. Using lexicon-based sentiment.")
            logger.warning("To enable FinBERT: pip install transformers torch --break-system-packages")
            self.use_finbert = False
        except Exception as e:
            logger.warning(f"FinBERT failed to load: {e}. Using lexicon fallback.")
            self.use_finbert = False

    # ── FinBERT inference ──────────────────────────────────
    def _finbert_analyze(self, text):
        """Classify text using FinBERT. Returns (label, score)."""
        import torch
        inputs = self.tokenizer(text, return_tensors="pt", truncation=True, max_length=512, padding=True)
        with torch.no_grad():
            outputs = self.model(**inputs)
        probs = torch.nn.functional.softmax(outputs.logits, dim=-1)
        # FinBERT labels: positive=0, negative=1, neutral=2
        labels = ['positive', 'negative', 'neutral']
        scores = probs[0].tolist()
        best_idx = scores.index(max(scores))
        return labels[best_idx], round(scores[best_idx], 4)

    # ── Lexicon fallback ───────────────────────────────────
    POSITIVE_WORDS = {
        'surge', 'surges', 'surging', 'rally', 'rallies', 'gain', 'gains', 'gained',
        'rise', 'rises', 'rising', 'jump', 'jumps', 'jumped', 'soar', 'soars', 'soaring',
        'boom', 'booming', 'bullish', 'upgrade', 'upgraded', 'outperform', 'beat', 'beats',
        'record', 'high', 'profit', 'profits', 'profitable', 'growth', 'grow', 'growing',
        'strong', 'strength', 'positive', 'optimistic', 'opportunity', 'recovery', 'recover',
        'breakout', 'uptrend', 'buy', 'accumulate', 'overweight', 'momentum', 'earnings',
        'revenue', 'exceeds', 'exceeded', 'innovation', 'approve', 'approved', 'partnership',
        'expansion', 'dividend', 'buyback', 'launch', 'launches', 'success', 'successful',
    }
    NEGATIVE_WORDS = {
        'crash', 'crashes', 'crashing', 'drop', 'drops', 'dropped', 'fall', 'falls',
        'falling', 'decline', 'declines', 'declining', 'plunge', 'plunges', 'plunging',
        'slump', 'slumps', 'sink', 'sinks', 'sinking', 'tumble', 'tumbles', 'bearish',
        'downgrade', 'downgraded', 'underperform', 'miss', 'misses', 'missed', 'loss',
        'losses', 'losing', 'weak', 'weakness', 'negative', 'pessimistic', 'risk', 'risks',
        'warning', 'concern', 'concerns', 'fear', 'fears', 'recession', 'inflation',
        'layoff', 'layoffs', 'cut', 'cuts', 'sell', 'selloff', 'underweight', 'debt',
        'lawsuit', 'fraud', 'investigation', 'default', 'bankruptcy', 'crisis', 'volatile',
        'investigation', 'penalty', 'fine', 'fined', 'recall', 'shortage', 'delay',
    }

    def _lexicon_analyze(self, text):
        """Simple lexicon-based financial sentiment."""
        words = set(text.lower().split())
        pos = len(words & self.POSITIVE_WORDS)
        neg = len(words & self.NEGATIVE_WORDS)
        total = pos + neg
        if total == 0:
            return 'neutral', 0.5
        score = pos / total
        if score > 0.6:
            return 'positive', round(0.5 + score * 0.5, 4)
        elif score < 0.4:
            return 'negative', round(0.5 + (1 - score) * 0.5, 4)
        return 'neutral', round(0.5, 4)

    # ── Public method ──────────────────────────────────────
    def analyze(self, text):
        """Analyze sentiment of text. Returns dict with label and score."""
        if not text or len(text.strip()) < 10:
            return {'label': 'neutral', 'score': 0.5, 'method': 'none'}

        try:
            if self.use_finbert:
                label, score = self._finbert_analyze(text)
                return {'label': label, 'score': score, 'method': 'finbert'}
        except Exception as e:
            logger.error(f"FinBERT error: {e}")

        label, score = self._lexicon_analyze(text)
        return {'label': label, 'score': score, 'method': 'lexicon'}

    def analyze_batch(self, texts):
        """Analyze multiple texts."""
        return [self.analyze(t) for t in texts]


# Initialize sentiment analyzer
sentiment_analyzer = SentimentAnalyzer()
class NewsAggregator:
    """Fetches news from multiple free sources and merges results"""

    def __init__(self, polygon_client):
        self.polygon = polygon_client
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'MarketScannerPro/1.0'})
        self.finnhub_key = os.getenv('FINNHUB_API_KEY', '')
        self.alpha_vantage_key = os.getenv('ALPHA_VANTAGE_KEY', '')

    # ── Source 1: Polygon.io ───────────────────────────
    def _fetch_polygon(self, symbol, limit=20):
        """Polygon.io news (existing)"""
        try:
            raw = self.polygon.get_news(symbol, limit=limit)
            articles = []
            for item in raw or []:
                publisher = item.get('publisher', {})
                articles.append({
                    'headline': item.get('title', ''),
                    'summary': (item.get('description', '') or item.get('title', ''))[:500],
                    'source': publisher.get('name', 'Polygon'),
                    'source_logo': publisher.get('logo_url', ''),
                    'date': item.get('published_utc', ''),
                    'url': item.get('article_url', ''),
                    'image_url': item.get('image_url', ''),
                    'tickers': item.get('tickers', []),
                    'origin': 'polygon',
                })
            return articles
        except Exception as e:
            logger.error(f"Polygon news error: {e}")
            return []

    # ── Source 2: Finnhub (free API key) ───────────────
    def _fetch_finnhub(self, symbol, days=30):
        """Finnhub company news - free tier: 60 calls/min"""
        if not self.finnhub_key:
            return []
        try:
            to_date = datetime.now().strftime('%Y-%m-%d')
            from_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            url = f"https://finnhub.io/api/v1/company-news"
            params = {
                'symbol': symbol,
                'from': from_date,
                'to': to_date,
                'token': self.finnhub_key,
            }
            resp = self.session.get(url, params=params, timeout=15)
            if resp.status_code != 200:
                return []

            articles = []
            for item in resp.json()[:30]:
                articles.append({
                    'headline': item.get('headline', ''),
                    'summary': (item.get('summary', '') or item.get('headline', ''))[:500],
                    'source': item.get('source', 'Finnhub'),
                    'source_logo': '',
                    'date': datetime.fromtimestamp(item.get('datetime', 0)).isoformat() + 'Z' if item.get('datetime') else '',
                    'url': item.get('url', ''),
                    'image_url': item.get('image', ''),
                    'tickers': [symbol],
                    'origin': 'finnhub',
                })
            return articles
        except Exception as e:
            logger.error(f"Finnhub news error: {e}")
            return []

    # ── Source 3: Alpha Vantage News Sentiment ─────────
    def _fetch_alpha_vantage(self, symbol, limit=20):
        """Alpha Vantage NEWS_SENTIMENT - free: 25 calls/day"""
        if not self.alpha_vantage_key:
            return []
        try:
            url = "https://www.alphavantage.co/query"
            params = {
                'function': 'NEWS_SENTIMENT',
                'tickers': symbol,
                'limit': limit,
                'apikey': self.alpha_vantage_key,
            }
            resp = self.session.get(url, params=params, timeout=15)
            if resp.status_code != 200:
                return []

            data = resp.json()
            articles = []
            for item in data.get('feed', [])[:limit]:
                # Find the ticker-specific sentiment
                ticker_sentiments = item.get('ticker_sentiment', [])
                relevance = 0
                for ts in ticker_sentiments:
                    if ts.get('ticker', '').upper() == symbol:
                        relevance = float(ts.get('relevance_score', 0))
                        break

                articles.append({
                    'headline': item.get('title', ''),
                    'summary': (item.get('summary', '') or item.get('title', ''))[:500],
                    'source': item.get('source', 'Alpha Vantage'),
                    'source_logo': '',
                    'date': self._parse_av_date(item.get('time_published', '')),
                    'url': item.get('url', ''),
                    'image_url': item.get('banner_image', ''),
                    'tickers': [t.get('ticker', '') for t in ticker_sentiments],
                    'origin': 'alpha_vantage',
                    '_relevance': relevance,
                })
            return articles
        except Exception as e:
            logger.error(f"Alpha Vantage news error: {e}")
            return []

    def _parse_av_date(self, date_str):
        """Parse Alpha Vantage date format: 20240101T120000"""
        try:
            dt = datetime.strptime(date_str[:15], '%Y%m%dT%H%M%S')
            return dt.isoformat() + 'Z'
        except Exception:
            return date_str

    # ── Source 4: Google News RSS (no API key) ─────────
    def _fetch_google_rss(self, symbol, company_name=''):
        """Google News RSS feed - completely free, no limits"""
        try:
            import feedparser
        except ImportError:
            logger.warning("feedparser not installed. pip install feedparser --break-system-packages")
            return []

        articles = []
        queries = [f"{symbol} stock"]
        if company_name:
            queries.append(f"{company_name} stock market")

        for query in queries:
            try:
                rss_url = f"https://news.google.com/rss/search?q={requests.utils.quote(query)}&hl=en-US&gl=US&ceid=US:en"
                feed = feedparser.parse(rss_url)
                for entry in feed.entries[:10]:
                    # Google News wraps source in the title: "Headline - Source"
                    title = entry.get('title', '')
                    source = 'Google News'
                    if ' - ' in title:
                        parts = title.rsplit(' - ', 1)
                        title = parts[0]
                        source = parts[1] if len(parts) > 1 else 'Google News'

                    pub_date = ''
                    if entry.get('published_parsed'):
                        try:
                            from time import mktime
                            pub_date = datetime.fromtimestamp(mktime(entry.published_parsed)).isoformat() + 'Z'
                        except Exception:
                            pub_date = entry.get('published', '')

                    articles.append({
                        'headline': title,
                        'summary': entry.get('summary', title)[:500],
                        'source': source,
                        'source_logo': '',
                        'date': pub_date,
                        'url': entry.get('link', ''),
                        'image_url': '',
                        'tickers': [symbol],
                        'origin': 'google_rss',
                    })
            except Exception as e:
                logger.error(f"Google RSS error for '{query}': {e}")

        return articles

    # ── Source 5: Yahoo Finance RSS (no API key) ───────
    def _fetch_yahoo_rss(self, symbol):
        """Yahoo Finance RSS - free, no API key"""
        try:
            import feedparser
        except ImportError:
            return []

        try:
            rss_url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbol}&region=US&lang=en-US"
            feed = feedparser.parse(rss_url)
            articles = []

            for entry in feed.entries[:15]:
                pub_date = ''
                if entry.get('published_parsed'):
                    try:
                        from time import mktime
                        pub_date = datetime.fromtimestamp(mktime(entry.published_parsed)).isoformat() + 'Z'
                    except Exception:
                        pub_date = entry.get('published', '')

                articles.append({
                    'headline': entry.get('title', ''),
                    'summary': (entry.get('summary', '') or entry.get('title', ''))[:500],
                    'source': 'Yahoo Finance',
                    'source_logo': '',
                    'date': pub_date,
                    'url': entry.get('link', ''),
                    'image_url': '',
                    'tickers': [symbol],
                    'origin': 'yahoo_rss',
                })
            return articles
        except Exception as e:
            logger.error(f"Yahoo RSS error: {e}")
            return []

    # ── Source 6: MarketWatch RSS (no API key) ─────────
    def _fetch_marketwatch_rss(self, symbol):
        """MarketWatch RSS feed - free"""
        try:
            import feedparser
        except ImportError:
            return []

        try:
            rss_url = f"https://feeds.marketwatch.com/marketwatch/StockstoWatch/"
            feed = feedparser.parse(rss_url)
            articles = []

            for entry in feed.entries[:10]:
                title = entry.get('title', '')
                # Only include if symbol is mentioned
                if symbol.upper() not in title.upper():
                    continue

                pub_date = ''
                if entry.get('published_parsed'):
                    try:
                        from time import mktime
                        pub_date = datetime.fromtimestamp(mktime(entry.published_parsed)).isoformat() + 'Z'
                    except Exception:
                        pub_date = entry.get('published', '')

                articles.append({
                    'headline': title,
                    'summary': (entry.get('summary', '') or title)[:500],
                    'source': 'MarketWatch',
                    'source_logo': '',
                    'date': pub_date,
                    'url': entry.get('link', ''),
                    'image_url': '',
                    'tickers': [symbol],
                    'origin': 'marketwatch_rss',
                })
            return articles
        except Exception as e:
            logger.error(f"MarketWatch RSS error: {e}")
            return []

    # ── Deduplication ──────────────────────────────────
    def _deduplicate(self, articles):
        """Remove duplicate articles based on headline similarity"""
        seen_titles = set()
        unique = []
        for article in articles:
            # Normalize title for comparison
            norm_title = article['headline'].lower().strip()
            # Remove common prefixes
            for prefix in ['breaking:', 'update:', 'exclusive:']:
                norm_title = norm_title.replace(prefix, '').strip()
            # Use first 60 chars as key to catch near-duplicates
            key = norm_title[:60]
            if key and key not in seen_titles:
                seen_titles.add(key)
                unique.append(article)
        return unique

    # ── Main fetch method ──────────────────────────────
    def fetch_all(self, symbol, limit=30, days=30, company_name=''):
        """Fetch from all available sources, merge, deduplicate, sort"""
        all_articles = []

        # Polygon (primary - always available with API key)
        polygon_articles = self._fetch_polygon(symbol, limit=limit)
        all_articles.extend(polygon_articles)
        logger.info(f"News sources - Polygon: {len(polygon_articles)} articles")

        # Finnhub (if API key configured)
        finnhub_articles = self._fetch_finnhub(symbol, days=days)
        all_articles.extend(finnhub_articles)
        if finnhub_articles:
            logger.info(f"News sources - Finnhub: {len(finnhub_articles)} articles")

        # Alpha Vantage (if API key configured)
        av_articles = self._fetch_alpha_vantage(symbol, limit=20)
        all_articles.extend(av_articles)
        if av_articles:
            logger.info(f"News sources - Alpha Vantage: {len(av_articles)} articles")

        # RSS feeds (always free, no API key needed)
        yahoo_articles = self._fetch_yahoo_rss(symbol)
        all_articles.extend(yahoo_articles)
        logger.info(f"News sources - Yahoo RSS: {len(yahoo_articles)} articles")

        google_articles = self._fetch_google_rss(symbol, company_name)
        all_articles.extend(google_articles)
        logger.info(f"News sources - Google RSS: {len(google_articles)} articles")

        mw_articles = self._fetch_marketwatch_rss(symbol)
        all_articles.extend(mw_articles)
        if mw_articles:
            logger.info(f"News sources - MarketWatch RSS: {len(mw_articles)} articles")

        # Deduplicate
        unique_articles = self._deduplicate(all_articles)
        logger.info(f"News total: {len(all_articles)} raw → {len(unique_articles)} after dedup")

        # Sort by date (newest first)
        def parse_date(article):
            try:
                d = article.get('date', '')
                if not d:
                    return datetime.min
                return datetime.fromisoformat(d.replace('Z', '+00:00')).replace(tzinfo=None)
            except Exception:
                return datetime.min

        unique_articles.sort(key=parse_date, reverse=True)

        # Filter by date range
        cutoff = datetime.utcnow() - timedelta(days=days)
        filtered = []
        for a in unique_articles:
            dt = parse_date(a)
            if dt > cutoff or dt == datetime.min:  # Keep articles with unparseable dates too
                filtered.append(a)

        return filtered[:limit * 2]  # Return up to 2x limit for frontend filtering


news_aggregator = NewsAggregator(polygon)


def get_news(symbol, limit=30, days=30, sentiment_filter=None, source_filter=None):
    canonical = canonicalize_symbol(symbol)
    cache_key = f"news_multi:{canonical.provider_symbol}:{limit}:{days}"
    cached = cache_get(cache_key)
    if cached:
        articles = cached
    else:
        details = polygon.get_ticker_details(canonical.provider_symbol)
        company_name = details.get("name", "") if details else ""
        raw_articles = news_aggregator.fetch_all(
            canonical.provider_symbol,
            limit=limit,
            days=days,
            company_name=company_name,
        )

        if not raw_articles:
            return {
                "symbol": canonical.display_symbol,
                "raw_symbol": canonical.provider_symbol,
                "provider_symbol": canonical.provider_symbol,
                "display_symbol": canonical.display_symbol,
                "market": canonical.market,
                "canonical_symbol": canonical.to_dict(),
                "articles": [],
                "summary": {},
                "total": 0,
                "sources": [],
            }

        articles = []
        for item in raw_articles:
            analysis_text = (
                f"{item['headline']}. {item['summary']}"
                if item.get("summary") and item["summary"] != item["headline"]
                else item["headline"]
            )
            sentiment = sentiment_analyzer.analyze(analysis_text)

            summary = item.get("summary", item["headline"])
            summary = re.sub(r"<[^>]+>", "", summary).strip()
            summary = summary[:500] if summary else item["headline"]

            articles.append(
                {
                    "headline": item["headline"],
                    "summary": summary,
                    "source": item.get("source", "Unknown"),
                    "source_logo": item.get("source_logo", ""),
                    "date": item.get("date", ""),
                    "url": item.get("url", ""),
                    "image_url": item.get("image_url", ""),
                    "tickers": item.get("tickers", [symbol]),
                    "sentiment": sentiment["label"],
                    "sentiment_score": sentiment["score"],
                    "sentiment_method": sentiment["method"],
                    "news_source": item.get("origin", "unknown"),
                }
            )

        cache_set(cache_key, articles, ttl=600)

    filtered = articles
    if sentiment_filter:
        filtered = [item for item in filtered if item["sentiment"] == sentiment_filter]
    if source_filter:
        filtered = [
            item
            for item in filtered
            if source_filter.lower() in item["source"].lower()
        ]

    if articles:
        positive = sum(1 for item in articles if item["sentiment"] == "positive")
        negative = sum(1 for item in articles if item["sentiment"] == "negative")
        neutral = sum(1 for item in articles if item["sentiment"] == "neutral")
        total = len(articles)
        avg_score = sum(
            item["sentiment_score"]
            * (
                1
                if item["sentiment"] == "positive"
                else -1
                if item["sentiment"] == "negative"
                else 0
            )
            for item in articles
        ) / total

        if avg_score > 0.15:
            overall = "positive"
        elif avg_score < -0.15:
            overall = "negative"
        else:
            overall = "neutral"

        summary = {
            "overall": overall,
            "avg_score": round(avg_score, 4),
            "positive_count": positive,
            "negative_count": negative,
            "neutral_count": neutral,
            "total": total,
            "method": sentiment_analyzer.use_finbert and "finbert" or "lexicon",
        }
    else:
        summary = {
            "overall": "neutral",
            "avg_score": 0,
            "positive_count": 0,
            "negative_count": 0,
            "neutral_count": 0,
            "total": 0,
        }

    sources = sorted(set(item["source"] for item in articles))
    active_feeds = sorted(set(item.get("news_source", "unknown") for item in articles))

    return {
        "symbol": canonical.display_symbol,
        "raw_symbol": canonical.provider_symbol,
        "provider_symbol": canonical.provider_symbol,
        "display_symbol": canonical.display_symbol,
        "market": canonical.market,
        "canonical_symbol": canonical.to_dict(),
        "articles": filtered,
        "summary": summary,
        "sources": sources,
        "active_feeds": active_feeds,
        "total": len(filtered),
        "sentiment_engine": "finbert" if sentiment_analyzer.use_finbert else "lexicon",
    }


