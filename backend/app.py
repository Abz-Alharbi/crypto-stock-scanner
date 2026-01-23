from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
import os
from dotenv import load_dotenv
import requests
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

load_dotenv()

app = Flask(__name__)

# Get allowed origins from environment or use default
allowed_origins = os.getenv('ALLOWED_ORIGINS', '*').split(',')

CORS(app, resources={
    r"/*": {
        "origins": allowed_origins,
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Accept"],
        "supports_credentials": True
    }
})

# Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///scanner.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration - REDUCED for free tier to complete within timeout
MAX_STOCKS = 25  # Only scan top 25 stocks to stay within timeout
LOOKBACK_DAYS = 365
MIN_DATA_ROWS = 60

# Polygon.io API Key
POLYGON_API_KEY = os.getenv('POLYGON_API_KEY', '')

if POLYGON_API_KEY:
    logger.info(f"✓ POLYGON_API_KEY is set (length: {len(POLYGON_API_KEY)})")
else:
    logger.warning("✗ POLYGON_API_KEY is NOT set!")

# Rate limiting - 5 calls per minute for free tier
# With 25 stocks, this takes about 5 minutes
RATE_LIMIT_DELAY = 12.5
last_api_call = 0
api_call_lock = False

def rate_limit():
    """Enforce rate limiting for API calls"""
    global last_api_call
    now = time.time()
    elapsed = now - last_api_call
    if elapsed < RATE_LIMIT_DELAY:
        sleep_time = RATE_LIMIT_DELAY - elapsed
        logger.info(f"Rate limiting: sleeping {sleep_time:.1f}s")
        time.sleep(sleep_time)
    last_api_call = time.time()

# ============ DATABASE MODELS ============
class ScanResult(db.Model):
    __tablename__ = 'scan_results'
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(20), index=True)
    market = db.Column(db.String(10))
    timeframe = db.Column(db.String(10))
    scan_date = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    filters_achieved = db.Column(db.JSON)
    ema_50 = db.Column(db.Float)
    ema_200 = db.Column(db.Float)
    fibo_50 = db.Column(db.Float)
    macd = db.Column(db.Float)
    rsi = db.Column(db.Float)
    pattern = db.Column(db.String(50))
    last_price = db.Column(db.Float)
    volume = db.Column(db.BigInteger)

# ============ NASDAQ SYMBOLS ============
# Top 25 most liquid NASDAQ stocks for fast scanning
NASDAQ_SYMBOLS_TOP = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'AVGO', 
    'NFLX', 'AMD', 'ADBE', 'CSCO', 'INTC', 'QCOM', 'AMGN', 'SBUX',
    'PYPL', 'INTU', 'ISRG', 'BKNG', 'GILD', 'MDLZ', 'ADI', 'LRCX', 'TXN'
]

# Extended list for paid tier
NASDAQ_SYMBOLS_EXTENDED = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'AVGO', 'COST',
    'NFLX', 'AMD', 'PEP', 'ADBE', 'CSCO', 'CMCSA', 'INTC', 'TMUS', 'INTU', 'TXN',
    'QCOM', 'AMAT', 'AMGN', 'SBUX', 'ISRG', 'BKNG', 'VRTX', 'ADI', 'GILD',
    'MDLZ', 'REGN', 'LRCX', 'PYPL', 'ADP', 'PANW', 'KLAC', 'SNPS', 'CDNS', 'MELI',
    'ABNB', 'ASML', 'MNST', 'FTNT', 'MAR', 'NXPI', 'MRVL', 'ORLY', 'ADSK', 'CTAS',
    'WDAY', 'DASH', 'CHTR', 'PCAR', 'CPRT', 'AEP', 'PAYX', 'ROST', 'ODFL', 'KDP',
    'CRWD', 'FAST', 'EA', 'KHC', 'DXCM', 'CTSH', 'VRSK', 'LULU', 'GEHC', 'TTD',
    'TEAM', 'IDXX', 'BKR', 'CSGP', 'EXC', 'ZS', 'ANSS', 'BIIB', 'XEL', 'FANG',
    'DDOG', 'ILMN', 'ON', 'EBAY', 'WBD', 'MDB', 'ZM', 'WBA', 'ENPH', 'COIN',
    'ROKU', 'UBER', 'LYFT', 'MRNA', 'SNAP', 'PLTR', 'RBLX', 'SHOP', 'NET', 'MU'
]

