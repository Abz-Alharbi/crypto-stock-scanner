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
