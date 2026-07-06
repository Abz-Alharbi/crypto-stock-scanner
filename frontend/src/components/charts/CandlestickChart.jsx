import React, { memo, useEffect, useMemo, useRef } from 'react';
import { createChart, CrosshairMode } from 'lightweight-charts';

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

const CandlestickChart = memo(function CandlestickChart({ data, height = 400, indicators = {} }) {
  const containerRef = useRef(null);
  const chartRef = useRef(null);
  const candleSeriesRef = useRef(null);
  const volumeSeriesRef = useRef(null);
  const candleDataRef = useRef([]);
  const volumeDataRef = useRef([]);
  const overlaySeriesRef = useRef(new Map());
  const overlayDataRef = useRef(new Map());

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

  return <div ref={containerRef} className="chart-container rounded-xl overflow-hidden" />;
});

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