# Use TOP list by default (faster)
NASDAQ_SYMBOLS = NASDAQ_SYMBOLS_TOP

logger.info(f"Loaded {len(NASDAQ_SYMBOLS)} NASDAQ symbols (fast mode)")

# ============ TECHNICAL INDICATORS ============
def calculate_ema(series, span):
    return series.ewm(span=span, adjust=False).mean()

def calculate_macd(df):
    ema_12 = calculate_ema(df['Close'], 12)
    ema_26 = calculate_ema(df['Close'], 26)
    return ema_12 - ema_26

def calculate_rsi(df, period=14):
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_fibonacci_50(df, lookback=60):
    recent = df.tail(lookback)
    high = recent['High'].max()
    low = recent['Low'].min()
    return low + 0.5 * (high - low)

def check_volume_spike(df):
    if len(df) < 21:
        return False
    avg_volume = df['Volume'].tail(21).iloc[:-1].mean()
    last_volume = df['Volume'].iloc[-1]
    return last_volume > (2 * avg_volume)

def detect_pattern(df):
    if len(df) < 60:
        return None
    closes = df['Close'].tail(60).values
    recent_trend = (closes[-1] - closes[-30]) / closes[-30]
    
    if recent_trend > 0.10:
        return "Bullish Trend"
    elif recent_trend < -0.10:
        return "Bearish Trend"
    return "Consolidation"

# ============ ADVANCED PATTERN DETECTION ============
def detect_advanced_patterns(df):
    patterns = []
    confidence = 0
    support = None
    resistance = None
    
    if len(df) < 60:
        return {
            'patterns': [],
            'confidence': 0,
            'support_resistance': None
        }
    
    closes = df['Close'].tail(100).values
    highs = df['High'].tail(100).values
    lows = df['Low'].tail(100).values
    
    recent_high = np.max(highs[-30:])
    recent_low = np.min(lows[-30:])
    resistance = round(float(recent_high), 2)
    support = round(float(recent_low), 2)
    
    try:
        if len(closes) >= 60:
            mid = len(closes) // 2
            left_shoulder = closes[mid-20:mid-10].max()
            head = closes[mid-10:mid+10].max()
            right_shoulder = closes[mid+10:mid+20].max()
            
            if head > left_shoulder * 1.05 and head > right_shoulder * 1.05:
                if abs(left_shoulder - right_shoulder) / left_shoulder < 0.05:
                    patterns.append("Head & Shoulders")
                    confidence = max(confidence, 75)
            
            left_trough = closes[mid-20:mid-10].min()
            head_trough = closes[mid-10:mid+10].min()
            right_trough = closes[mid+10:mid+20].min()
            
            if head_trough < left_trough * 0.95 and head_trough < right_trough * 0.95:
                if abs(left_trough - right_trough) / left_trough < 0.05:
                    patterns.append("Inverse Head & Shoulders")
                    confidence = max(confidence, 75)
    except:
        pass
    
    try:
        recent_highs = []
        recent_lows = []
        
        for i in range(10, len(closes) - 10):
            if highs[i] >= max(highs[i-5:i]) and highs[i] >= max(highs[i+1:i+6]):
                recent_highs.append((i, highs[i]))
            if lows[i] <= min(lows[i-5:i]) and lows[i] <= min(lows[i+1:i+6]):
                recent_lows.append((i, lows[i]))
        
        if len(recent_highs) >= 2:
            high1, high2 = recent_highs[-2][1], recent_highs[-1][1]
            if abs(high1 - high2) / high1 < 0.03:
                patterns.append("Double Top")
                confidence = max(confidence, 70)
        
        if len(recent_lows) >= 2:
            low1, low2 = recent_lows[-2][1], recent_lows[-1][1]
            if abs(low1 - low2) / low1 < 0.03:
                patterns.append("Double Bottom")
                confidence = max(confidence, 70)
    except:
        pass
    
    try:
        long_term_change = (closes[-1] - closes[-60]) / closes[-60]
        if long_term_change > 0.15:
            if "Bullish Trend" not in patterns:
                patterns.append("Bullish Trend")
                confidence = max(confidence, 55)
        elif long_term_change < -0.15:
            if "Bearish Trend" not in patterns:
                patterns.append("Bearish Trend")
                confidence = max(confidence, 55)
        else:
            if len(patterns) == 0:
                patterns.append("Consolidation")
                confidence = 45
    except:
        pass
    
    return {
        'patterns': patterns,
        'confidence': confidence,
        'support_resistance': {
            'support': support,
            'resistance': resistance
        } if support and resistance else None
    }

