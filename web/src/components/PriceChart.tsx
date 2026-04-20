import { useEffect, useRef, useState } from 'react'
import {
  CandlestickSeries,
  createChart,
  ColorType,
  HistogramSeries,
  LineSeries,
  type IChartApi,
  type ISeriesApi,
  type CandlestickData,
  type LineData,
  type Time,
} from 'lightweight-charts'
import type { PriceHistoryRow } from '../types'
import { parsePrice } from '../utils/format'

interface Props {
  rows: PriceHistoryRow[]
  height?: number
}

type ChartMode = 'candle' | 'line'

function hasOHLC(row: PriceHistoryRow): boolean {
  return !!(row.open && row.high && row.low && row.close)
}

function parseNum(v?: string): number {
  if (!v) return 0
  const trimmed = v.trim().toUpperCase()
  const suffix = trimmed.match(/[KMBT]$/)?.[0]
  const multiplier = suffix === 'K'
    ? 1_000
    : suffix === 'M'
      ? 1_000_000
      : suffix === 'B'
        ? 1_000_000_000
        : suffix === 'T'
          ? 1_000_000_000_000
          : 1
  const cleaned = trimmed.replace(/[^0-9.-]/g, '')
  const n = parseFloat(cleaned)
  return isNaN(n) ? 0 : n
    * multiplier
}

function formatVolume(v: number): string {
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`
  if (v >= 1_000) return `${(v / 1_000).toFixed(0)}K`
  return v.toFixed(0)
}

export function PriceChart({ rows, height = 360 }: Props) {
  const chartContainerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const lineSeriesRef = useRef<ISeriesApi<'Line'> | null>(null)
  const volumeSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null)
  const ohlcAvailable = rows.some(hasOHLC)
  const [mode, setMode] = useState<ChartMode>(ohlcAvailable ? 'candle' : 'line')

  useEffect(() => {
    if (!chartContainerRef.current || rows.length === 0) return

    const container = chartContainerRef.current
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark' ||
      window.matchMedia('(prefers-color-scheme: dark)').matches

    const chart = createChart(container, {
      width: container.clientWidth,
      height,
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: isDark ? '#a0a0b0' : '#555',
        fontSize: 12,
      },
      grid: {
        vertLines: { color: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.06)' },
        horzLines: { color: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.06)' },
      },
      crosshair: { mode: 0 },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false, fixLeftEdge: true, fixRightEdge: true },
    })
    chartRef.current = chart

    // Volume series (always shown)
    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume',
    })
    chart.priceScale('volume').applyOptions({
      scaleMargins: { top: 0.85, bottom: 0 },
    })
    volumeSeriesRef.current = volumeSeries

    const sortedRows = [...rows].sort((a, b) => a.date.localeCompare(b.date))

    if (mode === 'candle' && ohlcAvailable) {
      const candleSeries = chart.addSeries(CandlestickSeries, {
        upColor: '#26a69a',
        downColor: '#ef5350',
        borderDownColor: '#ef5350',
        borderUpColor: '#26a69a',
        wickDownColor: '#ef5350',
        wickUpColor: '#26a69a',
      })
      const candleData: CandlestickData[] = sortedRows
        .filter(hasOHLC)
        .map((r) => ({
          time: r.date as Time,
          open: parseNum(r.open),
          high: parseNum(r.high),
          low: parseNum(r.low),
          close: parseNum(r.close),
        }))
      candleSeries.setData(candleData)
      candleSeriesRef.current = candleSeries
    } else {
      const lineSeries = chart.addSeries(LineSeries, {
        color: isDark ? '#7c8cf8' : '#5b6abf',
        lineWidth: 2,
      })
      const lineData: LineData[] = sortedRows.map((r) => ({
        time: r.date as Time,
        value: parseNum(r.close) || parsePrice(r.price),
      }))
      lineSeries.setData(lineData)
      lineSeriesRef.current = lineSeries
    }

    // Volume data
    const volumeData = sortedRows.map((r) => {
      const vol = parseNum(r.volume)
      const close = parseNum(r.close) || parsePrice(r.price)
      const open = parseNum(r.open) || close
      return {
        time: r.date as Time,
        value: vol,
        color: close >= open ? 'rgba(38,166,154,0.3)' : 'rgba(239,83,80,0.3)',
      }
    })
    volumeSeries.setData(volumeData)

    chart.timeScale().fitContent()

    const handleResize = () => {
      if (chartContainerRef.current) {
        chart.applyOptions({ width: chartContainerRef.current.clientWidth })
      }
    }
    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      chart.remove()
      chartRef.current = null
      candleSeriesRef.current = null
      lineSeriesRef.current = null
      volumeSeriesRef.current = null
    }
  }, [rows, mode, ohlcAvailable, height])

  if (rows.length === 0) {
    return <p className="empty">Price history not available.</p>
  }

  // Summary stats
  const latestRow = rows[rows.length - 1]
  const latestVolume = parseNum(latestRow?.volume)

  return (
    <div className="price-chart-wrapper">
      <div className="price-chart-toolbar">
        {ohlcAvailable && (
          <div className="price-chart-mode-toggle">
            <button
              type="button"
              className={`preset-chip ${mode === 'candle' ? 'active' : ''}`}
              onClick={() => setMode('candle')}
            >
              캔들
            </button>
            <button
              type="button"
              className={`preset-chip ${mode === 'line' ? 'active' : ''}`}
              onClick={() => setMode('line')}
            >
              라인
            </button>
          </div>
        )}
        {latestVolume > 0 && (
          <span className="price-chart-volume-label">Vol {formatVolume(latestVolume)}</span>
        )}
      </div>
      <div ref={chartContainerRef} className="chart-container" style={{ height }} />
    </div>
  )
}
