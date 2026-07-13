import React, { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { createChart, CrosshairMode } from 'lightweight-charts';
import { AlertTriangle, Camera, Loader2 } from 'lucide-react';
import IndicatorLegend from '../chart/IndicatorLegend';
import {
  CHART_SEMANTIC_COLORS,
  INDICATOR_COLORS,
  PATTERN_OVERLAY_COLORS,
} from '../../config/indicatorColors';
import { patternAPI } from '../../services/api';
import {
  computeBollingerBands,
  computeEMA,
  computeMACD,
  computeRSI,
} from './indicatorCalculations';
import { toCandlestickPoint, toVolumePoint } from './chartData';

const PATTERN_DISCLAIMER = 'Pattern detection is for research only and does not constitute financial advice.';
const INDICATOR_VISIBILITY_KEY = 'marketScanner.chart.indicatorVisibility.v1';

const EMA_SERIES = [
  { key: 'ema_9', name: 'EMA 9', shortName: 'EMA9', period: 9, color: INDICATOR_COLORS.ema9 },
  { key: 'ema_20', name: 'EMA 20', shortName: 'EMA20', period: 20, color: INDICATOR_COLORS.ema20 },
  { key: 'ema_50', name: 'EMA 50', shortName: 'EMA50', period: 50, color: INDICATOR_COLORS.ema50 },
  { key: 'ema_200', name: 'EMA 200', shortName: 'EMA200', period: 200, color: INDICATOR_COLORS.ema200 },
];

const BOLLINGER_OPTIONS = {
  color: INDICATOR_COLORS.bollingerBands,
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

const HISTOGRAM_OPTIONS = {
  priceLineVisible: false,
  lastValueVisible: false,
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
  const legendValueMapsRef = useRef(new Map());
  const [patternResult, setPatternResult] = useState(null);
  const [patternError, setPatternError] = useState(null);
  const [isDetectingPattern, setIsDetectingPattern] = useState(false);
  const [indicatorVisibility, setIndicatorVisibility] = useState(loadIndicatorVisibility);
  const [hoverValues, setHoverValues] = useState({});

  const chartData = useMemo(() => {
    if (!data || data.length === 0) return [];

    return data.map(toCandlestickPoint).sort((a, b) => a.time - b.time);
  }, [data]);

  const volumeData = useMemo(() => {
    if (!data || data.length === 0) return [];

    return data.map(toVolumePoint).sort((a, b) => a.time - b.time);
  }, [data]);

  const hasData = chartData.length > 0;
  const showEma = Boolean(indicators?.ema);
  const showBollingerBands = Boolean(indicators?.bollinger_bands?.upper);
  const showMacd = Boolean(indicators?.macd);
  const showRsi = isFiniteNumber(indicators?.rsi);
  const closedChartData = useMemo(
    () => chartData.filter(point => !point.partial),
    [chartData]
  );
  const indicatorDefinitions = useMemo(() => (
    buildIndicatorDefinitions(closedChartData, {
      showBollingerBands,
      showEma,
      showMacd,
      showRsi,
    })
  ), [closedChartData, showBollingerBands, showEma, showMacd, showRsi]);
  const hasOscillatorSeries = indicatorDefinitions.series.some(
    definition => definition.priceScaleId === 'macd' || definition.priceScaleId === 'rsi'
  );
  const isIndicatorVisible = useCallback(
    key => indicatorVisibility[key] !== false,
    [indicatorVisibility]
  );
  const legendItems = useMemo(() => (
    indicatorDefinitions.legend.map(item => ({
      ...item,
      value: hoverValues[item.key] || item.value,
      visible: isIndicatorVisible(item.key),
    }))
  ), [hoverValues, indicatorDefinitions.legend, isIndicatorVisible]);
  const toggleIndicator = useCallback((key) => {
    setIndicatorVisibility((current) => {
      const next = { ...current, [key]: current[key] === false };
      saveIndicatorVisibility(next);
      return next;
    });
  }, []);

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
    context.strokeStyle = patternResult.source_badge === 'YOLOv8 + TA-Lib'
      ? PATTERN_OVERLAY_COLORS.combinedStroke
      : PATTERN_OVERLAY_COLORS.yoloStroke;
    context.fillStyle = patternResult.source_badge === 'YOLOv8 + TA-Lib'
      ? PATTERN_OVERLAY_COLORS.combinedFill
      : PATTERN_OVERLAY_COLORS.yoloFill;

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
    setHoverValues({});
    clearPatternOverlay();
  }, [clearPatternOverlay, data, symbol, timeframe]);

  useEffect(() => {
    const valueMaps = new Map();
    indicatorDefinitions.legend.forEach((item) => {
      valueMaps.set(item.key, item.valuesByTime);
    });
    legendValueMapsRef.current = valueMaps;
  }, [indicatorDefinitions.legend]);

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
        vertLine: { color: CHART_SEMANTIC_COLORS.crosshair, width: 1, style: 2 },
        horzLine: { color: CHART_SEMANTIC_COLORS.crosshair, width: 1, style: 2 },
      },
      rightPriceScale: {
        borderColor: '#2a3144',
        scaleMargins: getPriceScaleMargins(hasOscillatorSeries),
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
      upColor: CHART_SEMANTIC_COLORS.candleBullish,
      downColor: CHART_SEMANTIC_COLORS.candleBearish,
      borderDownColor: CHART_SEMANTIC_COLORS.candleBearish,
      borderUpColor: CHART_SEMANTIC_COLORS.candleBullish,
      wickDownColor: CHART_SEMANTIC_COLORS.candleBearish,
      wickUpColor: CHART_SEMANTIC_COLORS.candleBullish,
    });
    volumeSeriesRef.current = chart.addHistogramSeries({
      color: CHART_SEMANTIC_COLORS.volumeBase,
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume',
    });

    applyAuxiliaryScaleMargins(chart, hasOscillatorSeries);

    const handleCrosshairMove = (param) => {
      const time = normalizeCrosshairTime(param?.time);
      if (time == null) {
        setHoverValues({});
        return;
      }

      const nextValues = {};
      legendValueMapsRef.current.forEach((valuesByTime, key) => {
        const value = valuesByTime.get(time);
        if (value != null) nextValues[key] = value;
      });
      setHoverValues(nextValues);
    };

    const handleResize = () => {
      if (containerRef.current && chartRef.current) {
        chartRef.current.applyOptions({ width: containerRef.current.clientWidth });
      }
    };

    window.addEventListener('resize', handleResize);
    chart.subscribeCrosshairMove(handleCrosshairMove);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.unsubscribeCrosshairMove(handleCrosshairMove);
      chart.remove();
      chartRef.current = null;
      candleSeriesRef.current = null;
      volumeSeriesRef.current = null;
      candleDataRef.current = [];
      volumeDataRef.current = [];
      overlaySeriesMap.clear();
      overlayDataMap.clear();
    };
  }, [hasData, hasOscillatorSeries, height]);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    chart.applyOptions({
      rightPriceScale: {
        scaleMargins: getPriceScaleMargins(hasOscillatorSeries),
      },
    });
    applyAuxiliaryScaleMargins(chart, hasOscillatorSeries);
  }, [hasOscillatorSeries]);

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
  }, [chartData, hasData, hasOscillatorSeries, volumeData]);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || !hasData) return;

    const activeSeries = new Set();

    indicatorDefinitions.series.forEach((definition) => {
      activeSeries.add(definition.seriesKey);
      const series = ensureTechnicalSeries(chart, overlaySeriesRef.current, definition);
      series.applyOptions({ visible: isIndicatorVisible(definition.legendKey) });
      overlayDataRef.current.set(
        definition.seriesKey,
        updateSeriesData(series, overlayDataRef.current.get(definition.seriesKey) || [], definition.data)
      );
    });
    if (hasOscillatorSeries) applyOscillatorScaleMargins(chart);

    overlaySeriesRef.current.forEach((series, key) => {
      if (activeSeries.has(key)) return;
      chart.removeSeries(series);
      overlaySeriesRef.current.delete(key);
      overlayDataRef.current.delete(key);
    });
  }, [hasData, hasOscillatorSeries, indicatorDefinitions.series, isIndicatorVisible]);

  if (!data || data.length === 0) {
    return (
      <div className="flex items-center justify-center bg-scanner-bg rounded-xl" style={{ height }}>
        <p className="text-scanner-text-dim text-sm">No chart data available</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <IndicatorLegend items={legendItems} onToggle={toggleIndicator} />
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

function buildIndicatorDefinitions(chartData, visibility) {
  if (!chartData.length) return { series: [], legend: [] };

  const closePrices = chartData.map(point => point.close);
  const series = [];
  const legend = [];

  if (visibility.showEma) {
    EMA_SERIES.forEach(({ key, name, shortName, period, color }) => {
      const emaData = computeEMA(closePrices, period);
      if (emaData.length === 0) return;

      const lineData = alignValuesToChartData(chartData, emaData);
      addLineDefinition(series, legend, {
        seriesKey: key,
        legendKey: key,
        name,
        shortName,
        color,
        data: lineData,
        priceScaleId: 'right',
        formatter: value => formatIndicatorValue(value, 2),
      });
    });
  }

  if (visibility.showBollingerBands) {
    const bbData = computeBollingerBands(closePrices, 20, 2);
    if (bbData.upper.length > 0) {
      const upperData = alignValuesToChartData(chartData, bbData.upper);
      const lowerData = alignValuesToChartData(chartData, bbData.lower);
      const latestUpper = lastSeriesValue(upperData);
      const latestLower = lastSeriesValue(lowerData);
      const valuesByTime = new Map();

      upperData.forEach((point, index) => {
        const lowerPoint = lowerData[index];
        if (!lowerPoint) return;
        valuesByTime.set(point.time, formatBandValue(point.value, lowerPoint.value));
      });

      series.push({
        seriesKey: 'bb_upper',
        legendKey: 'bollinger_bands',
        type: 'line',
        data: upperData,
        priceScaleId: 'right',
        options: { ...BOLLINGER_OPTIONS, priceScaleId: 'right' },
      });
      series.push({
        seriesKey: 'bb_lower',
        legendKey: 'bollinger_bands',
        type: 'line',
        data: lowerData,
        priceScaleId: 'right',
        options: { ...BOLLINGER_OPTIONS, priceScaleId: 'right' },
      });
      legend.push({
        key: 'bollinger_bands',
        name: 'Bollinger Bands',
        shortName: 'BB',
        color: INDICATOR_COLORS.bollingerBands,
        value: formatBandValue(latestUpper, latestLower),
        valuesByTime,
      });
    }
  }

  if (visibility.showMacd) {
    const macd = computeMACD(closePrices);
    if (macd.line.length > 0) {
      const lineData = alignValuesToChartData(chartData, macd.line);
      const signalData = alignValuesToChartData(chartData, macd.signal);
      const histogramData = alignValuesToChartData(chartData, macd.histogram).map(point => ({
        ...point,
        color: point.value >= 0
          ? INDICATOR_COLORS.macdHistogramBullish
          : INDICATOR_COLORS.macdHistogramBearish,
      }));

      addLineDefinition(series, legend, {
        seriesKey: 'macd_line',
        legendKey: 'macd_line',
        name: 'MACD',
        shortName: 'MACD',
        color: INDICATOR_COLORS.macdLine,
        data: lineData,
        priceScaleId: 'macd',
        formatter: value => formatIndicatorValue(value, 4),
      });
      addLineDefinition(series, legend, {
        seriesKey: 'macd_signal',
        legendKey: 'macd_signal',
        name: 'MACD Signal',
        shortName: 'Signal',
        color: INDICATOR_COLORS.macdSignal,
        data: signalData,
        priceScaleId: 'macd',
        formatter: value => formatIndicatorValue(value, 4),
      });
      addHistogramDefinition(series, legend, {
        seriesKey: 'macd_histogram',
        legendKey: 'macd_histogram',
        name: 'MACD Hist',
        shortName: 'Hist',
        color: INDICATOR_COLORS.macdHistogram,
        data: histogramData,
        priceScaleId: 'macd',
        formatter: value => formatIndicatorValue(value, 4),
      });
    }
  }

  if (visibility.showRsi) {
    const rsiData = alignValuesToChartData(chartData, computeRSI(closePrices, 14));
    if (rsiData.length > 0) {
      addLineDefinition(series, legend, {
        seriesKey: 'rsi',
        legendKey: 'rsi',
        name: 'RSI',
        shortName: 'RSI',
        color: INDICATOR_COLORS.rsi,
        data: rsiData,
        priceScaleId: 'rsi',
        formatter: value => formatIndicatorValue(value, 1),
      });
    }
  }

  return { series, legend };
}

function addLineDefinition(series, legend, definition) {
  series.push({
    seriesKey: definition.seriesKey,
    legendKey: definition.legendKey,
    type: 'line',
    data: definition.data,
    priceScaleId: definition.priceScaleId,
    options: {
      ...LINE_OPTIONS,
      color: definition.color,
      priceScaleId: definition.priceScaleId,
    },
  });
  legend.push(buildLegendItem(definition));
}

function addHistogramDefinition(series, legend, definition) {
  series.push({
    seriesKey: definition.seriesKey,
    legendKey: definition.legendKey,
    type: 'histogram',
    data: definition.data,
    priceScaleId: definition.priceScaleId,
    options: {
      ...HISTOGRAM_OPTIONS,
      color: definition.color,
      priceScaleId: definition.priceScaleId,
    },
  });
  legend.push(buildLegendItem(definition));
}

function buildLegendItem({ legendKey, name, shortName, color, data, formatter }) {
  const valuesByTime = new Map();
  data.forEach((point) => {
    valuesByTime.set(point.time, formatter(point.value));
  });

  return {
    key: legendKey,
    name,
    shortName,
    color,
    value: formatter(lastSeriesValue(data)),
    valuesByTime,
  };
}

function ensureTechnicalSeries(chart, seriesMap, definition) {
  const existingSeries = seriesMap.get(definition.seriesKey);
  if (existingSeries) return existingSeries;

  const nextSeries = definition.type === 'histogram'
    ? chart.addHistogramSeries(definition.options)
    : chart.addLineSeries(definition.options);

  seriesMap.set(definition.seriesKey, nextSeries);
  return nextSeries;
}

function alignValuesToChartData(chartData, values) {
  if (!values.length) return [];
  const startIdx = chartData.length - values.length;
  if (startIdx < 0) return [];

  return values.map((value, idx) => ({
    time: chartData[startIdx + idx].time,
    value,
  }));
}

function lastSeriesValue(data) {
  return data.length > 0 ? data[data.length - 1].value : null;
}

function formatBandValue(upper, lower) {
  return `U ${formatIndicatorValue(upper, 2)} / L ${formatIndicatorValue(lower, 2)}`;
}

function formatIndicatorValue(value, precision = 2) {
  if (!isFiniteNumber(value)) return '--';
  if (Math.abs(value) >= 1000) {
    return value.toLocaleString(undefined, {
      maximumFractionDigits: precision,
      minimumFractionDigits: 0,
    });
  }
  return value.toFixed(precision);
}

function loadIndicatorVisibility() {
  if (typeof window === 'undefined') return {};

  try {
    return JSON.parse(window.localStorage.getItem(INDICATOR_VISIBILITY_KEY) || '{}');
  } catch {
    return {};
  }
}

function saveIndicatorVisibility(value) {
  if (typeof window === 'undefined') return;

  try {
    window.localStorage.setItem(INDICATOR_VISIBILITY_KEY, JSON.stringify(value));
  } catch {
    // Local storage can be unavailable in privacy modes; chart controls still work for the session.
  }
}

function getPriceScaleMargins(hasOscillatorSeries) {
  return hasOscillatorSeries
    ? { top: 0.06, bottom: 0.48 }
    : { top: 0.1, bottom: 0.2 };
}

function applyAuxiliaryScaleMargins(chart, hasOscillatorSeries) {
  chart.priceScale('volume').applyOptions({
    scaleMargins: hasOscillatorSeries ? { top: 0.9, bottom: 0 } : { top: 0.85, bottom: 0 },
  });
}

function applyOscillatorScaleMargins(chart) {
  chart.priceScale('macd').applyOptions({
    scaleMargins: { top: 0.58, bottom: 0.28 },
    borderVisible: false,
  });
  chart.priceScale('rsi').applyOptions({
    scaleMargins: { top: 0.76, bottom: 0.1 },
    borderVisible: false,
  });
}

function normalizeCrosshairTime(time) {
  if (time == null) return null;
  if (typeof time === 'number') return time;
  if (typeof time === 'object' && 'timestamp' in time) return time.timestamp;
  return null;
}

function isFiniteNumber(value) {
  return typeof value === 'number' && Number.isFinite(value);
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

export default CandlestickChart;
