export function getFooterUniverseCounts(apiStatus) {
  return {
    stocks: apiStatus?.universe_counts?.stocks?.active ?? apiStatus?.stock_symbols ?? 0,
    crypto: apiStatus?.universe_counts?.crypto?.active ?? apiStatus?.crypto_symbols ?? 0,
  }
}
