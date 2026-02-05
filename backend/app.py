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
import json
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

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

# ============ JSON SERIALIZATION HELPER ============
def convert_to_serializable(obj):
    """Recursively convert numpy types to native Python types for JSON serialization"""
    if isinstance(obj, dict):
        return {key: convert_to_serializable(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_to_serializable(item) for item in obj]
    elif isinstance(obj, (np.bool_, np.bool8)):
        return bool(obj)
    elif isinstance(obj, (np.integer, np.int64, np.int32, np.int16, np.int8)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64, np.float32, np.float16)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif pd.isna(obj):
        return None
    else:
        return obj

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

# ============ STOCK DATABASE FOR SEARCH ============
STOCK_DATABASE = {
    'AAPL': 'Apple Inc.',
    'MSFT': 'Microsoft Corporation',
    'GOOGL': 'Alphabet Inc. (Google)',
    'GOOG': 'Alphabet Inc. Class C',
    'AMZN': 'Amazon.com Inc.',
    'NVDA': 'NVIDIA Corporation',
    'META': 'Meta Platforms Inc. (Facebook)',
    'TSLA': 'Tesla Inc.',
    'AVGO': 'Broadcom Inc.',
    'COST': 'Costco Wholesale Corporation',
    'NFLX': 'Netflix Inc.',
    'AMD': 'Advanced Micro Devices Inc.',
    'PEP': 'PepsiCo Inc.',
    'ADBE': 'Adobe Inc.',
    'CSCO': 'Cisco Systems Inc.',
    'CMCSA': 'Comcast Corporation',
    'INTC': 'Intel Corporation',
    'TMUS': 'T-Mobile US Inc.',
    'INTU': 'Intuit Inc.',
    'TXN': 'Texas Instruments Inc.',
    'QCOM': 'Qualcomm Inc.',
    'AMAT': 'Applied Materials Inc.',
    'HON': 'Honeywell International Inc.',
    'AMGN': 'Amgen Inc.',
    'SBUX': 'Starbucks Corporation',
    'ISRG': 'Intuitive Surgical Inc.',
    'BKNG': 'Booking Holdings Inc.',
    'VRTX': 'Vertex Pharmaceuticals Inc.',
    'ADI': 'Analog Devices Inc.',
    'GILD': 'Gilead Sciences Inc.',
    'MDLZ': 'Mondelez International Inc.',
    'REGN': 'Regeneron Pharmaceuticals Inc.',
    'LRCX': 'Lam Research Corporation',
    'PYPL': 'PayPal Holdings Inc.',
    'ADP': 'Automatic Data Processing Inc.',
    'PANW': 'Palo Alto Networks Inc.',
    'KLAC': 'KLA Corporation',
    'SNPS': 'Synopsys Inc.',
    'CDNS': 'Cadence Design Systems Inc.',
    'MELI': 'MercadoLibre Inc.',
    'ABNB': 'Airbnb Inc.',
    'ASML': 'ASML Holding N.V.',
    'MNST': 'Monster Beverage Corporation',
    'FTNT': 'Fortinet Inc.',
    'MAR': 'Marriott International Inc.',
    'NXPI': 'NXP Semiconductors N.V.',
    'MRVL': 'Marvell Technology Inc.',
    'ORLY': "O'Reilly Automotive Inc.",
    'ADSK': 'Autodesk Inc.',
    'CTAS': 'Cintas Corporation',
    'WDAY': 'Workday Inc.',
    'DASH': 'DoorDash Inc.',
    'CHTR': 'Charter Communications Inc.',
    'PCAR': 'PACCAR Inc.',
    'CPRT': 'Copart Inc.',
    'AEP': 'American Electric Power Company Inc.',
    'PAYX': 'Paychex Inc.',
    'ROST': 'Ross Stores Inc.',
    'ODFL': 'Old Dominion Freight Line Inc.',
    'KDP': 'Keurig Dr Pepper Inc.',
    'CRWD': 'CrowdStrike Holdings Inc.',
    'FAST': 'Fastenal Company',
    'EA': 'Electronic Arts Inc.',
    'KHC': 'Kraft Heinz Company',
    'DXCM': 'DexCom Inc.',
    'CTSH': 'Cognizant Technology Solutions',
    'VRSK': 'Verisk Analytics Inc.',
    'LULU': 'Lululemon Athletica Inc.',
    'GEHC': 'GE HealthCare Technologies Inc.',
    'TTD': 'The Trade Desk Inc.',
    'TEAM': 'Atlassian Corporation',
    'IDXX': 'IDEXX Laboratories Inc.',
    'BKR': 'Baker Hughes Company',
    'CSGP': 'CoStar Group Inc.',
    'EXC': 'Exelon Corporation',
    'ZS': 'Zscaler Inc.',
    'ANSS': 'ANSYS Inc.',
    'BIIB': 'Biogen Inc.',
    'XEL': 'Xcel Energy Inc.',
    'FANG': 'Diamondback Energy Inc.',
    'DDOG': 'Datadog Inc.',
    'ILMN': 'Illumina Inc.',
    'ON': 'ON Semiconductor Corporation',
    'EBAY': 'eBay Inc.',
    'WBD': 'Warner Bros. Discovery Inc.',
    'MDB': 'MongoDB Inc.',
    'ZM': 'Zoom Video Communications Inc.',
    'WBA': 'Walgreens Boots Alliance Inc.',
    'ENPH': 'Enphase Energy Inc.',
    'ALGN': 'Align Technology Inc.',
    'SIRI': 'Sirius XM Holdings Inc.',
    'LCID': 'Lucid Group Inc.',
    'RIVN': 'Rivian Automotive Inc.',
    'PLUG': 'Plug Power Inc.',
    'COIN': 'Coinbase Global Inc.',
    'ROKU': 'Roku Inc.',
    'HOOD': 'Robinhood Markets Inc.',
    'UBER': 'Uber Technologies Inc.',
    'LYFT': 'Lyft Inc.',
    'MRNA': 'Moderna Inc.',
    'SNAP': 'Snap Inc.',
    'SOFI': 'SoFi Technologies Inc.',
    'CVNA': 'Carvana Co.',
    'SNOW': 'Snowflake Inc.',
    'PLTR': 'Palantir Technologies Inc.',
    'RBLX': 'Roblox Corporation',
    'SHOP': 'Shopify Inc.',
    'PINS': 'Pinterest Inc.',
    'DOCU': 'DocuSign Inc.',
    'NET': 'Cloudflare Inc.',
    'DELL': 'Dell Technologies Inc.',
    'HPQ': 'HP Inc.',
    'MU': 'Micron Technology Inc.',
    'WDC': 'Western Digital Corporation',
    'NTAP': 'NetApp Inc.',
    'STX': 'Seagate Technology Holdings',
    'SMCI': 'Super Micro Computer Inc.',
    'ANET': 'Arista Networks Inc.',
    'MCHP': 'Microchip Technology Inc.',
    'SWKS': 'Skyworks Solutions Inc.',
    'MPWR': 'Monolithic Power Systems Inc.',
    'AKAM': 'Akamai Technologies Inc.',
    'JNPR': 'Juniper Networks Inc.',
    'FFIV': 'F5 Inc.',
    'ZBRA': 'Zebra Technologies Corporation',
    'VRSN': 'VeriSign Inc.',
}

NASDAQ_SYMBOLS = list(STOCK_DATABASE.keys())

logger.info(f"Loaded {len(NASDAQ_SYMBOLS)} NASDAQ symbols")

# ============ TECHNICAL INDICATORS ============
def safe_float(value, default=0.0):
    """Safely convert value to float, handling NaN and None"""
    try:
        if pd.isna(value) or value is None:
            return default
        return float(value)
    except (ValueError, TypeError):
        return default

def safe_round(value, decimals=2, default=0.0):
    """Safely round a value, handling NaN and None"""
    try:
        if pd.isna(value) or value is None:
            return default
        return round(float(value), decimals)
    except (ValueError, TypeError):
        return default

def safe_bool(value, default=False):
    """Safely convert value to native Python bool"""
    try:
        if pd.isna(value) or value is None:
            return default
        return bool(value)
    except (ValueError, TypeError):
        return default

def safe_int(value, default=0):
    """Safely convert value to native Python int"""
    try:
        if pd.isna(value) or value is None:
            return default
        return int(value)
    except (ValueError, TypeError):
        return default

def calculate_ema(series, span):
    return series.ewm(span=span, adjust=False).mean()

def calculate_macd(df):
    ema_12 = calculate_ema(df['Close'], 12)
    ema_26 = calculate_ema(df['Close'], 26)
    macd_line = ema_12 - ema_26
    signal_line = calculate_ema(macd_line, 9)
    return macd_line, signal_line

def calculate_rsi(df, period=14):
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_fibonacci_levels(df, lookback=60):
    recent = df.tail(lookback)
    high = recent['High'].max()
    low = recent['Low'].min()
    diff = high - low
    return {
        'high': round(float(high), 2),
        'low': round(float(low), 2),
        'fib_236': round(float(high - 0.236 * diff), 2),
        'fib_382': round(float(high - 0.382 * diff), 2),
        'fib_50': round(float(high - 0.5 * diff), 2),
        'fib_618': round(float(high - 0.618 * diff), 2),
        'fib_786': round(float(high - 0.786 * diff), 2),
    }

def calculate_fibonacci_50(df, lookback=60):
    recent = df.tail(lookback)
    high = recent['High'].max()
    low = recent['Low'].min()
    return low + 0.5 * (high - low)

def calculate_bollinger_bands(df, period=20, std_dev=2):
    sma = df['Close'].rolling(window=period).mean()
    std = df['Close'].rolling(window=period).std()
    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)
    return upper, sma, lower

