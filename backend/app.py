from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import os
from dotenv import load_dotenv
import requests

load_dotenv()

app = Flask(__name__)
import os

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

# Configuration
MAX_STOCKS = 200
LOOKBACK_DAYS = 365
MIN_DATA_ROWS = 60

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

# ============ FETCH NASDAQ SYMBOLS ============
def fetch_nasdaq_symbols_list():
    """Fetch comprehensive NASDAQ symbol list"""
    symbols = set()
    
    try:
        logger.info("Fetching NASDAQ symbols from official FTP...")
        response = requests.get(
            "ftp://ftp.nasdaqtrader.com/SymbolDirectory/nasdaqlisted.txt",
            timeout=10
        )
        lines = response.text.split('\n')
        
        for line in lines[1:]:
            if '|' in line:
                parts = line.split('|')
                symbol = parts[0].strip()
                if symbol and not any(x in symbol for x in ['^', '.', 'TEST']):
                    if len(parts) > 4 and parts[4].strip() != 'Y':
                        symbols.add(symbol)
        
        logger.info(f"Fetched {len(symbols)} symbols from NASDAQ FTP")
    except Exception as e:
        logger.warning(f"FTP fetch failed: {e}")
    
    # Top NASDAQ stocks as fallback
    top_nasdaq_stocks = [
        'AAPL', 'MSFT', 'GOOGL', 'GOOG', 'AMZN', 'NVDA', 'META', 'TSLA', 'AVGO', 'COST',
        'NFLX', 'AMD', 'PEP', 'ADBE', 'CSCO', 'CMCSA', 'INTC', 'TMUS', 'INTU', 'TXN',
        'QCOM', 'AMAT', 'HON', 'AMGN', 'SBUX', 'ISRG', 'BKNG', 'VRTX', 'ADI', 'GILD',
        'MDLZ', 'REGN', 'LRCX', 'PYPL', 'ADP', 'PANW', 'KLAC', 'SNPS', 'CDNS', 'MELI',
        'ABNB', 'ASML', 'MNST', 'FTNT', 'MAR', 'NXPI', 'MRVL', 'ORLY', 'ADSK', 'CTAS',
        'WDAY', 'DASH', 'CHTR', 'PCAR', 'CPRT', 'AEP', 'PAYX', 'ROST', 'ODFL', 'KDP',
        'CRWD', 'FAST', 'EA', 'KHC', 'DXCM', 'CTSH', 'VRSK', 'LULU', 'GEHC', 'TTD',
        'TEAM', 'IDXX', 'BKR', 'CSGP', 'EXC', 'ZS', 'ANSS', 'BIIB', 'XEL', 'FANG',
        'DDOG', 'ILMN', 'ON', 'EBAY', 'WBD', 'MDB', 'ZM', 'SGEN', 'WBA', 'ENPH',
        'ALGN', 'SIRI', 'LCID', 'RIVN', 'PLUG', 'COIN', 'ROKU', 'HOOD', 'UBER', 'LYFT',
        'MRNA', 'ZI', 'SNAP', 'SOFI', 'CVNA', 'SNOW', 'PLTR', 'RBLX', 'SHOP', 'SQ',
        'PINS', 'DOCU', 'NET', 'DELL', 'HPQ', 'MU', 'WDC', 'NTAP', 'STX', 'SMCI',
        'ANET', 'MCHP', 'SWKS', 'MPWR', 'AKAM', 'JNPR', 'FFIV', 'ZBRA', 'VRSN', 'NLOK'
    ]
    
    symbols.update(top_nasdaq_stocks)
    symbol_list = sorted(list(symbols))
    logger.info(f"Total NASDAQ symbols loaded: {len(symbol_list)}")
    return symbol_list

