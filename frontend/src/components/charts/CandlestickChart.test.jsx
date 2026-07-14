import React from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

import CandlestickChart from './CandlestickChart'
import { toAuthoritativeIndicatorPoints, toCandlestickPoint, toVolumePoint } from './chartData'
import { CHART_SEMANTIC_COLORS, INDICATOR_COLORS } from '../../config/indicatorColors'

const chartMocks = vi.hoisted(() => {
  const series = []
  const makeSeries = (kind, options) => {
    const item = {
      kind,
      options,
      applyOptions: vi.fn(),
      setData: vi.fn(),
      update: vi.fn(),
    }
    series.push(item)
    return item
  }
  const chart = {
    addCandlestickSeries: vi.fn(options => makeSeries('candlestick', options)),
    addHistogramSeries: vi.fn(options => makeSeries('histogram', options)),
    addLineSeries: vi.fn(options => makeSeries('line', options)),
    applyOptions: vi.fn(),
    priceScale: vi.fn(() => ({ applyOptions: vi.fn() })),
    timeScale: vi.fn(() => ({ fitContent: vi.fn() })),
    subscribeCrosshairMove: vi.fn(),
    unsubscribeCrosshairMove: vi.fn(),
    removeSeries: vi.fn(),
    remove: vi.fn(),
  }
  return { chart, series }
})

vi.mock('lightweight-charts', () => ({
  CrosshairMode: { Normal: 0 },
  createChart: vi.fn(() => chartMocks.chart),
}))


describe('authoritative chart indicator series', () => {
  it('renders backend values unchanged and aligned to chart timestamps', () => {
    const points = toAuthoritativeIndicatorPoints([
      { t: 1_700_000_000_000, value: 2.25 },
      { t: 1_700_000_060_000, value: 22.33215956619923 },
      { t: 1_700_000_120_000, value: 999 },
    ], new Set([1_700_000_000, 1_700_000_060]))

    expect(points).toEqual([
      { time: 1_700_000_000, value: 2.25 },
      { time: 1_700_000_060, value: 22.33215956619923 },
    ])
  })
})

describe('partial candle presentation', () => {
  it('renders partial candles and volume with the distinct warning color', () => {
    const bar = { t: 1000, o: 100, h: 102, l: 99, c: 101, v: 500, partial: true }

    expect(toCandlestickPoint(bar)).toMatchObject({
      partial: true,
      color: CHART_SEMANTIC_COLORS.candlePartial,
      borderColor: CHART_SEMANTIC_COLORS.candlePartial,
      wickColor: CHART_SEMANTIC_COLORS.candlePartial,
    })
    expect(toVolumePoint(bar).color).toBe(CHART_SEMANTIC_COLORS.volumePartial)
  })
})

describe('backend-series chart legend and visibility controls', () => {
  beforeEach(() => {
    chartMocks.series.length = 0
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({
      clearRect: vi.fn(),
    })
  })

  it('uses configured colors, populates legend values, and toggles backend series', async () => {
    const first = 1_700_000_000_000
    const second = 1_700_000_060_000
    const point = value => [{ t: second, value }]
    const featureSeries = {
      version: 'technical-analysis-v1',
      ema: { ema_9: point(111.11), ema_20: [], ema_50: [], ema_200: [] },
      bollinger_bands: { upper: point(120.5), middle: point(110.25), lower: point(100.25) },
      macd: { line: point(1.23456), signal: point(1.1), histogram: point(0.13456) },
      rsi: point(55.4),
    }

    render(
      <CandlestickChart
        data={[
          { t: first, o: 100, h: 112, l: 99, c: 110, v: 1000 },
          { t: second, o: 110, h: 113, l: 108, c: 111, v: 1200 },
        ]}
        indicators={{
          ema: { ema_9: 111.11 },
          bollinger_bands: { upper: 120.5, middle: 110.25, lower: 100.25 },
          macd: { line: 1.23456, signal: 1.1, histogram: 0.13456 },
          rsi: 55.4,
        }}
        featureSeries={featureSeries}
        symbol="AAPL"
        timeframe="1H"
      />
    )

    const emaToggle = screen.getByRole('button', { name: 'Toggle EMA 9' })
    const bbToggle = screen.getByRole('button', { name: 'Toggle Bollinger Bands' })
    const macdToggle = screen.getByRole('button', { name: 'Toggle MACD' })
    const rsiToggle = screen.getByRole('button', { name: 'Toggle RSI' })

    expect(emaToggle).toHaveTextContent('111.11')
    expect(bbToggle).toHaveTextContent('U 120.50 / L 100.25')
    expect(macdToggle).toHaveTextContent('1.2346')
    expect(rsiToggle).toHaveTextContent('55.4')
    expect(emaToggle.querySelector('span')).toHaveStyle({ backgroundColor: INDICATOR_COLORS.ema9 })
    expect(bbToggle.querySelector('span')).toHaveStyle({ backgroundColor: INDICATOR_COLORS.bollingerBands })
    expect(macdToggle.querySelector('span')).toHaveStyle({ backgroundColor: INDICATOR_COLORS.macdLine })
    expect(rsiToggle.querySelector('span')).toHaveStyle({ backgroundColor: INDICATOR_COLORS.rsi })

    const emaSeries = chartMocks.series.find(
      item => item.kind === 'line' && item.options?.color === INDICATOR_COLORS.ema9
    )
    expect(emaSeries).toBeDefined()
    await waitFor(() => expect(emaSeries.applyOptions).toHaveBeenCalledWith({ visible: true }))

    fireEvent.click(emaToggle)

    expect(emaToggle).toHaveAttribute('aria-pressed', 'false')
    await waitFor(() => expect(emaSeries.applyOptions).toHaveBeenLastCalledWith({ visible: false }))
    expect(JSON.parse(localStorage.getItem('marketScanner.chart.indicatorVisibility.v1'))).toMatchObject({ ema_9: false })
  })
})