# ============ DATA FETCHING WITH POLYGON ============
def fetch_stock_data_polygon(symbol, timeframe='1d'):
    try:
        if not POLYGON_API_KEY:
            logger.error(f"{symbol}: POLYGON_API_KEY not set!")
            return None
        
        rate_limit()
        
        end_date = datetime.now()
        if timeframe == '1wk':
            start_date = end_date - timedelta(days=LOOKBACK_DAYS * 2)
            multiplier = 1
            timespan = 'week'
        else:
            start_date = end_date - timedelta(days=LOOKBACK_DAYS)
            multiplier = 1
            timespan = 'day'
        
        from_date = start_date.strftime('%Y-%m-%d')
        to_date = end_date.strftime('%Y-%m-%d')
        
        url = f"https://api.polygon.io/v2/aggs/ticker/{symbol}/range/{multiplier}/{timespan}/{from_date}/{to_date}"
        params = {
            'adjusted': 'true',
            'sort': 'asc',
            'limit': 50000,
            'apiKey': POLYGON_API_KEY
        }
        
        logger.info(f"{symbol}: Fetching from Polygon...")
        response = requests.get(url, params=params, timeout=30)
        
        if response.status_code == 403:
            logger.error(f"{symbol}: API key invalid or unauthorized")
            return None
        
        if response.status_code == 429:
            logger.warning(f"{symbol}: Rate limited, waiting 60s...")
            time.sleep(60)
            return None
        
        if response.status_code != 200:
            logger.warning(f"{symbol}: API returned status {response.status_code}")
            return None
        
        data = response.json()
        
        if data.get('status') == 'ERROR':
            logger.warning(f"{symbol}: API error - {data.get('error', 'Unknown')}")
            return None
        
        if 'results' not in data or not data['results']:
            logger.warning(f"{symbol}: No results")
            return None
        
        results = data['results']
        
        if len(results) < MIN_DATA_ROWS:
            logger.warning(f"{symbol}: Insufficient data ({len(results)} rows)")
            return None
        
        df = pd.DataFrame(results)
        
        df = df.rename(columns={
            't': 'timestamp',
            'o': 'Open',
            'h': 'High',
            'l': 'Low',
            'c': 'Close',
            'v': 'Volume'
        })
        
        df['Date'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('Date', inplace=True)
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']]
        
        logger.info(f"{symbol}: ✓ Fetched {len(df)} rows")
        return df
        
    except requests.exceptions.Timeout:
        logger.error(f"{symbol}: Request timeout")
        return None
    except Exception as e:
        logger.error(f"{symbol}: Error - {type(e).__name__}: {e}")
        return None

def fetch_stock_data(symbol, timeframe='1d'):
    return fetch_stock_data_polygon(symbol, timeframe)

# ============ FILTER EVALUATION ============
def evaluate_filters(df, selected_filters):
    try:
        results = {
            'filters_achieved': [],
            'values': {},
            'pattern': None
        }
        
        df['EMA_50'] = calculate_ema(df['Close'], 50)
        df['EMA_200'] = calculate_ema(df['Close'], 200)
        results['values']['ema_50'] = round(float(df['EMA_50'].iloc[-1]), 2)
        results['values']['ema_200'] = round(float(df['EMA_200'].iloc[-1]), 2)
        results['values']['last_price'] = round(float(df['Close'].iloc[-1]), 2)
        
        if 'ema' in selected_filters and df['EMA_50'].iloc[-1] > df['EMA_200'].iloc[-1]:
            results['filters_achieved'].append('ema')
        
        macd_series = calculate_macd(df)
        results['values']['macd'] = round(float(macd_series.iloc[-1]), 2)
        
        if 'macd' in selected_filters and macd_series.iloc[-1] > 0:
            results['filters_achieved'].append('macd')
        
        rsi_series = calculate_rsi(df)
        results['values']['rsi'] = round(float(rsi_series.iloc[-1]), 2)
        
        if 'rsi' in selected_filters and rsi_series.iloc[-1] > 50:
            results['filters_achieved'].append('rsi')
        
        fibo_level = calculate_fibonacci_50(df)
        results['values']['fibo'] = round(float(fibo_level), 2)
        
        if 'fibo' in selected_filters and df['Close'].iloc[-1] >= fibo_level:
            results['filters_achieved'].append('fibo')
        
        if 'volume' in selected_filters and check_volume_spike(df):
            results['filters_achieved'].append('volume')
        
        results['pattern'] = detect_pattern(df)
        
        return results
    except Exception as e:
        logger.error(f"Error evaluating filters: {e}")
        return None

# ============ PROCESS SYMBOL ============
def process_symbol(symbol, selected_filters, timeframe):
    try:
        df = fetch_stock_data(symbol, timeframe)
        
        if df is None:
            return None
        
        eval_result = evaluate_filters(df, selected_filters)
        
        if eval_result is None:
            return None
            
        if not eval_result['filters_achieved']:
            logger.info(f"{symbol}: No filters matched")
            return None
        
        logger.info(f"✓ {symbol}: MATCHED {eval_result['filters_achieved']}")
        
        return {
            'symbol': symbol,
            'filters': eval_result['filters_achieved'],
            'values': eval_result['values'],
            'pattern': eval_result['pattern']
        }
    except Exception as e:
        logger.error(f"{symbol}: EXCEPTION - {e}")
        return None

# ============ API ENDPOINTS ============
@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy',
        'nasdaq_symbols': len(NASDAQ_SYMBOLS),
        'polygon_configured': bool(POLYGON_API_KEY),
        'mode': 'fast (25 stocks)' if len(NASDAQ_SYMBOLS) <= 25 else 'extended'
    }), 200

