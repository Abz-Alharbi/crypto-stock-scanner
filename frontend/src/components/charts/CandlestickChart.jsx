import React, { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { createChart, CrosshairMode } from 'lightweight-charts';
import { AlertTriangle, Camera, Loader2 } from 'lucide-react';
import { patternAPI } from '../../services/api';

const PATTERN_DISCLAIMER = 'Pattern detection is for research only and does not constitute financial advice.';

const EMA_COLORS = {
  ema_9: '#f59e0b',
  ema_20: '#3b82f6',
  ema_50: '#a855f7',
  ema_200: '#ef4444',
};

const BOLLINGER_OPTIONS = {
  color: 'rgba(168, 85, 247, 0.4)',
  lineWidth: 1,
  lineStyle: 2,
  priceLineVisible: false,
  lastValueVisible: false,
};

const LINE_OPTIONS = {
  lineWidth: 1,
  priceLineVisible: false,
  lastValueVisible: false,
  crosshairMarkerVisible: false,
};

const CandlestickChart = memo(function CandlestickChart({
  data,
  height = 400,
  indicators = {},
  symbol,
  timeframe,
  canDetectPatterns = true,
  onPatternAuthRequired,
}) {
  const containerRef = useRef(null);
  const chartShellRef = useRef(null);
  const patternCanvasRef = useRef(null);
  const chartRef = useRef(null);
  const candleSeriesRef = useRef(null);
  const volumeSeriesRef = useRef(null);
  const candleDataRef = useRef([]);
  const volumeDataRef = useRef([]);
  const overlaySeriesRef = useRef(new Map());
  const overlayDataRef = useRef(new Map());
  const [patternResult, setPatternResult] = useState(null);
  const [patternError, setPatternError] = useState(null);
  const [isDetectingPattern, setIsDetectingPattern] = useState(false);

  const chartData = useMemo(() => {
    if (!data || data.length === 0) return [];

    return data.map(bar => ({
      time: Math.floor(bar.t / 1000),
      open: bar.o,
      high: bar.h,
      low: bar.l,
      close: bar.c,
    })).sort((a, b) => a.time - b.time);
  }, [data]);

  const volumeData = useMemo(() => {
    if (!data || data.length === 0) return [];

    return data.map(bar => ({
      time: Math.floor(bar.t / 1000),
      value: bar.v || 0,
      color: bar.c >= bar.o ? 'rgba(0, 212, 170, 0.2)' : 'rgba(239, 68, 68, 0.2)',
    })).sort((a, b) => a.time - b.time);
  }, [data]);

  const hasData = chartData.length > 0;
  const showEma = Boolean(indicators?.ema);
  const showBollingerBands = Boolean(indicators?.bollinger_bands?.upper);

  const clearPatternOverlay = useCallback(() => {
    const canvas = patternCanvasRef.current;
    if (!canvas) return;
    const context = canvas.getContext('2d');
    context?.clearRect(0, 0, canvas.width, canvas.height);
  }, []);

  const drawPatternOverlay = useCallback(() => {
    const canvas = patternCanvasRef.current;
    const shell = chartShellRef.current;
    if (!canvas || !shell) return;

    const rect = shell.getBoundingClientRect();
    const width = Math.max(1, Math.round(rect.width));
    const height = Math.max(1, Math.round(rect.height));
    if (canvas.width !== width) canvas.width = width;
    if (canvas.height !== height) canvas.height = height;

    const context = canvas.getContext('2d');
    if (!context) return;
    context.clearRect(0, 0, width, height);

    const boxes = patternResult?.bounding_boxes || [];
    if (!patternResult?.signal_priority || boxes.length === 0) return;

    const captureWidth = patternResult.capture_size?.width || width;
    const captureHeight = patternResult.capture_size?.height || height;
    const scaleX = width / captureWidth;
    const scaleY = height / captureHeight;

    context.lineWidth = 2;
    context.strokeStyle = patternResult.source_badge === 'YOLOv8 + TA-Lib' ? '#00d4aa' : '#3b82f6';
    context.fillStyle = patternResult.source_badge === 'YOLOv8 + TA-Lib'
      ? 'rgba(0, 212, 170, 0.12)'
      : 'rgba(59, 130, 246, 0.12)';

    boxes.forEach((box) => {
      const [x1, y1, x2, y2] = box;
      const x = x1 * scaleX;
      const y = y1 * scaleY;
      const boxWidth = (x2 - x1) * scaleX;
      const boxHeight = (y2 - y1) * scaleY;
      context.fillRect(x, y, boxWidth, boxHeight);
      context.strokeRect(x, y, boxWidth, boxHeight);
    });
  }, [patternResult]);

  useEffect(() => {
    setPatternResult(null);
    setPatternError(null);
    clearPatternOverlay();
  }, [clearPatternOverlay, data, symbol, timeframe]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || !hasData) return undefined;

    const chart = createChart(container, {
      width: container.clientWidth,
      height,
      layout: {
        background: { color: 'transparent' },
        textColor: '#9ca3af',
        fontFamily: "'DM Sans', system-ui, sans-serif",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: 'rgba(42, 49, 68, 0.3)' },
        horzLines: { color: 'rgba(42, 49, 68, 0.3)' },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { color: 'rgba(0, 212, 170, 0.3)', width: 1, style: 2 },
        horzLine: { color: 'rgba(0, 212, 170, 0.3)', width: 1, style: 2 },
      },
      rightPriceScale: {
        borderColor: '#2a3144',
        scaleMargins: { top: 0.1, bottom: 0.2 },
      },
      timeScale: {
        borderColor: '#2a3144',
        timeVisible: true,
        secondsVisible: false,
      },
      handleScroll: true,
      handleScale: true,
    });

    chartRef.current = chart;
    const overlaySeriesMap = overlaySeriesRef.current;
    const overlayDataMap = overlayDataRef.current;

    candleSeriesRef.current = chart.addCandlestickSeries({
      upColor: '#00d4aa',
      downColor: '#ef4444',
      borderDownColor: '#ef4444',
      borderUpColor: '#00d4aa',
      wickDownColor: '#ef4444',
      wickUpColor: '#00d4aa',
    });
    volumeSeriesRef.current = chart.addHistogramSeries({
      color: '#00d4aa33',
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume',
    });

    chart.priceScale('volume').applyOptions({
      scaleMargins: { top: 0.85, bottom: 0 },
    });

    const handleResize = () => {
      if (containerRef.current && chartRef.current) {
        chartRef.current.applyOptions({ width: containerRef.current.clientWidth });
      }
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
      chartRef.current = null;
      candleSeriesRef.current = null;
      volumeSeriesRef.current = null;
      candleDataRef.current = [];
      volumeDataRef.current = [];
      overlaySeriesMap.clear();
      overlayDataMap.clear();
    };
  }, [hasData, height]);

  useEffect(() => {
    drawPatternOverlay();
  }, [drawPatternOverlay]);

  useEffect(() => {
    window.addEventListener('resize', drawPatternOverlay);
    return () => window.removeEventListener('resize', drawPatternOverlay);
  }, [drawPatternOverlay]);

  const handleDetectPatterns = useCallback(async () => {
    if (!canDetectPatterns) {
      onPatternAuthRequired?.();
      return;
    }

    setIsDetectingPattern(true);
    setPatternError(null);

    try {
      const capture = captureVisibleChart(containerRef.current);
      const { data: response } = await patternAPI.detect({
        image: capture.image,
        symbol,
        timeframe,
      });

      setPatternResult({
        ...response,
        capture_size: { width: capture.width, height: capture.height },
      });
    } catch (error) {
      const payload = error.response?.data;
      const message = payload?.error || error.message || 'Pattern detection failed';
      setPatternError(message);
      setPatternResult(payload?.signal_priority === null ? { ...payload, bounding_boxes: [] } : null);
      clearPatternOverlay();
    } finally {
      setIsDetectingPattern(false);
    }
  }, [canDetectPatterns, clearPatternOverlay, onPatternAuthRequired, symbol, timeframe]);

  useEffect(() => {
    if (!hasData || !candleSeriesRef.current || !volumeSeriesRef.current) return;

    candleDataRef.current = updateSeriesData(candleSeriesRef.current, candleDataRef.current, chartData);
    volumeDataRef.current = updateSeriesData(volumeSeriesRef.current, volumeDataRef.current, volumeData);
    chartRef.current?.timeScale().fitContent();
  }, [chartData, hasData, volumeData]);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || !hasData) return;

    const activeSeries = new Set();
    const closePrices = chartData.map(point => point.close);

    if (showEma) {
      Object.entries(EMA_COLORS).forEach(([key, color]) => {
        const period = parseInt(key.split('_')[1], 10);
        if (chartData.length < period) return;

        const emaData = computeEMA(closePrices, period);
        if (emaData.length === 0) return;

        const startIdx = chartData.length - emaData.length;
        const lineData = emaData.map((value, idx) => ({
          time: chartData[startIdx + idx].time,
          value,
        }));

        activeSeries.add(key);
        const series = ensureLineSeries(chart, overlaySeriesRef.current, key, { ...LINE_OPTIONS, color });
        overlayDataRef.current.set(key, updateSeriesData(series, overlayDataRef.current.get(key) || [], lineData));
      });
    }

    if (showBollingerBands) {
      const bbData = computeBollingerBands(closePrices, 20, 2);
      if (bbData.upper.length > 0) {
        const startIdx = chartData.length - bbData.upper.length;
        const upperData = bbData.upper.map((value, idx) => ({
          time: chartData[startIdx + idx].time,
          value,
        }));
        const lowerData = bbData.lower.map((value, idx) => ({
          time: chartData[startIdx + idx].time,
          value,
        }));

        activeSeries.add('bb_upper');
        activeSeries.add('bb_lower');

        const upperSeries = ensureLineSeries(chart, overlaySeriesRef.current, 'bb_upper', BOLLINGER_OPTIONS);
        const lowerSeries = ensureLineSeries(chart, overlaySeriesRef.current, 'bb_lower', BOLLINGER_OPTIONS);

        overlayDataRef.current.set('bb_upper', updateSeriesData(upperSeries, overlayDataRef.current.get('bb_upper') || [], upperData));
        overlayDataRef.current.set('bb_lower', updateSeriesData(lowerSeries, overlayDataRef.current.get('bb_lower') || [], lowerData));
      }
    }

    overlaySeriesRef.current.forEach((series, key) => {
      if (activeSeries.has(key)) return;
      chart.removeSeries(series);
      overlaySeriesRef.current.delete(key);
      overlayDataRef.current.delete(key);
    });
  }, [chartData, hasData, showBollingerBands, showEma]);

  if (!data || data.length === 0) {
    return (
      <div className="flex items-center justify-center bg-scanner-bg rounded-xl" style={{ height }}>
        <p className="text-scanner-text-dim text-sm">No chart data available</p>
      </div>
    );
  }

  return (
    <div ref={chartShellRef} className="relative rounded-xl overflow-hidden bg-scanner-bg" style={{ height }}>
      <div ref={containerRef} className="chart-container h-full" />
      <canvas
        ref={patternCanvasRef}
        className="absolute inset-0 z-10 h-full w-full pointer-events-none"
        aria-hidden="true"
      />
      <div className="absolute right-3 top-3 z-20 flex items-center gap-2">
        <button
          type="button"
          onClick={handleDetectPatterns}
          disabled={isDetectingPattern}
          className="inline-flex h-9 items-center gap-2 rounded-lg border border-scanner-border bg-scanner-surface/95 px-3 text-xs font-semibold text-scanner-text shadow-scanner-sm transition-colors hover:border-scanner-accent/60 hover:text-scanner-accent disabled:cursor-wait disabled:opacity-70"
        >
          {isDetectingPattern ? <Loader2 size={14} className="animate-spin" /> : <Camera size={14} />}
          Detect Patterns
        </button>
      </div>

      <PatternDetectionStatus result={patternResult} error={patternError} />
    </div>
  );
});

