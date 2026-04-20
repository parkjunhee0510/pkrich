interface Props {
  values: number[]
  width?: number
  height?: number
  color?: string
}

/**
 * Tiny dependency-free SVG sparkline. Used by the sector explorer to render
 * 6-month close-only trends without pulling the full lightweight-charts bundle.
 */
export function Sparkline({ values, width = 160, height = 40, color }: Props) {
  if (values.length < 2) {
    return <svg width={width} height={height} aria-hidden="true" />
  }
  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = max - min || 1
  const stepX = width / (values.length - 1)
  const points = values
    .map((v, i) => {
      const x = i * stepX
      const y = height - ((v - min) / range) * height
      return `${x.toFixed(2)},${y.toFixed(2)}`
    })
    .join(' ')

  const first = values[0]
  const last = values[values.length - 1]
  const stroke = color ?? (last >= first ? '#26a69a' : '#ef5350')

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden="true">
      <polyline
        points={points}
        fill="none"
        stroke={stroke}
        strokeWidth={1.5}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  )
}