NASDAQ_SYMBOLS = fetch_nasdaq_symbols_list()

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
    """Detect multiple technical patterns with confidence levels"""
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
    
    # Calculate support and resistance
    recent_high = np.max(highs[-30:])
    recent_low = np.min(lows[-30:])
    resistance = round(float(recent_high), 2)
    support = round(float(recent_low), 2)
    
    # Head & Shoulders Detection
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
            
            # Inverse Head & Shoulders
            left_trough = closes[mid-20:mid-10].min()
            head_trough = closes[mid-10:mid+10].min()
            right_trough = closes[mid+10:mid+20].min()
            
            if head_trough < left_trough * 0.95 and head_trough < right_trough * 0.95:
                if abs(left_trough - right_trough) / left_trough < 0.05:
                    patterns.append("Inverse Head & Shoulders")
                    confidence = max(confidence, 75)
    except:
        pass
    
    # Double Top/Bottom Detection
    try:
        recent_highs = []
        recent_lows = []
        
        for i in range(10, len(closes) - 10):
            if highs[i] >= max(highs[i-5:i]) and highs[i] >= max(highs[i+1:i+6]):
                recent_highs.append((i, highs[i]))
            if lows[i] <= min(lows[i-5:i]) and lows[i] <= min(lows[i+1:i+6]):
                recent_lows.append((i, lows[i]))
        
        # Double Top
        if len(recent_highs) >= 2:
            high1, high2 = recent_highs[-2][1], recent_highs[-1][1]
            if abs(high1 - high2) / high1 < 0.03:
                patterns.append("Double Top")
                confidence = max(confidence, 70)
        
        # Double Bottom
        if len(recent_lows) >= 2:
            low1, low2 = recent_lows[-2][1], recent_lows[-1][1]
            if abs(low1 - low2) / low1 < 0.03:
                patterns.append("Double Bottom")
                confidence = max(confidence, 70)
        
        # Triple Top
        if len(recent_highs) >= 3:
            high1, high2, high3 = recent_highs[-3][1], recent_highs[-2][1], recent_highs[-1][1]
            avg_high = (high1 + high2 + high3) / 3
            if all(abs(h - avg_high) / avg_high < 0.03 for h in [high1, high2, high3]):
                patterns.append("Triple Top")
                confidence = max(confidence, 80)
        
        # Triple Bottom
        if len(recent_lows) >= 3:
            low1, low2, low3 = recent_lows[-3][1], recent_lows[-2][1], recent_lows[-1][1]
            avg_low = (low1 + low2 + low3) / 3
            if all(abs(l - avg_low) / avg_low < 0.03 for l in [low1, low2, low3]):
                patterns.append("Triple Bottom")
                confidence = max(confidence, 80)
    except:
        pass
    
    # Triangle Patterns
    try:
        upper_levels = [highs[i] for i in range(-30, -1) if i < 0 and i >= -len(highs)]
        lower_levels = [lows[i] for i in range(-30, -1) if i < 0 and i >= -len(lows)]
        
        if len(upper_levels) >= 10 and len(lower_levels) >= 10:
            upper_slope = np.polyfit(range(len(upper_levels)), upper_levels, 1)[0]
            lower_slope = np.polyfit(range(len(lower_levels)), lower_levels, 1)[0]
            
            if abs(upper_slope) < 0.5 and lower_slope > 1:
                patterns.append("Ascending Triangle")
                confidence = max(confidence, 65)
            elif abs(upper_slope) < 0.5 and lower_slope < -1:
                patterns.append("Descending Triangle")
                confidence = max(confidence, 65)
            elif abs(upper_slope) > 0.5 and abs(lower_slope) > 0.5:
                if (upper_slope < 0 and lower_slope > 0):
                    patterns.append("Symmetrical Triangle")
                    confidence = max(confidence, 60)
    except:
        pass
    
    # Flag Patterns
    try:
        recent_change = (closes[-1] - closes[-20]) / closes[-20]
        slope_recent = np.polyfit(range(20), closes[-20:], 1)[0]
        
        if recent_change > 0.15:
            if -0.5 < slope_recent < 0.5:
                patterns.append("Bull Flag")
                confidence = max(confidence, 70)
        elif recent_change < -0.15:
            if -0.5 < slope_recent < 0.5:
                patterns.append("Bear Flag")
                confidence = max(confidence, 70)
    except:
        pass
    
    # Cup & Handle
    try:
        if closes[-1] > closes[-30] * 0.95 and closes[-1] < closes[0] * 1.05:
            cup_low = closes[-30:-10].min()
            if cup_low < closes[0] * 0.90 and closes[-1] > cup_low * 1.05:
                patterns.append("Cup & Handle")
                confidence = max(confidence, 68)
    except:
        pass
    
    # Trend Detection
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