def calculate_atr(df, period=14):
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return true_range.rolling(window=period).mean()

def calculate_stochastic(df, k_period=14, d_period=3):
    low_min = df['Low'].rolling(window=k_period).min()
    high_max = df['High'].rolling(window=k_period).max()
    k = 100 * (df['Close'] - low_min) / (high_max - low_min)
    d = k.rolling(window=d_period).mean()
    return k, d

def check_volume_spike(df):
    if len(df) < 21:
        return False
    avg_volume = df['Volume'].tail(21).iloc[:-1].mean()
    last_volume = df['Volume'].iloc[-1]
    # Convert numpy.bool_ to native Python bool
    return bool(last_volume > (2 * avg_volume))

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
            'support_resistance': None,
            'pattern_details': []
        }
    
    closes = df['Close'].tail(100).values
    highs = df['High'].tail(100).values
    lows = df['Low'].tail(100).values
    
    recent_high = np.max(highs[-30:])
    recent_low = np.min(lows[-30:])
    resistance = round(float(recent_high), 2)
    support = round(float(recent_low), 2)
    
    pattern_details = []
    
    # Head and Shoulders
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
                    pattern_details.append({
                        'name': 'Head & Shoulders',
                        'type': 'Bearish Reversal',
                        'description': 'A bearish reversal pattern with three peaks, the middle being the highest.',
                        'signal': 'Sell',
                        'reliability': 'High'
                    })
            
            left_trough = closes[mid-20:mid-10].min()
            head_trough = closes[mid-10:mid+10].min()
            right_trough = closes[mid+10:mid+20].min()
            
            if head_trough < left_trough * 0.95 and head_trough < right_trough * 0.95:
                if abs(left_trough - right_trough) / left_trough < 0.05:
                    patterns.append("Inverse Head & Shoulders")
                    confidence = max(confidence, 75)
                    pattern_details.append({
                        'name': 'Inverse Head & Shoulders',
                        'type': 'Bullish Reversal',
                        'description': 'A bullish reversal pattern with three troughs, the middle being the lowest.',
                        'signal': 'Buy',
                        'reliability': 'High'
                    })
    except:
        pass
    
    # Double Top / Double Bottom
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
                pattern_details.append({
                    'name': 'Double Top',
                    'type': 'Bearish Reversal',
                    'description': 'Two peaks at similar price levels indicating resistance.',
                    'signal': 'Sell',
                    'reliability': 'High'
                })
        
        if len(recent_lows) >= 2:
            low1, low2 = recent_lows[-2][1], recent_lows[-1][1]
            if abs(low1 - low2) / low1 < 0.03:
                patterns.append("Double Bottom")
                confidence = max(confidence, 70)
                pattern_details.append({
                    'name': 'Double Bottom',
                    'type': 'Bullish Reversal',
                    'description': 'Two troughs at similar price levels indicating support.',
                    'signal': 'Buy',
                    'reliability': 'High'
                })
    except:
        pass
    
    # Trend Detection
    try:
        long_term_change = (closes[-1] - closes[-60]) / closes[-60]
        short_term_change = (closes[-1] - closes[-20]) / closes[-20]
        
        if long_term_change > 0.15 and short_term_change > 0:
            if "Bullish Trend" not in patterns:
                patterns.append("Bullish Trend")
                confidence = max(confidence, 60)
                pattern_details.append({
                    'name': 'Bullish Trend',
                    'type': 'Trend',
                    'description': f'Stock is up {long_term_change*100:.1f}% over 60 days.',
                    'signal': 'Hold/Buy',
                    'reliability': 'Medium'
                })
        elif long_term_change < -0.15 and short_term_change < 0:
            if "Bearish Trend" not in patterns:
                patterns.append("Bearish Trend")
                confidence = max(confidence, 60)
                pattern_details.append({
                    'name': 'Bearish Trend',
                    'type': 'Trend',
                    'description': f'Stock is down {abs(long_term_change)*100:.1f}% over 60 days.',
                    'signal': 'Hold/Sell',
                    'reliability': 'Medium'
                })
        else:
            if len(patterns) == 0:
                patterns.append("Consolidation")
                confidence = 45
                pattern_details.append({
                    'name': 'Consolidation',
                    'type': 'Neutral',
                    'description': 'Stock is moving sideways within a range.',
                    'signal': 'Wait',
                    'reliability': 'Medium'
                })
    except:
        pass
    
    # Breakout Detection
    try:
        recent_close = closes[-1]
        sma_20 = np.mean(closes[-20:])
        sma_50 = np.mean(closes[-50:]) if len(closes) >= 50 else sma_20
        
        if recent_close > resistance * 0.98 and short_term_change > 0.05:
            patterns.append("Potential Breakout")
            confidence = max(confidence, 65)
            pattern_details.append({
                'name': 'Potential Breakout',
                'type': 'Bullish',
                'description': f'Price approaching resistance at ${resistance}.',
                'signal': 'Watch for breakout',
                'reliability': 'Medium'
            })
        
        if recent_close < support * 1.02 and short_term_change < -0.05:
            patterns.append("Potential Breakdown")
            confidence = max(confidence, 65)
            pattern_details.append({
                'name': 'Potential Breakdown',
                'type': 'Bearish',
                'description': f'Price approaching support at ${support}.',
                'signal': 'Watch for breakdown',
                'reliability': 'Medium'
            })
    except:
        pass
    
    return {
        'patterns': patterns,
        'confidence': int(confidence),
        'support_resistance': {
            'support': float(support) if support else None,
            'resistance': float(resistance) if resistance else None
        } if support and resistance else None,
        'pattern_details': pattern_details
    }