function captureVisibleChart(container) {
  if (!container) {
    throw new Error('Chart is not ready yet');
  }

  const rect = container.getBoundingClientRect();
  const width = Math.max(1, Math.round(rect.width));
  const height = Math.max(1, Math.round(rect.height));
  const chartCanvases = Array.from(container.querySelectorAll('canvas')).filter(
    canvas => canvas.width > 0 && canvas.height > 0
  );

  if (chartCanvases.length === 0) {
    throw new Error('Chart image is not ready yet');
  }

  const output = document.createElement('canvas');
  output.width = width;
  output.height = height;
  const context = output.getContext('2d');
  if (!context) {
    throw new Error('Chart image could not be captured');
  }

  context.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--color-bg').trim() || '#0a0e17';
  context.fillRect(0, 0, width, height);

  chartCanvases.forEach((canvas) => {
    const canvasRect = canvas.getBoundingClientRect();
    const drawX = canvasRect.left - rect.left;
    const drawY = canvasRect.top - rect.top;
    context.drawImage(
      canvas,
      0,
      0,
      canvas.width,
      canvas.height,
      drawX,
      drawY,
      canvasRect.width,
      canvasRect.height
    );
  });

  return {
    image: output.toDataURL('image/jpeg', 0.92),
    width,
    height,
  };
}

