import { describe, expect, it } from 'vitest'

import { computeBollingerBands, computeEMA } from './indicatorCalculations'


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
