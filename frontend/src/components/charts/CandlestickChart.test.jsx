import { describe, expect, it } from 'vitest'

import { computeBollingerBands, computeEMA } from './indicatorCalculations'
import { toCandlestickPoint, toVolumePoint } from './chartData'
import { CHART_SEMANTIC_COLORS } from '../../config/indicatorColors'


describe('current chart indicator calculation characterization', () => {
  it('seeds EMA with an SMA instead of the backend pandas first-value seed', () => {
    expect(computeEMA([1, 2, 3], 3)).toEqual([2])
  })

  it('uses population variance for Bollinger Bands instead of backend sample variance', () => {
    const bands = computeBollingerBands(Array.from({ length: 20 }, (_, index) => index + 1), 20, 2)

    expect(bands.middle.at(-1)).toBeCloseTo(10.5, 12)
    expect(bands.upper.at(-1)).toBeCloseTo(22.032562594670797, 12)
    expect(bands.lower.at(-1)).toBeCloseTo(-1.0325625946707966, 12)
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