function PatternDetectionStatus({ result, error }) {
  if (error) {
    return (
      <div className="absolute bottom-3 left-3 z-20 max-w-[calc(100%-1.5rem)] rounded-lg border border-scanner-danger/30 bg-scanner-surface/95 px-3 py-2 text-xs text-scanner-danger shadow-scanner-sm">
        <div>{error}</div>
        <div className="mt-1 text-[10px] leading-snug text-scanner-text-dim">{PATTERN_DISCLAIMER}</div>
      </div>
    );
  }

  if (!result) return null;

  if (result.signal_priority === null) {
    return (
      <div className="absolute bottom-3 left-3 z-20 rounded-lg border border-scanner-border bg-scanner-surface/95 px-3 py-2 text-xs text-scanner-text-dim shadow-scanner-sm">
        <div>No pattern detected above threshold</div>
        <div className="mt-1 text-[10px] leading-snug">{PATTERN_DISCLAIMER}</div>
      </div>
    );
  }

  return (
    <div className="absolute bottom-3 left-3 z-20 max-w-[calc(100%-1.5rem)] rounded-lg border border-scanner-border bg-scanner-surface/95 px-3 py-2 shadow-scanner-sm">
      <div className="flex flex-wrap items-center gap-2">
        <span className={`rounded-full border px-2 py-0.5 text-[10px] font-bold ${sourceBadgeClass(result.source_badge)}`}>
          {result.source_badge}
        </span>
        {result.talib_conflict && (
          <AlertTriangle
            size={15}
            className="text-scanner-warning"
            title="TA-Lib detected a different pattern"
          />
        )}
      </div>
      <div className="mt-1 text-sm font-semibold text-scanner-text">
        {result.pattern || 'Pattern'} <span className="font-mono text-xs text-scanner-text-dim">{formatConfidence(result.confidence)}</span>
      </div>
      <div className="mt-1 text-[10px] leading-snug text-scanner-text-dim">{PATTERN_DISCLAIMER}</div>
    </div>
  );
}

