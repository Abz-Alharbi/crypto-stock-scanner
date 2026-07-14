import { CHART_SEMANTIC_COLORS } from '../../config/indicatorColors'

export function toCandlestickPoint(bar) {
  return {
    time: Math.floor(bar.t / 1000),
    open: bar.o,
    high: bar.h,
    low: bar.l,
    close: bar.c,
    partial: Boolean(bar.partial),
    ...(bar.partial ? {
      color: CHART_SEMANTIC_COLORS.candlePartial,
      borderColor: CHART_SEMANTIC_COLORS.candlePartial,
      wickColor: CHART_SEMANTIC_COLORS.candlePartial,
    } : {}),
  }
}

export function toVolumePoint(bar) {
  let color = bar.c >= bar.o
    ? CHART_SEMANTIC_COLORS.volumeBullish
    : CHART_SEMANTIC_COLORS.volumeBearish
  if (bar.partial) color = CHART_SEMANTIC_COLORS.volumePartial
  return {
    time: Math.floor(bar.t / 1000),
    value: bar.v || 0,
    color,
  }
}

export function toAuthoritativeIndicatorPoints(points, validTimes) {
  return (points || []).map(point => ({
    time: point.t > 10_000_000_000 ? Math.floor(point.t / 1000) : point.t,
    value: point.value,
  })).filter(point => validTimes.has(point.time) && Number.isFinite(point.value))
}
