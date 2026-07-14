import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

class TechnicalAnalysis:
    """Complete technical analysis calculations"""

    FEATURE_SERIES_VERSION = "technical-analysis-v1"

    @staticmethod
    def _ema_series(prices, period):
        """SMA-seeded EMA using the conventional 2 / (period + 1) alpha."""
        values = np.asarray(prices, dtype=float)
        result = np.full(len(values), np.nan)
        if len(values) < period:
            return result
        alpha = 2.0 / (period + 1)
        result[period - 1] = float(np.mean(values[:period]))
        for index in range(period, len(values)):
            result[index] = (
                alpha * values[index]
                + (1.0 - alpha) * result[index - 1]
            )
        return result

    @staticmethod
    def _macd_series(prices, fast=12, slow=26, signal=9):
        values = np.asarray(prices, dtype=float)
        line = TechnicalAnalysis._ema_series(values, fast) - TechnicalAnalysis._ema_series(values, slow)
        signal_line = np.full(len(values), np.nan)
        first_line_index = slow - 1
        if len(values) >= slow + signal - 1:
            valid_signal = TechnicalAnalysis._ema_series(
                line[first_line_index:], signal
            )
            signal_line[first_line_index:] = valid_signal
        return line, signal_line, line - signal_line

    @staticmethod
    def indicator_series(bars):
        """Return chart-ready series from the same formulas used by analysis.

        Values are aligned to closed provider candles.  The frontend renders
        these points directly and never recalculates decision-bearing values.
        """
        closed = [bar for bar in bars or [] if not bar.get('partial', False)]
        if not closed:
            return {
                'version': TechnicalAnalysis.FEATURE_SERIES_VERSION,
                'ema': {},
                'bollinger_bands': {},
                'macd': {},
                'rsi': [],
            }

        times = [bar['t'] for bar in closed]
        closes = np.asarray([bar['c'] for bar in closed], dtype=float)
        prices = pd.Series(closes)

        def points(values, start_index):
            return [
                {'t': times[index], 'value': float(values[index])}
                for index in range(start_index, len(times))
                if pd.notna(values[index])
            ]

        ema = {}
        for period in (9, 20, 50, 200):
            values = TechnicalAnalysis._ema_series(closes, period)
            ema[f'ema_{period}'] = points(values, period - 1)

        rolling = prices.rolling(window=20)
        middle = rolling.mean().to_numpy()
        deviation = rolling.std(ddof=0).to_numpy()
        bollinger = {
            'upper': points(middle + (2 * deviation), 19),
            'middle': points(middle, 19),
            'lower': points(middle - (2 * deviation), 19),
        }

        macd_line, signal, histogram = TechnicalAnalysis._macd_series(closes)
        macd = {
            'line': points(macd_line, 33),
            'signal': points(signal, 33),
            'histogram': points(histogram, 33),
        }

        rsi_values = np.full(len(closes), np.nan)
        if len(closes) >= 15:
            deltas = np.diff(closes)
            gains = np.where(deltas > 0, deltas, 0)
            losses = np.where(deltas < 0, -deltas, 0)
            avg_gain = float(np.mean(gains[:14]))
            avg_loss = float(np.mean(losses[:14]))
            rsi_values[14] = (
                100.0 if avg_loss == 0
                else 100 - (100 / (1 + (avg_gain / avg_loss)))
            )
            for delta_index in range(14, len(deltas)):
                avg_gain = (avg_gain * 13 + gains[delta_index]) / 14
                avg_loss = (avg_loss * 13 + losses[delta_index]) / 14
                rsi_values[delta_index + 1] = (
                    100.0 if avg_loss == 0
                    else 100 - (100 / (1 + (avg_gain / avg_loss)))
                )

        return {
            'version': TechnicalAnalysis.FEATURE_SERIES_VERSION,
            'ema': ema,
            'bollinger_bands': bollinger,
            'macd': macd,
            'rsi': points(rsi_values, 14),
        }

    @staticmethod
    def calculate_sma(prices, period):
        if len(prices) < period:
            return None
        return float(np.mean(prices[-period:]))

    @staticmethod
    def calculate_ema(prices, period):
        if len(prices) < period:
            return None
        return float(TechnicalAnalysis._ema_series(prices, period)[-1])

    @staticmethod
    def calculate_rsi(prices, period=14):
        if len(prices) < period + 1:
            return None
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

        avg_gain = np.mean(gains[:period])
        avg_loss = np.mean(losses[:period])

        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return float(100 - (100 / (1 + rs)))

    @staticmethod
    def calculate_macd(prices, fast=12, slow=26, signal=9):
        if len(prices) < slow + signal - 1:
            return None, None, None
        macd_line, signal_line, histogram = TechnicalAnalysis._macd_series(
            prices, fast, slow, signal
        )
        return (
            float(macd_line[-1]),
            float(signal_line[-1]),
            float(histogram[-1]),
        )

    @staticmethod
    def calculate_bollinger_bands(prices, period=20, std_dev=2):
        if len(prices) < period:
            return None, None, None
        series = pd.Series(prices[-period:])
        middle = float(series.mean())
        std = float(series.std(ddof=0))
        upper = middle + (std_dev * std)
        lower = middle - (std_dev * std)
        return upper, middle, lower

    @staticmethod
    def calculate_stochastic(highs, lows, closes, k_period=14, d_period=3):
        if len(closes) < k_period:
            return None, None
        high_max = max(highs[-k_period:])
        low_min = min(lows[-k_period:])
        if high_max == low_min:
            return 50.0, 50.0
        k = ((closes[-1] - low_min) / (high_max - low_min)) * 100

        # Simple %D as SMA of recent %K values
        k_values = []
        for i in range(min(d_period, len(closes) - k_period + 1)):
            idx = len(closes) - 1 - i
            h = max(highs[max(0, idx - k_period + 1):idx + 1])
            low = min(lows[max(0, idx - k_period + 1):idx + 1])
            if h != low:
                k_values.append(((closes[idx] - low) / (h - low)) * 100)
        d = np.mean(k_values) if k_values else k
        return float(k), float(d)

    @staticmethod
    def calculate_fibonacci_levels(prices, highs=None, lows=None):
        """
        Comprehensive Fibonacci analysis: retracements, extensions, zones, and trend detection.
        Uses swing high/low detection for more accurate pivot points.
        """
        if len(prices) < 20:
            return None

        lookback = min(120, len(prices))
        price_slice = prices[-lookback:]
        last_price = float(prices[-1])

        # ── Detect swing high/low (smarter than simple min/max) ──
        swing_high = max(price_slice)
        swing_low = min(price_slice)
        swing_high_idx = list(price_slice).index(swing_high)
        swing_low_idx = list(price_slice).index(swing_low)

        diff = swing_high - swing_low
        if diff == 0:
            return None

        # Determine trend direction: uptrend if low came before high
        is_uptrend = swing_low_idx < swing_high_idx

        # ── Retracement Levels (price pulling back within the move) ──
        # In uptrend: measured from low to high, levels are where pullbacks find support
        # In downtrend: measured from high to low, levels are where bounces find resistance
        retracements = {}
        retrace_percentages = {
            '0':     0.0,     # Start of move
            '14_6':  0.146,   # Shallow pullback (sqrt of 0.236)
            '23_6':  0.236,   # Shallow pullback
            '38_2':  0.382,   # KEY — most common first pullback level
            '50_0':  0.500,   # KEY — psychological midpoint
            '61_8':  0.618,   # KEY — golden ratio, strongest retracement
            '70_7':  0.707,   # Secondary level (sqrt of 0.5)
            '78_6':  0.786,   # Deep retracement (sqrt of 0.618)
            '88_6':  0.886,   # Very deep retracement (sqrt of 0.786)
            '100':   1.0,     # Full retracement
        }

        for key, pct in retrace_percentages.items():
            if is_uptrend:
                # Uptrend retracement: support levels below the high
                retracements[f'retrace_{key}'] = float(swing_high - pct * diff)
            else:
                # Downtrend retracement: resistance levels above the low
                retracements[f'retrace_{key}'] = float(swing_low + pct * diff)

        # ── Extension Levels (price extending beyond the move) ──
        extensions = {}
        ext_percentages = {
            '127_2':  1.272,   # KEY — first major extension target
            '141_4':  1.414,   # sqrt(2) extension
            '161_8':  1.618,   # KEY — golden ratio extension (most important)
            '200_0':  2.0,     # Double the move
            '227_2':  2.272,   # Extended target
            '261_8':  2.618,   # KEY — major extension target
            '314_6':  3.146,   # Rare extended target
            '423_6':  4.236,   # Extreme extension
        }

        for key, pct in ext_percentages.items():
            if is_uptrend:
                # Uptrend extensions: targets above the high
                extensions[f'ext_{key}'] = float(swing_low + pct * diff)
            else:
                # Downtrend extensions: targets below the low
                extensions[f'ext_{key}'] = float(swing_high - pct * diff)

        # ── Classify all levels as support/resistance relative to current price ──
        all_levels = {}
        all_levels.update(retracements)
        all_levels.update(extensions)

        supports = []
        resistances = []
        for key, val in sorted(all_levels.items(), key=lambda x: x[1]):
            if val < last_price:
                supports.append({'key': key, 'price': round(val, 2)})
            elif val > last_price:
                resistances.append({'key': key, 'price': round(val, 2)})

        nearest_support = supports[-1]['price'] if supports else None
        nearest_resistance = resistances[0]['price'] if resistances else None

        # ── Fibonacci Zones (confluences where levels cluster) ──
        # When multiple fib levels are close together, they form strong S/R zones
        all_prices = sorted([v for v in all_levels.values()])
        zones = []
        zone_threshold = diff * 0.015  # Levels within 1.5% of range are a cluster
        i = 0
        while i < len(all_prices):
            cluster = [all_prices[i]]
            j = i + 1
            while j < len(all_prices) and all_prices[j] - all_prices[i] < zone_threshold:
                cluster.append(all_prices[j])
                j += 1
            if len(cluster) >= 2:
                zone_mid = round(sum(cluster) / len(cluster), 2)
                zone_low = round(min(cluster), 2)
                zone_high = round(max(cluster), 2)
                zone_type = 'support' if zone_mid < last_price else 'resistance'
                zones.append({
                    'mid': zone_mid,
                    'low': zone_low,
                    'high': zone_high,
                    'strength': len(cluster),
                    'type': zone_type,
                })
            i = j

        # ── Price position analysis ──
        # Where is current price relative to key levels?
        retrace_pct = round(((swing_high - last_price) / diff) * 100, 1) if is_uptrend else round(((last_price - swing_low) / diff) * 100, 1)

        # Determine which zone the price is in
        if retrace_pct < 23.6:
            price_zone = 'near_high'
            zone_desc = 'Near swing high — minimal retracement'
        elif retrace_pct < 38.2:
            price_zone = 'shallow_retrace'
            zone_desc = 'Shallow pullback zone (23.6-38.2%)'
        elif retrace_pct < 50:
            price_zone = 'moderate_retrace'
            zone_desc = 'Moderate pullback zone (38.2-50%)'
        elif retrace_pct < 61.8:
            price_zone = 'golden_zone'
            zone_desc = 'Golden pocket zone (50-61.8%) — highest probability reversal area'
        elif retrace_pct < 78.6:
            price_zone = 'deep_retrace'
            zone_desc = 'Deep retracement zone (61.8-78.6%)'
        elif retrace_pct < 100:
            price_zone = 'very_deep'
            zone_desc = 'Very deep retracement (78.6-100%) — trend may be failing'
        else:
            price_zone = 'beyond_retrace'
            zone_desc = 'Beyond full retracement — previous trend invalidated'

        return {
            # ── Key retracement levels ──
            'level_0':     retracements.get('retrace_0'),
            'level_146':   retracements.get('retrace_14_6'),
            'level_236':   retracements.get('retrace_23_6'),
            'level_382':   retracements.get('retrace_38_2'),
            'level_500':   retracements.get('retrace_50_0'),
            'level_618':   retracements.get('retrace_61_8'),
            'level_707':   retracements.get('retrace_70_7'),
            'level_786':   retracements.get('retrace_78_6'),
            'level_886':   retracements.get('retrace_88_6'),
            'level_100':   retracements.get('retrace_100'),

            # ── Extension levels ──
            'ext_1272':    extensions.get('ext_127_2'),
            'ext_1414':    extensions.get('ext_141_4'),
            'ext_1618':    extensions.get('ext_161_8'),
            'ext_2000':    extensions.get('ext_200_0'),
            'ext_2272':    extensions.get('ext_227_2'),
            'ext_2618':    extensions.get('ext_261_8'),
            'ext_3146':    extensions.get('ext_314_6'),
            'ext_4236':    extensions.get('ext_423_6'),

            # ── Swing points ──
            'swing_high':  float(swing_high),
            'swing_low':   float(swing_low),
            'trend':       'uptrend' if is_uptrend else 'downtrend',
            'range':       round(float(diff), 2),
            'range_pct':   round((diff / swing_low) * 100, 2),

            # ── Nearest levels to price ──
            'nearest_support':    nearest_support,
            'nearest_resistance': nearest_resistance,
            'current_price':      last_price,

            # ── Price position ──
            'retracement_pct':    retrace_pct,
            'price_zone':         price_zone,
            'price_zone_desc':    zone_desc,

            # ── Confluence zones ──
            'zones':              zones,
            'supports':           supports[-5:],     # 5 nearest supports
            'resistances':        resistances[:5],    # 5 nearest resistances
        }

    @staticmethod
    def calculate_atr(highs, lows, closes, period=14):
        """Calculate Average True Range"""
        if len(closes) < period + 1:
            return None
        true_ranges = []
        for i in range(1, len(closes)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1])
            )
            true_ranges.append(tr)
        if len(true_ranges) < period:
            return None
        # Wilder's smoothing
        atr = np.mean(true_ranges[:period])
        for i in range(period, len(true_ranges)):
            atr = (atr * (period - 1) + true_ranges[i]) / period
        return float(atr)

    @staticmethod
    def find_swing_levels(highs, lows, closes, lookback=20):
        """Find recent swing high/low support and resistance levels"""
        if len(closes) < lookback:
            lookback = len(closes)

        recent_highs = highs[-lookback:]
        recent_lows = lows[-lookback:]
        last_price = closes[-1]

        # Find local swing highs and lows (peaks and troughs)
        swing_highs = []
        swing_lows = []
        for i in range(2, len(recent_highs) - 2):
            if recent_highs[i] > recent_highs[i-1] and recent_highs[i] > recent_highs[i-2] and \
               recent_highs[i] > recent_highs[i+1] and recent_highs[i] > recent_highs[i+2]:
                swing_highs.append(recent_highs[i])
            if recent_lows[i] < recent_lows[i-1] and recent_lows[i] < recent_lows[i-2] and \
               recent_lows[i] < recent_lows[i+1] and recent_lows[i] < recent_lows[i+2]:
                swing_lows.append(recent_lows[i])

        # Fallback to simple min/max if no swings found
        if not swing_highs:
            swing_highs = [max(recent_highs)]
        if not swing_lows:
            swing_lows = [min(recent_lows)]

        supports = sorted([level for level in swing_lows if level < last_price], reverse=True)
        resistances = sorted([r for r in swing_highs if r > last_price])

        return supports, resistances

    @staticmethod
    def calculate_trade_setup(closes, highs, lows, opens, volumes, indicators, fib_levels, overall_signal, candle_patterns, chart_patterns):
        """Calculate target price, stop loss, risk/reward, and trade recommendation"""
        last_price = closes[-1]
        atr = TechnicalAnalysis.calculate_atr(highs, lows, closes)
        supports, resistances = TechnicalAnalysis.find_swing_levels(highs, lows, closes, lookback=40)

        if atr is None or atr == 0:
            return None

        atr_pct = (atr / last_price) * 100

        # ── Determine trade direction ──────────────────
        if overall_signal == 'bullish':
            direction = 'long'
        elif overall_signal == 'bearish':
            direction = 'short'
        else:
            direction = 'neutral'

        # ── Calculate Stop Loss ────────────────────────
        if direction == 'long':
            # Use nearest support or 2x ATR below entry, whichever is tighter
            atr_stop = last_price - (2.0 * atr)
            swing_stop = supports[0] - (0.005 * last_price) if supports else atr_stop  # 0.5% below support
            stop_loss = max(atr_stop, swing_stop)  # Take the tighter (higher) stop
            # Don't let stop be too close (min 0.5% away)
            if (last_price - stop_loss) / last_price < 0.005:
                stop_loss = last_price * 0.995
        elif direction == 'short':
            atr_stop = last_price + (2.0 * atr)
            swing_stop = resistances[0] + (0.005 * last_price) if resistances else atr_stop
            stop_loss = min(atr_stop, swing_stop)
            if (stop_loss - last_price) / last_price < 0.005:
                stop_loss = last_price * 1.005
        else:
            # Neutral: use ATR-based symmetric stops
            stop_loss = last_price - (1.5 * atr)

        # ── Calculate Target Prices (3 levels) ─────────
        risk = abs(last_price - stop_loss)

        if direction == 'long':
            target_1 = last_price + (risk * 1.5)  # 1.5:1 R:R
            target_2 = last_price + (risk * 2.5)  # 2.5:1 R:R
            target_3 = last_price + (risk * 4.0)  # 4:1 R:R (stretch)

            # Adjust targets to nearest resistance/fib levels if available
            if resistances:
                if resistances[0] > last_price + risk:
                    target_1 = resistances[0]
                if len(resistances) > 1 and resistances[1] > target_1:
                    target_2 = resistances[1]

            # Use Fibonacci extension levels for smarter targets
            if fib_levels:
                ext_1272 = fib_levels.get('ext_1272')
                ext_1618 = fib_levels.get('ext_1618')
                ext_2618 = fib_levels.get('ext_2618')

                # T1: nearest resistance or 127.2% extension
                if ext_1272 and ext_1272 > last_price + risk * 0.8:
                    target_1 = max(target_1, ext_1272)
                elif fib_levels.get('nearest_resistance'):
                    fib_r = fib_levels['nearest_resistance']
                    if fib_r > last_price + risk * 0.8:
                        target_1 = max(target_1, fib_r)

                # T2: 161.8% extension
                if ext_1618 and ext_1618 > target_1:
                    target_2 = ext_1618

                # T3: 261.8% extension
                if ext_2618 and ext_2618 > target_2:
                    target_3 = ext_2618

        elif direction == 'short':
            target_1 = last_price - (risk * 1.5)
            target_2 = last_price - (risk * 2.5)
            target_3 = last_price - (risk * 4.0)

            if supports:
                if supports[0] < last_price - risk:
                    target_1 = supports[0]
                if len(supports) > 1 and supports[1] < target_1:
                    target_2 = supports[1]

            # Use Fibonacci extension levels for short targets
            if fib_levels:
                ext_1272 = fib_levels.get('ext_1272')
                ext_1618 = fib_levels.get('ext_1618')
                ext_2618 = fib_levels.get('ext_2618')

                if ext_1272 and ext_1272 < last_price - risk * 0.8:
                    target_1 = min(target_1, ext_1272)
                elif fib_levels.get('nearest_support'):
                    fib_s = fib_levels['nearest_support']
                    if fib_s < last_price - risk * 0.8:
                        target_1 = min(target_1, fib_s)

                if ext_1618 and ext_1618 < target_1:
                    target_2 = ext_1618
                if ext_2618 and ext_2618 < target_2:
                    target_3 = ext_2618
        else:
            target_1 = last_price + (risk * 1.5)
            target_2 = last_price + (risk * 2.5)
            target_3 = last_price + (risk * 4.0)

        # ── Risk/Reward Ratios ─────────────────────────
        rr_1 = round(abs(target_1 - last_price) / risk, 2) if risk > 0 else 0
        rr_2 = round(abs(target_2 - last_price) / risk, 2) if risk > 0 else 0
        rr_3 = round(abs(target_3 - last_price) / risk, 2) if risk > 0 else 0

        # ── Potential Gain/Loss % ──────────────────────
        potential_gain_pct = round(abs(target_1 - last_price) / last_price * 100, 2)
        potential_loss_pct = round(abs(last_price - stop_loss) / last_price * 100, 2)

        # ── Confidence Score (0-100) ───────────────────
        confidence = 50  # Base
        rsi = indicators.get('rsi')
        macd_data = indicators.get('macd', {})
        ema_data = indicators.get('ema', {})
        bb_data = indicators.get('bollinger_bands', {})
        stoch_data = indicators.get('stochastic', {})

        if direction == 'long':
            if rsi and rsi < 35:
                confidence += 10
            if rsi and rsi < 25:
                confidence += 5
            if macd_data.get('histogram') and macd_data['histogram'] > 0:
                confidence += 8
            if ema_data.get('ema_50') and ema_data.get('ema_200') and ema_data['ema_50'] > ema_data['ema_200']:
                confidence += 10
            if bb_data.get('lower') and last_price <= bb_data['lower'] * 1.01:
                confidence += 7
            if stoch_data.get('k') and stoch_data['k'] < 25:
                confidence += 5
            if any(p['type'] == 'bullish' for p in candle_patterns):
                confidence += 8
            if any(p['type'] == 'bullish' for p in chart_patterns):
                confidence += 10
            # Volume confirmation
            if len(volumes) >= 20:
                avg_vol = np.mean(volumes[-20:])
                if volumes[-1] > avg_vol * 1.5:
                    confidence += 7
        elif direction == 'short':
            if rsi and rsi > 65:
                confidence += 10
            if rsi and rsi > 75:
                confidence += 5
            if macd_data.get('histogram') and macd_data['histogram'] < 0:
                confidence += 8
            if ema_data.get('ema_50') and ema_data.get('ema_200') and ema_data['ema_50'] < ema_data['ema_200']:
                confidence += 10
            if bb_data.get('upper') and last_price >= bb_data['upper'] * 0.99:
                confidence += 7
            if stoch_data.get('k') and stoch_data['k'] > 75:
                confidence += 5
            if any(p['type'] == 'bearish' for p in candle_patterns):
                confidence += 8
            if any(p['type'] == 'bearish' for p in chart_patterns):
                confidence += 10
            if len(volumes) >= 20:
                avg_vol = np.mean(volumes[-20:])
                if volumes[-1] > avg_vol * 1.5:
                    confidence += 7

        # ── Fibonacci position bonus ──────────────────────
        if fib_levels:
            fib_zone = fib_levels.get('price_zone', '')
            fib_trend = fib_levels.get('trend', '')
            if direction == 'long' and fib_zone == 'golden_zone' and fib_trend == 'uptrend':
                confidence += 12  # Golden pocket + uptrend = high conviction
            elif direction == 'long' and fib_zone in ('moderate_retrace', 'golden_zone'):
                confidence += 8   # Good pullback zone
            elif direction == 'long' and fib_zone == 'shallow_retrace' and fib_trend == 'uptrend':
                confidence += 6   # Strong trend, shallow dip
            elif direction == 'short' and fib_zone == 'golden_zone' and fib_trend == 'downtrend':
                confidence += 12
            elif direction == 'short' and fib_zone in ('near_high', 'shallow_retrace') and fib_trend == 'downtrend':
                confidence += 8
            # Confluence zone bonus
            if fib_levels.get('zones'):
                price = fib_levels.get('current_price', last_price)
                for zone in fib_levels['zones']:
                    if zone['strength'] >= 3 and abs(price - zone['mid']) / price < 0.02:
                        confidence += 8  # Strong confluence
                        break
                    elif zone['strength'] >= 2 and abs(price - zone['mid']) / price < 0.02:
                        confidence += 5
                        break

        confidence = min(confidence, 98)  # Cap at 98

        # ── Trade Action Summary ───────────────────────
        if direction == 'long':
            if confidence >= 75:
                action = 'Strong Buy'
            elif confidence >= 60:
                action = 'Buy'
            else:
                action = 'Weak Buy'
        elif direction == 'short':
            if confidence >= 75:
                action = 'Strong Sell'
            elif confidence >= 60:
                action = 'Sell'
            else:
                action = 'Weak Sell'
        else:
            action = 'Hold / Wait'

        # ── Key Support & Resistance Levels ────────────
        key_supports = []
        key_resistances = []

        # Add swing levels
        for s in supports[:3]:
            key_supports.append({'price': round(s, 2), 'type': 'swing_low'})
        for r in resistances[:3]:
            key_resistances.append({'price': round(r, 2), 'type': 'swing_high'})

        # Add EMA levels as dynamic S/R
        for ema_key, ema_name in [('ema_50', 'EMA 50'), ('ema_200', 'EMA 200')]:
            ema_val = ema_data.get(ema_key)
            if ema_val:
                entry = {'price': round(ema_val, 2), 'type': ema_name}
                if ema_val < last_price:
                    key_supports.append(entry)
                else:
                    key_resistances.append(entry)

        # Add Fibonacci levels
        if fib_levels:
            fib_entries = [
                ('level_146', 'Fib 14.6%'), ('level_236', 'Fib 23.6%'),
                ('level_382', 'Fib 38.2%'), ('level_500', 'Fib 50%'),
                ('level_618', 'Fib 61.8%'), ('level_707', 'Fib 70.7%'),
                ('level_786', 'Fib 78.6%'), ('level_886', 'Fib 88.6%'),
                ('ext_1272', 'Fib Ext 127.2%'), ('ext_1618', 'Fib Ext 161.8%'),
                ('ext_2000', 'Fib Ext 200%'), ('ext_2618', 'Fib Ext 261.8%'),
            ]
            for fib_key, fib_name in fib_entries:
                fib_val = fib_levels.get(fib_key)
                if fib_val:
                    entry = {'price': round(fib_val, 2), 'type': fib_name}
                    if fib_val < last_price:
                        key_supports.append(entry)
                    else:
                        key_resistances.append(entry)

        # Sort and deduplicate
        key_supports = sorted(key_supports, key=lambda x: x['price'], reverse=True)[:5]
        key_resistances = sorted(key_resistances, key=lambda x: x['price'])[:5]

        return {
            'direction': direction,
            'action': action,
            'confidence': confidence,
            'entry_price': round(last_price, 2),
            'stop_loss': round(stop_loss, 2),
            'targets': {
                't1': {'price': round(target_1, 2), 'rr': rr_1, 'label': 'Conservative'},
                't2': {'price': round(target_2, 2), 'rr': rr_2, 'label': 'Moderate'},
                't3': {'price': round(target_3, 2), 'rr': rr_3, 'label': 'Aggressive'},
            },
            'risk_reward': rr_1,
            'potential_gain_pct': potential_gain_pct,
            'potential_loss_pct': potential_loss_pct,
            'atr': round(atr, 2),
            'atr_pct': round(atr_pct, 2),
            'support_levels': key_supports,
            'resistance_levels': key_resistances,
            'fib_position': {
                'zone': fib_levels.get('price_zone', '') if fib_levels else '',
                'zone_desc': fib_levels.get('price_zone_desc', '') if fib_levels else '',
                'retracement_pct': fib_levels.get('retracement_pct') if fib_levels else None,
                'trend': fib_levels.get('trend', '') if fib_levels else '',
            } if fib_levels else None,
        }

    @staticmethod
    def detect_candlestick_patterns(opens, highs, lows, closes):
        """Detect Japanese candlestick patterns"""
        patterns = []
        if len(closes) < 3:
            return patterns

        o, h, low, c = opens[-1], highs[-1], lows[-1], closes[-1]
        body = abs(c - o)
        total_range = h - low if h != low else 0.0001
        upper_shadow = h - max(o, c)
        lower_shadow = min(o, c) - low

        # Doji
        if body / total_range < 0.1:
            patterns.append({'pattern': 'Doji', 'type': 'neutral', 'strength': 'medium'})

        # Hammer (bullish)
        if lower_shadow > body * 2 and upper_shadow < body * 0.5 and c > o:
            patterns.append({'pattern': 'Hammer', 'type': 'bullish', 'strength': 'strong'})

        # Inverted Hammer
        if upper_shadow > body * 2 and lower_shadow < body * 0.5 and c > o:
            patterns.append({'pattern': 'Inverted Hammer', 'type': 'bullish', 'strength': 'medium'})

        # Shooting Star (bearish)
        if upper_shadow > body * 2 and lower_shadow < body * 0.5 and c < o:
            patterns.append({'pattern': 'Shooting Star', 'type': 'bearish', 'strength': 'strong'})

        # Engulfing patterns (need 2 candles)
        if len(closes) >= 2:
            prev_o, prev_c = opens[-2], closes[-2]
            # Bullish engulfing
            if prev_c < prev_o and c > o and o <= prev_c and c >= prev_o:
                patterns.append({'pattern': 'Bullish Engulfing', 'type': 'bullish', 'strength': 'strong'})
            # Bearish engulfing
            if prev_c > prev_o and c < o and o >= prev_c and c <= prev_o:
                patterns.append({'pattern': 'Bearish Engulfing', 'type': 'bearish', 'strength': 'strong'})

        # Morning Star (need 3 candles)
        if len(closes) >= 3:
            o1, c1 = opens[-3], closes[-3]
            o2, c2 = opens[-2], closes[-2]
            if c1 < o1 and abs(c2 - o2) < abs(c1 - o1) * 0.3 and c > o and c > (o1 + c1) / 2:
                patterns.append({'pattern': 'Morning Star', 'type': 'bullish', 'strength': 'strong'})

        # Evening Star (need 3 candles)
        if len(closes) >= 3:
            o1, c1 = opens[-3], closes[-3]
            o2, c2 = opens[-2], closes[-2]
            if c1 > o1 and abs(c2 - o2) < abs(c1 - o1) * 0.3 and c < o and c < (o1 + c1) / 2:
                patterns.append({'pattern': 'Evening Star', 'type': 'bearish', 'strength': 'strong'})

        return patterns

    @staticmethod
    def detect_chart_patterns(closes, window=60):
        """Detect major chart patterns"""
        patterns = []
        if len(closes) < window:
            return patterns

        data = closes[-window:]
        mid = len(data) // 2

        # Double Bottom
        first_half_min = min(data[:mid])
        second_half_min = min(data[mid:])
        peak_between = max(data[mid - 5:mid + 5]) if mid >= 5 else max(data)
        if abs(first_half_min - second_half_min) / first_half_min < 0.03 and peak_between > first_half_min * 1.03:
            patterns.append({'pattern': 'Double Bottom', 'type': 'bullish', 'strength': 'strong'})

        # Double Top
        first_half_max = max(data[:mid])
        second_half_max = max(data[mid:])
        trough_between = min(data[mid - 5:mid + 5]) if mid >= 5 else min(data)
        if abs(first_half_max - second_half_max) / first_half_max < 0.03 and trough_between < first_half_max * 0.97:
            patterns.append({'pattern': 'Double Top', 'type': 'bearish', 'strength': 'strong'})

        # Ascending Triangle
        recent = data[-20:]
        highs_stable = (max(recent) - min(recent[-5:])) / max(recent) < 0.02
        lows_rising = all(recent[i] >= recent[i - 3] * 0.99 for i in range(3, len(recent)) if i < len(recent))
        if highs_stable and lows_rising:
            patterns.append({'pattern': 'Ascending Triangle', 'type': 'bullish', 'strength': 'medium'})

        # Descending Triangle
        # Use section envelopes as close-price pivots. A descending triangle
        # needs resistance to fall toward support while support itself remains
        # materially flatter; a uniform downtrend has similar slopes and must
        # not qualify.
        sections = np.array_split(np.asarray(recent, dtype=float), 4)
        resistance = np.asarray([section.max() for section in sections])
        support = np.asarray([section.min() for section in sections])
        section_indexes = np.arange(len(sections), dtype=float)
        price_scale = float(np.mean(recent))
        resistance_slope = float(np.polyfit(section_indexes, resistance, 1)[0])
        support_slope = float(np.polyfit(section_indexes, support, 1)[0])
        normalized_resistance_slope = resistance_slope / price_scale if price_scale else 0
        normalized_support_range = (
            float(support.max() - support.min()) / price_scale if price_scale else 0
        )
        initial_spread = float(resistance[0] - support[0])
        final_spread = float(resistance[-1] - support[-1])

        resistance_falling = normalized_resistance_slope <= -0.002
        support_relatively_flat = (
            abs(support_slope) <= abs(resistance_slope) * 0.35
            and normalized_support_range <= 0.015
        )
        converging = initial_spread > 0 and 0 < final_spread <= initial_spread * 0.75
        if resistance_falling and support_relatively_flat and converging:
            patterns.append({'pattern': 'Descending Triangle', 'type': 'bearish', 'strength': 'medium'})

        # Bullish Flag
        if len(data) >= 30:
            pole = data[-30:-15]
            flag = data[-15:]
            pole_gain = (pole[-1] - pole[0]) / pole[0] if pole[0] != 0 else 0
            flag_range = (max(flag) - min(flag)) / max(flag) if max(flag) != 0 else 0
            if pole_gain > 0.05 and flag_range < 0.05:
                patterns.append({'pattern': 'Bullish Flag', 'type': 'bullish', 'strength': 'medium'})

        return patterns

    @staticmethod
    def full_analysis(bars, features=None, timeframe=None):
        """Run technical analysis, optionally limited to named feature families.

        ``features=None`` preserves the historical complete response. A selected
        feature set is used by registry-driven scans before a matching result
        needs the complete legacy response payload.
        """
        bars = [bar for bar in bars or [] if not bar.get('partial', False)]
        if len(bars) < 2:
            return None

        all_features = {
            'rsi', 'macd', 'ema', 'sma', 'bollinger_bands', 'stochastic',
            'fibonacci', 'candlestick_patterns', 'chart_patterns', 'trade_setup'
        }
        requested = all_features if features is None else set(features)
        unknown = requested - all_features
        if unknown:
            raise ValueError(f"Unknown analysis features: {', '.join(sorted(unknown))}")
        # A trade setup is a composite presentation that consumes every feature.
        computed = all_features if 'trade_setup' in requested else requested

        opens = [b['o'] for b in bars]
        highs = [b['h'] for b in bars]
        lows = [b['l'] for b in bars]
        closes = [b['c'] for b in bars]
        volumes = [b.get('v', 0) for b in bars]

        last_price = closes[-1]
        prev_price = closes[-2] if len(closes) > 1 else last_price
        change_pct = ((last_price - prev_price) / prev_price * 100) if prev_price else 0

        rsi = TechnicalAnalysis.calculate_rsi(closes) if 'rsi' in computed else None
        macd, macd_signal, macd_hist = (
            TechnicalAnalysis.calculate_macd(closes)
            if 'macd' in computed else (None, None, None)
        )
        ema_9, ema_20, ema_50, ema_200 = (
            (
                TechnicalAnalysis.calculate_ema(closes, 9),
                TechnicalAnalysis.calculate_ema(closes, 20),
                TechnicalAnalysis.calculate_ema(closes, 50),
                TechnicalAnalysis.calculate_ema(closes, 200),
            )
            if 'ema' in computed else (None, None, None, None)
        )
        sma_20, sma_50, sma_200 = (
            (
                TechnicalAnalysis.calculate_sma(closes, 20),
                TechnicalAnalysis.calculate_sma(closes, 50),
                TechnicalAnalysis.calculate_sma(closes, 200),
            )
            if 'sma' in computed else (None, None, None)
        )
        bb_upper, bb_middle, bb_lower = (
            TechnicalAnalysis.calculate_bollinger_bands(closes)
            if 'bollinger_bands' in computed else (None, None, None)
        )
        stoch_k, stoch_d = (
            TechnicalAnalysis.calculate_stochastic(highs, lows, closes)
            if 'stochastic' in computed else (None, None)
        )
        fib_levels = (
            TechnicalAnalysis.calculate_fibonacci_levels(closes)
            if 'fibonacci' in computed else None
        )
        candle_patterns = (
            TechnicalAnalysis.detect_candlestick_patterns(opens, highs, lows, closes)
            if 'candlestick_patterns' in computed else []
        )
        pattern_window = 60
        if timeframe:
            from backend.market_config import timeframe_config

            pattern_window = int(
                (timeframe_config(timeframe) or {}).get('pattern_window', 60)
            )
        chart_patterns = (
            TechnicalAnalysis.detect_chart_patterns(closes, window=pattern_window)
            if 'chart_patterns' in computed else []
        )

        # Fill fibonacci nearest levels
        if fib_levels:
            levels = sorted([fib_levels[k] for k in fib_levels if k.startswith('level_')])
            supports = [level for level in levels if level < last_price]
            resistances = [level for level in levels if level > last_price]
            fib_levels['nearest_support'] = supports[-1] if supports else None
            fib_levels['nearest_resistance'] = resistances[0] if resistances else None

        # Generate signals
        signals = []
        overall_signal = 'neutral'
        bullish_count = 0
        bearish_count = 0

        if rsi is not None:
            if rsi < 30:
                signals.append('RSI oversold (bullish)')
                bullish_count += 1
            elif rsi > 70:
                signals.append('RSI overbought (bearish)')
                bearish_count += 1

        if macd is not None and macd_signal is not None:
            if macd > macd_signal:
                signals.append('MACD bullish crossover')
                bullish_count += 1
            else:
                signals.append('MACD bearish crossover')
                bearish_count += 1

        if ema_50 is not None and ema_200 is not None:
            if ema_50 > ema_200:
                signals.append('Golden Cross (EMA 50 > 200)')
                bullish_count += 1
            else:
                signals.append('Death Cross (EMA 50 < 200)')
                bearish_count += 1

        if bb_lower is not None and bb_upper is not None:
            if last_price <= bb_lower:
                signals.append('Price at lower Bollinger Band (bullish)')
                bullish_count += 1
            elif last_price >= bb_upper:
                signals.append('Price at upper Bollinger Band (bearish)')
                bearish_count += 1

        if stoch_k is not None:
            if stoch_k < 20:
                signals.append('Stochastic oversold (bullish)')
                bullish_count += 1
            elif stoch_k > 80:
                signals.append('Stochastic overbought (bearish)')
                bearish_count += 1

        for p in candle_patterns:
            if p['type'] == 'bullish':
                bullish_count += 1
            elif p['type'] == 'bearish':
                bearish_count += 1

        for p in chart_patterns:
            if p['type'] == 'bullish':
                bullish_count += 1
            elif p['type'] == 'bearish':
                bearish_count += 1

        if bullish_count > bearish_count + 1:
            overall_signal = 'bullish'
        elif bearish_count > bullish_count + 1:
            overall_signal = 'bearish'

        indicators_dict = {
            'rsi': round(rsi, 2) if rsi is not None else None,
            'macd': {'line': round(macd, 4) if macd is not None else None, 'signal': round(macd_signal, 4) if macd_signal is not None else None, 'histogram': round(macd_hist, 4) if macd_hist is not None else None},
            'ema': {'ema_9': round(ema_9, 2) if ema_9 is not None else None, 'ema_20': round(ema_20, 2) if ema_20 is not None else None, 'ema_50': round(ema_50, 2) if ema_50 is not None else None, 'ema_200': round(ema_200, 2) if ema_200 is not None else None},
            'sma': {'sma_20': round(sma_20, 2) if sma_20 is not None else None, 'sma_50': round(sma_50, 2) if sma_50 is not None else None, 'sma_200': round(sma_200, 2) if sma_200 is not None else None},
            'bollinger_bands': {'upper': round(bb_upper, 2) if bb_upper is not None else None, 'middle': round(bb_middle, 2) if bb_middle is not None else None, 'lower': round(bb_lower, 2) if bb_lower is not None else None},
            'stochastic': {'k': round(stoch_k, 2) if stoch_k is not None else None, 'd': round(stoch_d, 2) if stoch_d is not None else None},
        }

        trade_setup = (
            TechnicalAnalysis.calculate_trade_setup(
                closes, highs, lows, opens, volumes,
                indicators_dict, fib_levels, overall_signal,
                candle_patterns, chart_patterns
            )
            if 'trade_setup' in requested else None
        )

        return {
            'price': {
                'last': last_price,
                'change_pct': round(change_pct, 2),
                'open': opens[-1],
                'high': highs[-1],
                'low': lows[-1],
                'volume': volumes[-1] if volumes else 0
            },
            'indicators': indicators_dict,
            'fibonacci': fib_levels,
            'patterns': {
                'candlestick': candle_patterns,
                'chart': chart_patterns
            },
            'signals': signals,
            'overall_signal': overall_signal,
            'signal_counts': {'bullish': bullish_count, 'bearish': bearish_count},
            'trade_setup': trade_setup
        }


