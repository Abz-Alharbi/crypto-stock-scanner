export const assetClassForMarket = market => market === 'crypto' ? 'crypto' : 'stocks'

export function defaultUniverseFor(universes, market) {
  const assetClass = assetClassForMarket(market)
  const definitions = Object.values(universes || {}).filter(
    definition => definition.asset_class === assetClass
  )
  return definitions.find(definition => definition.default)?.key
    || definitions[0]?.key
    || null
}

export function strategyUnavailableReason(strategy, market, timeframe, planCapabilities = null) {
  if (!strategy) return 'Strategy capability metadata is unavailable'
  if (planCapabilities && !planCapabilities.asset_classes?.includes(assetClassForMarket(market))) {
    return `${assetClassForMarket(market)} is unavailable on the current provider plan`
  }
  if (strategy.available === false) return 'Unavailable on the current provider plan'
  if (!strategy.supported_asset_classes?.includes(assetClassForMarket(market))) {
    return `Not supported for ${assetClassForMarket(market)}`
  }
  if (!strategy.supported_timeframes?.includes(timeframe)) {
    return `Not supported on ${timeframe}`
  }
  return null
}

export function timeframeUnavailableReason(config, selectedStrategies, market, timeframe, planCapabilities = null) {
  if (!config || config.available === false) {
    return 'Unavailable on the current provider plan'
  }
  const incompatible = selectedStrategies.find(
    strategy => strategyUnavailableReason(strategy, market, timeframe, planCapabilities)
  )
  if (!incompatible) return null
  return `${incompatible.name || incompatible.id} is incompatible with ${timeframe}`
}

export function flattenStrategies(definitions) {
  return Object.values(definitions || {}).flatMap(category => (
    Object.entries(category).map(([id, strategy]) => ({ id, ...strategy }))
  ))
}

export function buildScanSubmission({ market, universe, timeframe, strategyIds, limit = 30 }) {
  return {
    request: {
      market: assetClassForMarket(market),
      universe,
      timeframe,
      filters: [...strategyIds],
      limit,
    },
    context: Object.freeze({
      asset_class: assetClassForMarket(market),
      scope: 'universe',
      universe,
      timeframe,
      strategy_ids: Object.freeze([...strategyIds]),
    }),
  }
}
