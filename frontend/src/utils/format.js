export function formatKRW(n) {
  return new Intl.NumberFormat('ko-KR').format(Math.round(n))
}

export function formatRate(rate, decimals = 1) {
  return (rate * 100).toFixed(decimals)
}

export function formatCostRate(rate) {
  return (rate * 100).toFixed(1)
}

export function formatDecimal(n, decimals = 2) {
  return parseFloat(n).toFixed(decimals)
}
