import { describe, expect, it } from 'vitest'

import { getFooterUniverseCounts } from './utils/footerUniverseCounts'


describe('footer universe count selection', () => {
  it('prefers active universe counts over legacy fallback fields', () => {
    expect(getFooterUniverseCounts({
      stock_symbols: 80,
      crypto_symbols: 15,
      universe_counts: {
        stocks: { active: 734 },
        crypto: { active: 15 },
      },
    })).toEqual({ stocks: 734, crypto: 15 })
  })

  it('remains compatible with the legacy health payload', () => {
    expect(getFooterUniverseCounts({ stock_symbols: 80, crypto_symbols: 15 }))
      .toEqual({ stocks: 80, crypto: 15 })
  })
})