# ============ DATA FETCHING WITH YFINANCE ============
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

def get_stock_info(symbol):
    """Get basic stock info from yfinance"""
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        if not info or len(info) == 0:
            raise Exception("Empty info")
        return {
            'name': info.get('longName', info.get('shortName', STOCK_DATABASE.get(symbol, 'Unknown'))),
            'sector': info.get('sector', 'N/A'),
            'industry': info.get('industry', 'N/A'),
            'market_cap': info.get('marketCap', 0),
            'pe_ratio': info.get('trailingPE', None),
            'dividend_yield': info.get('dividendYield', None),
            '52_week_high': info.get('fiftyTwoWeekHigh', None),
            '52_week_low': info.get('fiftyTwoWeekLow', None),
        }
    except Exception as e:
        logger.warning(f"Could not get stock info for {symbol}: {e}")
        return {
            'name': STOCK_DATABASE.get(symbol, 'Unknown'),
            'sector': 'N/A',
            'industry': 'N/A'
        }

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
        results['values']['ema_50'] = safe_round(df['EMA_50'].iloc[-1], 2)
        results['values']['ema_200'] = safe_round(df['EMA_200'].iloc[-1], 2)
        results['values']['last_price'] = safe_round(df['Close'].iloc[-1], 2)
        
        ema_50_val = safe_float(df['EMA_50'].iloc[-1])
        ema_200_val = safe_float(df['EMA_200'].iloc[-1])
        if 'ema' in selected_filters and ema_50_val > ema_200_val:
            results['filters_achieved'].append('ema')
        
        macd_line, signal_line = calculate_macd(df)
        macd_val = safe_float(macd_line.iloc[-1])
        results['values']['macd'] = safe_round(macd_val, 2)
        
        if 'macd' in selected_filters and macd_val > 0:
            results['filters_achieved'].append('macd')
        
        rsi_series = calculate_rsi(df)
        rsi_val = safe_float(rsi_series.iloc[-1], 50.0)
        results['values']['rsi'] = safe_round(rsi_val, 2)
        
        if 'rsi' in selected_filters and rsi_val > 50:
            results['filters_achieved'].append('rsi')
        
        fibo_level = calculate_fibonacci_50(df)
        results['values']['fibo'] = safe_round(fibo_level, 2)
        
        close_val = safe_float(df['Close'].iloc[-1])
        if 'fibo' in selected_filters and close_val >= fibo_level:
            results['filters_achieved'].append('fibo')
        
        if 'volume' in selected_filters and check_volume_spike(df):
            results['filters_achieved'].append('volume')
        
        results['pattern'] = detect_pattern(df)
        
        return results
    except Exception as e:
        logger.error(f"Error evaluating filters: {e}")
        import traceback
        traceback.print_exc()
        return None