@app.route('/debug')
def debug():
    return jsonify({
        'polygon_key_set': bool(POLYGON_API_KEY),
        'polygon_key_length': len(POLYGON_API_KEY) if POLYGON_API_KEY else 0,
        'polygon_key_preview': POLYGON_API_KEY[:4] + '...' if POLYGON_API_KEY and len(POLYGON_API_KEY) > 4 else 'NOT SET',
        'database_url_set': bool(os.getenv('DATABASE_URL')),
        'allowed_origins': allowed_origins,
        'symbols_count': len(NASDAQ_SYMBOLS),
        'max_stocks': MAX_STOCKS,
        'estimated_scan_time': f"{len(NASDAQ_SYMBOLS) * RATE_LIMIT_DELAY / 60:.1f} minutes"
    }), 200

@app.route('/filter', methods=['POST'])
def filter_assets():
    try:
        if not POLYGON_API_KEY:
            logger.error("POLYGON_API_KEY not configured!")
            return jsonify({
                'error': 'API key not configured',
                'hint': 'Add POLYGON_API_KEY to Railway environment variables'
            }), 500
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data received'}), 400
            
        selected_filters = data.get('filters', [])
        timeframe = data.get('timeframe', '1d')
        
        logger.info(f"=" * 60)
        logger.info(f"NEW SCAN - Filters: {selected_filters}, Timeframe: {timeframe}")
        
        if not selected_filters:
            return jsonify([]), 200
        
        symbols = NASDAQ_SYMBOLS[:MAX_STOCKS]
        estimated_time = len(symbols) * RATE_LIMIT_DELAY / 60
        
        logger.info(f"Scanning {len(symbols)} symbols (~{estimated_time:.1f} min)...")
        
        results = []
        processed = 0
        
        for symbol in symbols:
            try:
                result = process_symbol(symbol, selected_filters, timeframe)
                processed += 1
                
                if result:
                    results.append(result)
                
                if processed % 5 == 0:
                    logger.info(f"Progress: {processed}/{len(symbols)} ({len(results)} matches)")
                    
            except Exception as e:
                logger.error(f"{symbol}: Error - {e}")
        
        logger.info(f"✓ SCAN COMPLETE: {len(results)} matches from {processed} stocks")
        logger.info(f"=" * 60)
        
        # Save to database
        try:
            for result in results:
                scan_result = ScanResult(
                    symbol=result['symbol'],
                    market='NASDAQ',
                    timeframe=timeframe,
                    filters_achieved=result['filters'],
                    ema_50=result['values'].get('ema_50'),
                    ema_200=result['values'].get('ema_200'),
                    fibo_50=result['values'].get('fibo'),
                    macd=result['values'].get('macd'),
                    rsi=result['values'].get('rsi'),
                    pattern=result['pattern'],
                    last_price=result['values'].get('last_price')
                )
                db.session.add(scan_result)
            db.session.commit()
        except Exception as db_error:
            logger.warning(f"Database save failed: {db_error}")
            db.session.rollback()
        
        return jsonify(results), 200
        
    except Exception as e:
        logger.error(f"Filter endpoint error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/pattern-analysis', methods=['POST'])
def pattern_analysis():
    try:
        if not POLYGON_API_KEY:
            return jsonify({
                'patterns': [],
                'confidence': 0,
                'support_resistance': None
            }), 200
            
        data = request.get_json()
        symbol = data.get('symbol')
        timeframe = data.get('timeframe', '1d')
        
        logger.info(f"Pattern analysis for {symbol} ({timeframe})")
        
        df = fetch_stock_data(symbol, timeframe)
        
        if df is None:
            return jsonify({
                'patterns': [],
                'confidence': 0,
                'support_resistance': None
            }), 200
        
        pattern_result = detect_advanced_patterns(df)
        
        return jsonify(pattern_result), 200
        
    except Exception as e:
        logger.error(f"Pattern analysis error: {e}")
        return jsonify({
            'patterns': [],
            'confidence': 0,
            'support_resistance': None
        }), 200

@app.route('/')
def home():
    return jsonify({
        'message': 'NASDAQ Scanner API',
        'status': 'running',
        'data_source': 'Polygon.io (Massive.com)',
        'mode': 'fast (25 stocks)',
        'polygon_configured': bool(POLYGON_API_KEY),
        'endpoints': {
            'health': '/health',
            'debug': '/debug',
            'filter': '/filter (POST)',
            'pattern_analysis': '/pattern-analysis (POST)',
            'test_symbol': '/test-symbol/<symbol>'
        }
    }), 200

@app.route('/test-symbol/<symbol>')
def test_single_symbol(symbol):
    try:
        if not POLYGON_API_KEY:
            return jsonify({
                'symbol': symbol,
                'status': 'error',
                'error': 'POLYGON_API_KEY not set'
            }), 200
            
        logger.info(f"Testing symbol: {symbol}")
        
        df = fetch_stock_data(symbol, '1d')
        
        if df is None:
            return jsonify({
                'symbol': symbol,
                'status': 'failed',
                'error': 'Could not fetch data'
            }), 200
        
        result = {
            'symbol': symbol,
            'status': 'success',
            'rows': len(df),
            'date_range': f"{df.index[0]} to {df.index[-1]}",
            'last_close': float(df['Close'].iloc[-1]),
            'last_volume': int(df['Volume'].iloc[-1])
        }
        
        try:
            df['EMA_50'] = calculate_ema(df['Close'], 50)
            df['RSI'] = calculate_rsi(df)
            result['ema_50'] = round(float(df['EMA_50'].iloc[-1]), 2)
            result['rsi'] = round(float(df['RSI'].iloc[-1]), 2)
        except Exception as e:
            result['indicator_error'] = str(e)
        
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({
            'symbol': symbol,
            'status': 'error',
            'error': str(e)
        }), 500

# Initialize database
with app.app_context():
    try:
        db.create_all()
        logger.info("Database initialized")
    except Exception as e:
        logger.warning(f"Database init warning: {e}")

if __name__ == '__main__':
    logger.info(f"Loaded {len(NASDAQ_SYMBOLS)} NASDAQ symbols")
    logger.info(f"Polygon API Key configured: {bool(POLYGON_API_KEY)}")
    app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)