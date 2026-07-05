import React, { useEffect, useRef, memo } from 'react';
import { createChart, CrosshairMode } from 'lightweight-charts';

const CandlestickChart = memo(function CandlestickChart({ data, height = 400, indicators = {} }) {
  const containerRef = useRef(null);
  const chartRef = useRef(null);

  useEffect(() => {
    if (!containerRef.current || !data || data.length === 0) return;

    // Clear previous chart
    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
    }

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height: height,
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

    // Candlestick series
    const candleSeries = chart.addCandlestickSeries({
      upColor: '#00d4aa',
      downColor: '#ef4444',
      borderDownColor: '#ef4444',
      borderUpColor: '#00d4aa',
      wickDownColor: '#ef4444',
      wickUpColor: '#00d4aa',
    });

    const chartData = data.map(bar => ({
      time: Math.floor(bar.t / 1000), // Polygon sends ms timestamps
      open: bar.o,
      high: bar.h,
      low: bar.l,
      close: bar.c,
    })).sort((a, b) => a.time - b.time);

    candleSeries.setData(chartData);

    // Volume series
    const volumeSeries = chart.addHistogramSeries({
      color: '#00d4aa33',
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume',
    });

    chart.priceScale('volume').applyOptions({
      scaleMargins: { top: 0.85, bottom: 0 },
    });

    const volumeData = data.map(bar => ({
      time: Math.floor(bar.t / 1000),
      value: bar.v || 0,
      color: bar.c >= bar.o ? 'rgba(0, 212, 170, 0.2)' : 'rgba(239, 68, 68, 0.2)',
    })).sort((a, b) => a.time - b.time);

    volumeSeries.setData(volumeData);

    // Add EMA overlays if available
    if (indicators.ema) {
      const emaColors = { ema_9: '#f59e0b', ema_20: '#3b82f6', ema_50: '#a855f7', ema_200: '#ef4444' };
      // We'll compute EMAs from the chart data for visual overlay
      Object.entries(emaColors).forEach(([key, color]) => {
        const period = parseInt(key.split('_')[1]);
        if (chartData.length >= period) {
          const emaData = computeEMA(chartData.map(d => d.close), period);
          if (emaData.length > 0) {
            const lineSeries = chart.addLineSeries({
              color: color,
              lineWidth: 1,
              priceLineVisible: false,
              lastValueVisible: false,
              crosshairMarkerVisible: false,
            });
            const lineData = emaData.map((val, idx) => ({
              time: chartData[chartData.length - emaData.length + idx].time,
              value: val,
            }));
            lineSeries.setData(lineData);
          }
        }
      });
    }

    // Add Bollinger Bands if available
    if (indicators.bollinger_bands && indicators.bollinger_bands.upper) {
      // Compute BB for visual overlay
      const bbData = computeBollingerBands(chartData.map(d => d.close), 20, 2);
      if (bbData.upper.length > 0) {
        const bbUpper = chart.addLineSeries({ color: 'rgba(168, 85, 247, 0.4)', lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false });
        const bbLower = chart.addLineSeries({ color: 'rgba(168, 85, 247, 0.4)', lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false });

        const startIdx = chartData.length - bbData.upper.length;
        bbUpper.setData(bbData.upper.map((val, idx) => ({ time: chartData[startIdx + idx].time, value: val })));
        bbLower.setData(bbData.lower.map((val, idx) => ({ time: chartData[startIdx + idx].time, value: val })));
      }
    }

    // Fit content
    chart.timeScale().fitContent();

    // Handle resize
    const handleResize = () => {
      if (containerRef.current && chartRef.current) {
        chartRef.current.applyOptions({ width: containerRef.current.clientWidth });
      }
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
      }
    };
  }, [data, height, indicators]);

  if (!data || data.length === 0) {
    return (
      <div className="flex items-center justify-center bg-scanner-bg rounded-xl" style={{ height }}>
        <p className="text-scanner-text-dim text-sm">No chart data available</p>
      </div>
    );
  }

  return <div ref={containerRef} className="chart-container rounded-xl overflow-hidden" />;
});

// Helper: Compute EMA
function computeEMA(prices, period) {
  if (prices.length < period) return [];
  const k = 2 / (period + 1);
  const ema = [prices.slice(0, period).reduce((a, b) => a + b, 0) / period];
  for (let i = period; i < prices.length; i++) {
    ema.push(prices[i] * k + ema[ema.length - 1] * (1 - k));
  }
  return ema;
}

// Helper: Compute Bollinger Bands
function computeBollingerBands(prices, period = 20, stdDev = 2) {
  if (prices.length < period) return { upper: [], middle: [], lower: [] };
  const upper = [], middle = [], lower = [];
  for (let i = period - 1; i < prices.length; i++) {
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