# ============ COMPREHENSIVE ANALYSIS FOR SINGLE STOCK ============
def analyze_stock_comprehensive(df, selected_filters):
    """Full analysis for single stock search feature"""
    try:
        analysis = {
            'indicators': {},
            'filters_passed': [],
            'filters_failed': [],
            'pattern': None,
            'advanced_patterns': None,
            'fibonacci_levels': None,
            'bollinger_bands': None,
            'additional_indicators': {}
        }
        
        # Calculate all indicators
        df['EMA_20'] = calculate_ema(df['Close'], 20)
        df['EMA_50'] = calculate_ema(df['Close'], 50)
        df['EMA_200'] = calculate_ema(df['Close'], 200)
        
        ema_20 = safe_round(df['EMA_20'].iloc[-1], 2)
        ema_50 = safe_round(df['EMA_50'].iloc[-1], 2)
        ema_200 = safe_round(df['EMA_200'].iloc[-1], 2)
        last_price = safe_round(df['Close'].iloc[-1], 2)
        
        macd_line, signal_line = calculate_macd(df)
        macd_value = safe_round(macd_line.iloc[-1], 2)
        macd_signal = safe_round(signal_line.iloc[-1], 2)
        macd_histogram = safe_round(macd_line.iloc[-1] - signal_line.iloc[-1], 2)
        
        rsi_series = calculate_rsi(df)
        rsi_value = safe_round(rsi_series.iloc[-1], 2, default=50.0)
        
        fibo_levels = calculate_fibonacci_levels(df)
        fibo_50 = fibo_levels['fib_50']
        
        volume_spike = check_volume_spike(df)
        avg_volume = int(safe_float(df['Volume'].tail(20).mean(), 0))
        last_volume = int(safe_float(df['Volume'].iloc[-1], 0))
        
        # Bollinger Bands
        bb_upper, bb_middle, bb_lower = calculate_bollinger_bands(df)
        bb_upper_val = safe_round(bb_upper.iloc[-1], 2)
        bb_middle_val = safe_round(bb_middle.iloc[-1], 2)
        bb_lower_val = safe_round(bb_lower.iloc[-1], 2)
        
        # ATR
        atr = calculate_atr(df)
        atr_value = safe_round(atr.iloc[-1], 2)
        
        # Stochastic
        stoch_k, stoch_d = calculate_stochastic(df)
        stoch_k_val = safe_round(stoch_k.iloc[-1], 2, default=50.0)
        stoch_d_val = safe_round(stoch_d.iloc[-1], 2, default=50.0)
        
        # Store all indicator values - ensure all types are JSON serializable
        analysis['indicators'] = {
            'last_price': last_price,
            'ema_20': ema_20,
            'ema_50': ema_50,
            'ema_200': ema_200,
            'macd': macd_value,
            'macd_signal': macd_signal,
            'macd_histogram': macd_histogram,
            'rsi': rsi_value,
            'fibo_50': fibo_50,
            'volume_spike': bool(volume_spike),
            'avg_volume': avg_volume,
            'last_volume': last_volume,
            'stochastic_k': stoch_k_val,
            'stochastic_d': stoch_d_val,
            'atr': atr_value
        }
        
        analysis['fibonacci_levels'] = fibo_levels
        
        analysis['bollinger_bands'] = {
            'upper': bb_upper_val,
            'middle': bb_middle_val,
            'lower': bb_lower_val,
            'position': 'Above Upper' if last_price > bb_upper_val else 'Below Lower' if last_price < bb_lower_val else 'Within Bands'
        }
        
        # Filter checks - ensure all 'passed' values are native Python bool
        filter_checks = {
            'ema': {
                'name': 'EMA Crossover (50 > 200)',
                'passed': bool(ema_50 > ema_200),
                'value': f"EMA 50: {ema_50}, EMA 200: {ema_200}",
                'condition': 'EMA 50 > EMA 200'
            },
            'macd': {
                'name': 'MACD > 0',
                'passed': bool(macd_value > 0),
                'value': f"MACD: {macd_value}, Signal: {macd_signal}",
                'condition': 'MACD > 0'
            },
            'rsi': {
                'name': 'RSI > 50',
                'passed': bool(rsi_value > 50),
                'value': f"RSI: {rsi_value}",
                'condition': 'RSI > 50'
            },
            'rsi_oversold': {
                'name': 'RSI Oversold (< 30)',
                'passed': bool(rsi_value < 30),
                'value': f"RSI: {rsi_value}",
                'condition': 'RSI < 30 (Oversold - potential buy)'
            },
            'rsi_overbought': {
                'name': 'RSI Overbought (> 70)',
                'passed': bool(rsi_value > 70),
                'value': f"RSI: {rsi_value}",
                'condition': 'RSI > 70 (Overbought - potential sell)'
            },
            'fibo': {
                'name': 'Price above Fibonacci 50%',
                'passed': bool(last_price >= fibo_50),
                'value': f"Price: ${last_price}, Fibo 50%: ${fibo_50}",
                'condition': 'Price ≥ Fibonacci 50%'
            },
            'volume': {
                'name': 'Volume Spike (2x average)',
                'passed': bool(volume_spike),
                'value': f"Volume: {last_volume:,}, Avg: {avg_volume:,}",
                'condition': 'Current volume > 2x 20-day average'
            },
            'macd_crossover': {
                'name': 'MACD Bullish Crossover',
                'passed': bool(macd_value > macd_signal and macd_histogram > 0),
                'value': f"MACD: {macd_value}, Signal: {macd_signal}",
                'condition': 'MACD > Signal Line'
            },
            'bb_oversold': {
                'name': 'Below Bollinger Lower Band',
                'passed': bool(last_price < bb_lower_val),
                'value': f"Price: ${last_price}, Lower Band: ${bb_lower_val}",
                'condition': 'Price below lower Bollinger Band (oversold)'
            },
            'bb_overbought': {
                'name': 'Above Bollinger Upper Band',
                'passed': bool(last_price > bb_upper_val),
                'value': f"Price: ${last_price}, Upper Band: ${bb_upper_val}",
                'condition': 'Price above upper Bollinger Band (overbought)'
            },
            'trend_up': {
                'name': 'Uptrend (Price > EMA 20 > EMA 50)',
                'passed': bool(last_price > ema_20 and ema_20 > ema_50),
                'value': f"Price: ${last_price}, EMA20: {ema_20}, EMA50: {ema_50}",
                'condition': 'Price > EMA 20 > EMA 50'
            },
            'trend_down': {
                'name': 'Downtrend (Price < EMA 20 < EMA 50)',
                'passed': bool(last_price < ema_20 and ema_20 < ema_50),
                'value': f"Price: ${last_price}, EMA20: {ema_20}, EMA50: {ema_50}",
                'condition': 'Price < EMA 20 < EMA 50'
            }
        }
        
        # Categorize selected filters
        for filter_id in selected_filters:
            if filter_id in filter_checks:
                check = filter_checks[filter_id]
                if check['passed']:
                    analysis['filters_passed'].append({
                        'id': filter_id,
                        'name': check['name'],
                        'value': check['value'],
                        'condition': check['condition']
                    })
                else:
                    analysis['filters_failed'].append({
                        'id': filter_id,
                        'name': check['name'],
                        'value': check['value'],
                        'condition': check['condition']
                    })
        
        # Get patterns
        analysis['pattern'] = detect_pattern(df)
        analysis['advanced_patterns'] = detect_advanced_patterns(df)
        
        return analysis
        
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        import traceback
        traceback.print_exc()
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
        
        return {
            'symbol': symbol,
            'filters': eval_result['filters_achieved'],
            'values': eval_result['values'],
            'pattern': eval_result['pattern']
        }
    except Exception as e:
        logger.error(f"Error processing {symbol}: {e}")
        return None