function sourceBadgeClass(sourceBadge) {
  if (sourceBadge === 'YOLOv8 + TA-Lib') {
    return 'border-scanner-bullish/40 bg-scanner-bullish/10 text-scanner-bullish';
  }
  return 'border-blue-400/40 bg-blue-400/10 text-blue-300';
}

function formatConfidence(confidence) {
  if (confidence == null) return '';
  const percent = confidence <= 1 ? confidence * 100 : confidence;
  return `${Math.round(percent)}%`;
}

function ensureLineSeries(chart, seriesMap, key, options) {
  const existingSeries = seriesMap.get(key);
  if (existingSeries) return existingSeries;

  const series = chart.addLineSeries(options);
  seriesMap.set(key, series);
  return series;
}

function updateSeriesData(series, previousData, nextData) {
  if (nextData.length === 0) {
    series.setData([]);
    return [];
  }

  if (canPatchSeries(previousData, nextData)) {
    const updateStart = Math.max(0, previousData.length - 1);
    nextData.slice(updateStart).forEach(point => series.update(point));
    return nextData;
  }

  series.setData(nextData);
  return nextData;
}

function canPatchSeries(previousData, nextData) {
  if (previousData.length === 0 || nextData.length < previousData.length) return false;
  if (previousData[previousData.length - 1].time !== nextData[previousData.length - 1].time) return false;

  for (let i = 0; i < previousData.length - 1; i += 1) {
    if (!isSamePoint(previousData[i], nextData[i])) return false;
  }

  return true;
}

function isSamePoint(left, right) {
  const leftKeys = Object.keys(left);
  const rightKeys = Object.keys(right);
  if (leftKeys.length !== rightKeys.length) return false;
  return leftKeys.every(key => left[key] === right[key]);
}

function computeEMA(prices, period) {
  if (prices.length < period) return [];
  const k = 2 / (period + 1);
  const ema = [prices.slice(0, period).reduce((a, b) => a + b, 0) / period];
  for (let i = period; i < prices.length; i += 1) {
    ema.push(prices[i] * k + ema[ema.length - 1] * (1 - k));
  }
  return ema;
}

function computeBollingerBands(prices, period = 20, stdDev = 2) {
  if (prices.length < period) return { upper: [], middle: [], lower: [] };
  const upper = [];
  const middle = [];
  const lower = [];

  for (let i = period - 1; i < prices.length; i += 1) {
    const slice = prices.slice(i - period + 1, i + 1);
    const mean = slice.reduce((a, b) => a + b, 0) / period;
    const std = Math.sqrt(slice.reduce((sum, val) => sum + Math.pow(val - mean, 2), 0) / period);
    middle.push(mean);
    upper.push(mean + stdDev * std);
    lower.push(mean - stdDev * std);
  }

  return { upper, middle, lower };
}

export default CandlestickChart;
