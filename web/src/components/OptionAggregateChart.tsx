import { useEffect, useMemo, useRef } from 'react'
import {
  ColorType,
  LineSeries,
  createChart,
  type IChartApi,
  type ISeriesApi,
  type LineData,
  type Time,
} from 'lightweight-charts'
import type { OptionsAggregateEvent } from '../types/optionsLive'

interface OptionAggregateChartProps {
  rows: OptionsAggregateEvent[]
  contract: string
  height?: number
}

function toChartTime(timestamp: number): Time {
  return Math.floor(timestamp / 1000) as Time
}

export function OptionAggregateChart({ rows, contract, height = 260 }: OptionAggregateChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const seriesRef = useRef<ISeriesApi<'Line'> | null>(null)
  const hasRows = rows.length > 0
  const chartData = useMemo<LineData[]>(
    () => rows.map((row) => ({ time: toChartTime(row.timestamp), value: row.close })),
    [rows],
  )

  useEffect(() => {
    if (!containerRef.current || !hasRows) return
    const container = containerRef.current
    const styles = getComputedStyle(document.documentElement)
    const readToken = (name: string, fallback: string) => styles.getPropertyValue(name).trim() || fallback
    const chart = createChart(container, {
      width: container.clientWidth,
      height,
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: readToken('--color-fg-muted', '#555'),
        fontSize: 12,
      },
      grid: {
        vertLines: { color: 'rgba(0,0,0,0.06)' },
        horzLines: { color: 'rgba(0,0,0,0.06)' },
      },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false, timeVisible: true, secondsVisible: true },
    })
    const series = chart.addSeries(LineSeries, {
      color: readToken('--color-accent', '#5b6abf'),
      lineWidth: 2,
    })
    chartRef.current = chart
    seriesRef.current = series
    const handleResize = () => chart.applyOptions({ width: container.clientWidth })
    window.addEventListener('resize', handleResize)
    return () => {
      window.removeEventListener('resize', handleResize)
      chart.remove()
      chartRef.current = null
      seriesRef.current = null
    }
  }, [hasRows, height])

  useEffect(() => {
    if (!seriesRef.current || !chartRef.current || chartData.length === 0) return
    seriesRef.current.setData(chartData)
    chartRef.current.timeScale().fitContent()
  }, [chartData])

  if (!hasRows) {
    return <p className="empty">옵션 초봉 데이터가 없습니다.</p>
  }

  return (
    <div
      ref={containerRef}
      className="chart-container option-aggregate-chart"
      style={{ height }}
      role="img"
      aria-label={`${contract} 옵션 초봉 차트`}
    />
  )
}
