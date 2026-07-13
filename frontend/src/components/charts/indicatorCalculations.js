export function computeEMA(prices, period) {
  if (prices.length < period) return []
  const k = 2 / (period + 1)
  const ema = [prices.slice(0, period).reduce((a, b) => a + b, 0) / period]
  for (let i = period; i < prices.length; i += 1) {
    ema.push(prices[i] * k + ema[ema.length - 1] * (1 - k))
  }
  return ema
}

export function computeBollingerBands(prices, period = 20, stdDev = 2) {
  if (prices.length < period) return { upper: [], middle: [], lower: [] }
  const upper = []
  const middle = []
  const lower = []

  for (let i = period - 1; i < prices.length; i += 1) {
    const slice = prices.slice(i - period + 1, i + 1)
    const mean = slice.reduce((a, b) => a + b, 0) / period
    const std = Math.sqrt(slice.reduce((sum, val) => sum + Math.pow(val - mean, 2), 0) / period)
    middle.push(mean)
    upper.push(mean + stdDev * std)
    lower.push(mean - stdDev * std)
  }

  return { upper, middle, lower }
}

export function computeMACD(prices, fastPeriod = 12, slowPeriod = 26, signalPeriod = 9) {
  if (prices.length < slowPeriod + signalPeriod) {
    return { line: [], signal: [], histogram: [] }
  }

  const fastEma = computeEMA(prices, fastPeriod)
  const slowEma = computeEMA(prices, slowPeriod)
  const fastOffset = fastEma.length - slowEma.length
  const line = slowEma.map((slowValue, index) => fastEma[index + fastOffset] - slowValue)
  const signal = computeEMA(line, signalPeriod)
  const signalOffset = line.length - signal.length
  const alignedLine = line.slice(signalOffset)
  const histogram = alignedLine.map((value, index) => value - signal[index])

  return { line: alignedLine, signal, histogram }
}

export function computeRSI(prices, period = 14) {
  if (prices.length <= period) return []

  let gains = 0
  let losses = 0

  for (let i = 1; i <= period; i += 1) {
    const change = prices[i] - prices[i - 1]
    if (change >= 0) gains += change
    else losses -= change
  }

  let averageGain = gains / period
  let averageLoss = losses / period
  const values = [calculateRsiValue(averageGain, averageLoss)]

  for (let i = period + 1; i < prices.length; i += 1) {
    const change = prices[i] - prices[i - 1]
    const gain = Math.max(change, 0)
    const loss = Math.max(-change, 0)
    averageGain = ((averageGain * (period - 1)) + gain) / period
    averageLoss = ((averageLoss * (period - 1)) + loss) / period
    values.push(calculateRsiValue(averageGain, averageLoss))
  }

  return values
}

function calculateRsiValue(averageGain, averageLoss) {
  if (averageLoss === 0) return 100
  const relativeStrength = averageGain / averageLoss
  return 100 - (100 / (1 + relativeStrength))
}