# ============ API ENDPOINTS ============

@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy',
        'nasdaq_symbols': len(NASDAQ_SYMBOLS),
        'data_source': 'yfinance'
    }), 200

@app.route('/search-stocks', methods=['GET'])
def search_stocks():
    """Search for stocks by symbol or name"""
    query = request.args.get('q', '').upper().strip()
    
    if len(query) < 1:
        return jsonify([]), 200
    
    results = []
    for symbol, name in STOCK_DATABASE.items():
        if query in symbol or query.lower() in name.lower():
            results.append({
                'symbol': symbol,
                'name': name
            })
    
    results.sort(key=lambda x: (0 if x['symbol'] == query else 1, x['symbol']))
    
    return jsonify(results[:10]), 200

@app.route('/analyze', methods=['POST'])
def analyze_stock():
    """Analyze a single stock with its own set of filters"""
    try:
        data = request.get_json()
        symbol = data.get('symbol', '').upper().strip()
        selected_filters = data.get('filters', [])
        timeframe = data.get('timeframe', '1d')
        
        if not symbol:
            return jsonify({'error': 'Symbol is required'}), 400
        
        logger.info(f"🔍 Analyzing {symbol} with filters: {selected_filters}, timeframe: {timeframe}")
        
        # Fetch stock data
        df = fetch_stock_data(symbol, timeframe)
        
        if df is None:
            return jsonify({
                'success': False,
                'symbol': symbol,
                'error': f"Could not fetch data for {symbol}. Please check if the symbol is correct.",
                'name': STOCK_DATABASE.get(symbol, 'Unknown')
            }), 200
        
        # Get stock info
        stock_info = get_stock_info(symbol)
        stock_name = stock_info.get('name', STOCK_DATABASE.get(symbol, 'Unknown Company'))
        
        # If no filters selected, return full analysis without filter comparison
        if not selected_filters:
            # Still do full analysis
            analysis = analyze_stock_comprehensive(df, [])
            
            if analysis is None:
                return jsonify({
                    'success': False,
                    'symbol': symbol,
                    'error': 'Analysis failed'
                }), 200
            
            # Convert all numpy types to native Python types
            response_data = convert_to_serializable({
                'success': True,
                'symbol': symbol,
                'name': stock_name,
                'stock_info': stock_info,
                'message': 'Full analysis (no filters selected)',
                'status': 'info',
                'timeframe': 'Daily' if timeframe == '1d' else 'Weekly',
                'indicators': analysis['indicators'],
                'fibonacci_levels': analysis['fibonacci_levels'],
                'bollinger_bands': analysis['bollinger_bands'],
                'pattern': analysis['pattern'],
                'advanced_patterns': analysis['advanced_patterns'],
                'filters_passed': [],
                'filters_failed': []
            })
            return jsonify(response_data), 200
        
        # Perform comprehensive analysis with filters
        analysis = analyze_stock_comprehensive(df, selected_filters)
        
        if analysis is None:
            return jsonify({
                'success': False,
                'symbol': symbol,
                'error': 'Analysis failed'
            }), 200
        
        # Determine overall result
        total_filters = len(selected_filters)
        passed_filters = len(analysis['filters_passed'])
        
        if passed_filters == total_filters:
            status = 'all_passed'
            message = f"✅ {symbol} passes ALL {total_filters} selected filter(s)!"
        elif passed_filters > 0:
            status = 'partial'
            message = f"⚠️ {symbol} passes {passed_filters} of {total_filters} selected filter(s)"
        else:
            status = 'none_passed'
            message = f"❌ {symbol} does not pass any of the {total_filters} selected filter(s)"
        
        # Convert all numpy types to native Python types
        response_data = convert_to_serializable({
            'success': True,
            'symbol': symbol,
            'name': stock_name,
            'stock_info': stock_info,
            'status': status,
            'message': message,
            'timeframe': 'Daily' if timeframe == '1d' else 'Weekly',
            'indicators': analysis['indicators'],
            'fibonacci_levels': analysis['fibonacci_levels'],
            'bollinger_bands': analysis['bollinger_bands'],
            'filters_passed': analysis['filters_passed'],
            'filters_failed': analysis['filters_failed'],
            'pattern': analysis['pattern'],
            'advanced_patterns': analysis['advanced_patterns']
        })
        return jsonify(response_data), 200
        
    except Exception as e:
        logger.error(f"Analyze error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/filter', methods=['POST'])
def filter_assets():
    """Bulk scan all stocks with selected filters"""
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
                pattern=result['pattern'],
                last_price=result['values'].get('last_price')
            )
            db.session.add(scan_result)
        
        try:
            db.session.commit()
        except:
            db.session.rollback()
        
        logger.info(f"Found {len(results)} matches")
        # Convert all numpy types before returning
        return jsonify(convert_to_serializable(results)), 200
        
    except Exception as e:
        logger.error(f"Filter endpoint error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/pattern-analysis', methods=['POST'])
def pattern_analysis():
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
                'support_resistance': None,
                'pattern_details': []
            }), 200
        
        pattern_result = detect_advanced_patterns(df)
        
        logger.info(f"Found patterns for {symbol}: {pattern_result['patterns']}")
        
        # Convert all numpy types before returning
        return jsonify(convert_to_serializable(pattern_result)), 200
        
    except Exception as e:
        logger.error(f"Pattern analysis error: {e}")
        return jsonify({
            'patterns': [],
            'confidence': 0,
            'support_resistance': None,
            'pattern_details': []
        }), 200

@app.route('/')
def home():
    return jsonify({
        'message': 'NASDAQ Scanner API',
        'status': 'running',
        'data_source': 'yfinance',
        'stocks': len(NASDAQ_SYMBOLS),
        'features': ['Bulk Scan', 'Single Stock Search & Analysis', 'Pattern Detection', 'Advanced Indicators'],
        'endpoints': {
            'health': '/health',
            'search': '/search-stocks?q=AAPL',
            'analyze': '/analyze (POST) - Single stock analysis with separate filters',
            'filter': '/filter (POST) - Bulk scan all stocks',
            'pattern_analysis': '/pattern-analysis (POST)'
        }
    }), 200

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    logger.info(f"Loaded {len(NASDAQ_SYMBOLS)} NASDAQ symbols")
    logger.info(f"Stock search database: {len(STOCK_DATABASE)} companies")
    app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)