# ============ DATA FETCHING ============
def fetch_stock_data(symbol, timeframe='1d'):
    try:
        ticker = yf.Ticker(symbol)
        end_date = datetime.now()
        
        if timeframe == '1wk':
            start_date = end_date - timedelta(days=LOOKBACK_DAYS * 2)
        else:
            start_date = end_date - timedelta(days=LOOKBACK_DAYS)
        
        df = ticker.history(start=start_date, end=end_date, interval=timeframe, auto_adjust=True)
        
        if df.empty or len(df) < MIN_DATA_ROWS:
            return None
        
        return df
    except Exception as e:
        logger.error(f"Error fetching {symbol} ({timeframe}): {e}")
        return None

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
        if eval_result is None or not eval_result['filters_achieved']:
            return None
        
        chart_df = df.tail(90).copy()
        chart_df['EMA_50'] = calculate_ema(df['Close'], 50).tail(90)
        chart_df['EMA_200'] = calculate_ema(df['Close'], 200).tail(90)
        
        chart_data = []
        for idx, row in chart_df.iterrows():
            chart_data.append({
                'date': idx.strftime('%Y-%m-%d'),
                'price': round(float(row['Close']), 2),
                'ema50': round(float(row['EMA_50']), 2),
                'ema200': round(float(row['EMA_200']), 2)
            })
        
        return {
            'symbol': symbol,
            'filters': eval_result['filters_achieved'],
            'values': eval_result['values'],
            'pattern': eval_result['pattern'],
            'chartData': chart_data
        }
    except Exception as e:
        logger.error(f"Error processing {symbol}: {e}")
        return None

# ============ API ENDPOINTS ============
@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy',
        'nasdaq_symbols': len(NASDAQ_SYMBOLS)
    }), 200

@app.route('/filter', methods=['POST'])
def filter_assets():
    try:
        data = request.get_json()
        selected_filters = data.get('filters', [])
        timeframe = data.get('timeframe', '1d')
        
        if not selected_filters:
            return jsonify([]), 200
        
        symbols = NASDAQ_SYMBOLS[:MAX_STOCKS]
        
        logger.info(f"Scanning {len(symbols)} NASDAQ symbols with {timeframe} timeframe")
        
        results = []
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_symbol = {
                executor.submit(process_symbol, symbol, selected_filters, timeframe): symbol 
                for symbol in symbols
            }
            
            for future in as_completed(future_to_symbol):
                try:
                    result = future.result(timeout=15)
                    if result:
                        results.append(result)
                except Exception as e:
                    logger.error(f"Processing error: {e}")
        
        # Save to database
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
                pattern=result['pattern']
            )
            db.session.add(scan_result)
        
        try:
            db.session.commit()
        except:
            db.session.rollback()
        
        logger.info(f"Found {len(results)} matches")
        return jsonify(results), 200
        
    except Exception as e:
        logger.error(f"Filter endpoint error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/pattern-analysis', methods=['POST'])
def pattern_analysis():
    """Detailed pattern analysis for a specific symbol"""
    try:
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
        
        # Detect patterns
        pattern_result = detect_advanced_patterns(df)
        
        logger.info(f"Found patterns for {symbol}: {pattern_result['patterns']}")
        
        return jsonify(pattern_result), 200
        
    except Exception as e:
        logger.error(f"Pattern analysis error: {e}")
        return jsonify({
            'patterns': [],
            'confidence': 0,
            'support_resistance': None
        }), 200

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    logger.info(f"Loaded {len(NASDAQ_SYMBOLS)} NASDAQ symbols")
    app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)
