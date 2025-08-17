import { useEffect, useMemo, useState, useCallback } from 'react'
import './App.css'
import createPlotlyComponent from 'react-plotly.js/factory'
import Plotly from 'plotly.js-finance-dist'
import { fetchOHLCV, fetchIndicators, fetchSignal } from './api'
import type { OHLCV, Indicators, Signal } from './api'

const Plot = createPlotlyComponent(Plotly)

const plotConfig = { scrollZoom: true, displayModeBar: true, responsive: true, doubleClick: 'reset' } as const
const symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT'] as const
const timeframes = ['1h', '4h', '1d'] as const

// Performance optimization: Memoized thermometer component
const Thermometer = ({ value, min, max, label, unit = '', dangerZones, type = 'neutral' }: {
  value: number
  min: number
  max: number
  label: string
  unit?: string
  dangerZones?: { sell: number; buy: number }
  type?: 'rsi' | 'funding' | 'neutral'
}) => {
  // Calculate percentage for visual positioning
  const percentage = Math.max(0, Math.min(100, ((value - min) / (max - min)) * 100))

  // Determine color based on danger zones and type
  const getColor = () => {
    if (type === 'rsi') {
      if (value > 70) return '#ef5350' // Overbought - red
      if (value < 30) return '#26a69a' // Oversold - green
      return '#1f77b4' // Neutral - blue
    }
    if (type === 'funding') {
      if (value > 0.05) return '#ef5350' // High positive funding - sell
      if (value < -0.05) return '#26a69a' // High negative funding - buy
      return '#1f77b4' // Neutral
    }
    return '#1f77b4'
  }

  const color = getColor()

  // Get signal indication
  const getSignal = () => {
    if (type === 'rsi') {
      if (value > 75) return 'SELL'
      if (value < 25) return 'BUY'
      return 'NEUTRAL'
    }
    if (type === 'funding') {
      if (value > 0.05) return 'SELL'
      if (value < -0.05) return 'BUY'
      return 'NEUTRAL'
    }
    return 'NEUTRAL'
  }

  const signal = getSignal()
  const signalColor = signal === 'SELL' ? '#ef5350' : signal === 'BUY' ? '#26a69a' : '#666'

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      minWidth: 120,
      padding: 8,
      backgroundColor: '#f8f9fa',
      borderRadius: 8,
      border: `2px solid ${color}33`,
      boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
    }}>
      <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 4, color: '#333' }}>
        {label}
      </div>

      {/* Thermometer visual */}
      <div style={{
        position: 'relative',
        width: 20,
        height: 100,
        backgroundColor: '#e0e0e0',
        borderRadius: 10,
        marginBottom: 8,
        overflow: 'hidden'
      }}>
        {/* Danger zone indicators */}
        {type === 'rsi' && (
          <>
            <div style={{
              position: 'absolute',
              top: '20%',
              right: -6,
              width: 4,
              height: 2,
              backgroundColor: '#ef5350',
              borderRadius: 1
            }} />
            <div style={{
              position: 'absolute',
              top: '70%',
              right: -6,
              width: 4,
              height: 2,
              backgroundColor: '#26a69a',
              borderRadius: 1
            }} />
          </>
        )}

        {/* Fill based on value */}
        <div style={{
          position: 'absolute',
          bottom: 0,
          left: 0,
          right: 0,
          height: `${percentage}%`,
          backgroundColor: color,
          borderRadius: '0 0 10px 10px',
          transition: 'all 0.3s ease-in-out'
        }} />

        {/* Current value indicator */}
        <div style={{
          position: 'absolute',
          bottom: `${percentage}%`,
          left: '50%',
          transform: 'translate(-50%, 50%)',
          width: 6,
          height: 6,
          backgroundColor: '#fff',
          border: `2px solid ${color}`,
          borderRadius: '50%',
          boxShadow: '0 1px 3px rgba(0,0,0,0.3)'
        }} />
      </div>

      {/* Value display */}
      <div style={{
        fontSize: 14,
        fontWeight: 700,
        color: color,
        marginBottom: 2
      }}>
        {type === 'funding' ? (value * 100).toFixed(3) : value.toFixed(1)}{unit}
      </div>

      {/* Signal indicator */}
      <div style={{
        fontSize: 10,
        fontWeight: 600,
        color: signalColor,
        backgroundColor: `${signalColor}20`,
        padding: '2px 6px',
        borderRadius: 4,
        textAlign: 'center'
      }}>
        {signal}
      </div>
    </div>
  )
}

// Performance optimization: Memoized MACD indicator component
const MACDIndicator = ({ dif, dea, hist, maxAbs }: { dif: number; dea: number; hist: number; maxAbs: number }) => {
  // Signal rule kept simple
  const signal: 'BUY' | 'SELL' | 'NEUTRAL' =
    hist > 0 && dif > dea ? 'BUY' : hist < 0 && dif < dea ? 'SELL' : 'NEUTRAL'

  // Colors
  const histColor =
    hist > 0.01 ? '#26a69a' :
    hist > 0     ? '#4caf50' :
    hist < -0.01 ? '#ef5350' : '#f44336'
  const signalColor = signal === 'BUY' ? '#26a69a' : signal === 'SELL' ? '#ef5350' : '#666'

  // Normalize by recent magnitude so the bar fits the tube
  const tubeHeightPx = 100
  const max = Math.max(maxAbs || 0, 1e-8)
  const norm = Math.min(1, Math.abs(hist) / max) // 0..1
  const half = tubeHeightPx * 0.45 // headroom
  const barPx = Math.max(4, Math.round(norm * half))
  const dotBottomPct = 50 + (hist >= 0 ? norm * 45 : -norm * 45)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: 120, padding: 8, backgroundColor: '#f8f9fa', borderRadius: 8, border: `2px solid ${histColor}33`, boxShadow: '0 2px 4px rgba(0,0,0,0.1)' }}>
      <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 4, color: '#333' }}>MACD</div>

      {/* Tube */}
      <div style={{ position: 'relative', width: 20, height: tubeHeightPx, backgroundColor: '#e0e0e0', borderRadius: 10, marginBottom: 8, overflow: 'hidden' }}>
        {/* Zero line */}
        <div style={{ position: 'absolute', top: '50%', left: 0, right: 0, height: 1, backgroundColor: '#ccc', transform: 'translateY(-0.5px)' }} />
        {/* Histogram bar (up if > 0, down if < 0) */}
        <div style={{ position: 'absolute', left: '50%', top: '50%', transform: 'translateX(-50%)', width: 8, height: barPx, backgroundColor: histColor, borderRadius: 2, marginTop: hist < 0 ? 0 : -barPx, transition: 'height 0.2s ease' }} />
        {/* Indicator dot */}
        <div style={{ position: 'absolute', bottom: `${dotBottomPct}%`, left: '50%', transform: 'translate(-50%, 50%)', width: 6, height: 6, backgroundColor: '#fff', border: `2px solid ${histColor}`, borderRadius: '50%', boxShadow: '0 1px 3px rgba(0,0,0,0.3)' }} />
      </div>

      <div style={{ fontSize: 14, fontWeight: 700, color: histColor, marginBottom: 2 }}>{hist.toFixed(4)}</div>
      <div style={{ fontSize: 10, fontWeight: 600, color: signalColor, backgroundColor: `${signalColor}20`, padding: '2px 6px', borderRadius: 4, textAlign: 'center' }}>{signal}</div>
    </div>
  )
}

export default function App() {
  const [symbol, setSymbol] = useState<typeof symbols[number]>('ETH/USDT')
  const [tf, setTf] = useState<typeof timeframes[number]>('1h')
  const [ohlcv, setOhlcv] = useState<OHLCV[]>([])
  const [inds, setInds] = useState<Indicators>({})
  const [sig, setSig] = useState<Signal | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [xRange, setXRange] = useState<[string | number, string | number] | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    setXRange(null)

    try {
      const [o, i, s] = await Promise.all([
        fetchOHLCV(symbol, tf, 300),
        fetchIndicators(symbol, tf, 300),
        fetchSignal(symbol, tf, 300),
      ])
      setOhlcv(o)
      setInds(i)
      setSig(s)
    } catch (e: any) {
      setError(e?.message ?? 'Failed to load data')
    } finally {
      setLoading(false)
    }
  }, [symbol, tf])

  useEffect(() => {
    load()
  }, [load])

  const processedOHLCV = useMemo(() => {
    return ohlcv.map(row => ({
      ...row,
      ts: new Date(row.ts).getTime(),
    }))
  }, [ohlcv])

  const macdMaxAbs = useMemo(() => {
    const hs = (inds.MACD?.hist ?? []).filter((v) => Number.isFinite(v)) as number[]
    if (!hs.length) return 1e-6
    const recent = hs.slice(-200)
    const m = Math.max(...recent.map(v => Math.abs(v)))
    return m || 1e-6
  }, [inds])

  const handleRelayout = useCallback((eventData: any) => {
    if (eventData?.['xaxis.autorange'] === true) {
      setXRange(null)
      return
    }

    if (
      eventData?.['xaxis.range[0]'] != null &&
      eventData?.['xaxis.range[1]'] != null &&
      !eventData['xaxis.rangeslider.range'] &&
      !eventData['xaxis.autosize'] &&
      eventData['xaxis.range[0]'] !== eventData['xaxis.range[1]']
    ) {
      const newRange: [string | number, string | number] = [
        eventData['xaxis.range[0]'],
        eventData['xaxis.range[1]']
      ]
      setXRange(newRange)
    }
  }, [])

  const figPrice = useMemo(() => {
    if (!processedOHLCV.length) return undefined
    const x = processedOHLCV.map(r => r.ts)
    const open = processedOHLCV.map(r => r.open)
    const high = processedOHLCV.map(r => r.high)
    const low = processedOHLCV.map(r => r.low)
    const close = processedOHLCV.map(r => r.close)

    const shapes: any[] = []
    if (sig) {
      shapes.push(
        { type: 'line', xref: 'paper', x0: 0, x1: 1, y0: sig.levels.support, y1: sig.levels.support, line: { color: 'green', dash: 'dot' } },
        { type: 'line', xref: 'paper', x0: 0, x1: 1, y0: sig.levels.resistance, y1: sig.levels.resistance, line: { color: 'red', dash: 'dot' } },
      )
    }

    const layout: any = {
      margin: { l: 40, r: 40, t: 40, b: 60 },
      height: 420,
      shapes,
      showlegend: false,
      dragmode: 'pan',
      uirevision: 'price-chart',
      xaxis: {
        type: 'date',
        rangeslider: { visible: true },
        fixedrange: false,
        tickformat: tf === '1h' ? '%H:%M\n%m/%d' : tf === '4h' ? '%H:%M\n%m/%d' : '%m/%d\n%Y',
        tickmode: 'auto',
        nticks: 10,
      },
      yaxis: {
        fixedrange: false,
        title: 'Price (USDT)',
        tickformat: '.2f'
      },
    }

    if (xRange) {
      layout.xaxis.range = xRange
      layout.xaxis.autorange = false
    } else {
      layout.xaxis.autorange = true
    }

    return {
      data: [{
        type: 'candlestick',
        x,
        open,
        high,
        low,
        close,
        name: symbol,
        increasing: { line: { color: '#26a69a' } },
        decreasing: { line: { color: '#ef5350' } }
      }],
      layout
    }
  }, [processedOHLCV, symbol, sig, xRange, tf])

  const figInd = useMemo(() => {
    if (!processedOHLCV.length) return undefined
    const x = processedOHLCV.map(r => r.ts)
    const rsi = inds.RSI ?? []
    const hist = inds.MACD?.hist ?? []

    const layout: any = {
      margin: { l: 40, r: 40, t: 20, b: 40 },
      height: 320,
      barmode: 'overlay',
      showlegend: true,
      yaxis: {
        domain: [0.45, 1],
        title: 'RSI',
        fixedrange: false,
        range: [0, 100]
      },
      yaxis2: {
        domain: [0, 0.4],
        title: 'MACD',
        zeroline: true,
        zerolinecolor: '#888',
        fixedrange: false
      },
      dragmode: 'pan',
      uirevision: 'indicator-chart',
      xaxis: {
        type: 'date',
        fixedrange: false,
        tickformat: tf === '1h' ? '%H:%M\n%m/%d' : tf === '4h' ? '%H:%M\n%m/%d' : '%m/%d\n%Y',
        tickmode: 'auto',
        nticks: 8,
      },
      shapes: [
        { type: 'line', xref: 'paper', x0: 0, x1: 1, yref: 'y1', y0: 70, y1: 70, line: { dash: 'dot', color: '#ef5350', width: 1 } },
        { type: 'line', xref: 'paper', x0: 0, x1: 1, yref: 'y1', y0: 30, y1: 30, line: { dash: 'dot', color: '#26a69a', width: 1 } },
        { type: 'line', xref: 'paper', x0: 0, x1: 1, yref: 'y1', y0: 50, y1: 50, line: { dash: 'dot', color: '#888', width: 0.5 } },
      ],
    }

    if (xRange) {
      layout.xaxis.range = xRange
      layout.xaxis.autorange = false
    } else {
      layout.xaxis.autorange = true
    }

    return {
      data: [
        {
          type: 'scatter',
          mode: 'lines',
          x,
          y: rsi,
          name: 'RSI',
          line: { color: '#1f77b4', width: 2 },
          yaxis: 'y1'
        },
        {
          type: 'bar',
          x,
          y: hist,
          name: 'MACD Histogram',
          marker: {
            color: hist.map(v => (v ?? 0) >= 0 ? 'rgba(38, 166, 154, 0.7)' : 'rgba(239, 83, 80, 0.7)'),
            line: { width: 0 }
          },
          yaxis: 'y2'
        },
      ],
      layout
    }
  }, [processedOHLCV, inds, xRange, tf])

  const handleReset = useCallback(() => {
    setXRange(null)
  }, [])

  return (
    <div style={{ fontFamily: 'system-ui, sans-serif', padding: 16, maxWidth: 1200, margin: '0 auto' }}>
      <h2>Crypto Signals Dashboard</h2>

      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1fr auto auto',
        gap: 8,
        maxWidth: 700,
        position: 'sticky',
        top: 0,
        backgroundColor: 'white',
        zIndex: 10,
        padding: '8px 0',
        borderBottom: '1px solid #e0e0e0'
      }}>
        <select value={symbol} onChange={(e) => setSymbol(e.target.value as typeof symbols[number])}>
          {symbols.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <select value={tf} onChange={(e) => setTf(e.target.value as typeof timeframes[number])}>
          {timeframes.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
        <button onClick={load} disabled={loading}>
          {loading ? 'Loading…' : 'Refresh'}
        </button>
        <button onClick={handleReset} disabled={loading}>
          Reset Zoom
        </button>
      </div>

      {/* Visual Thermometer Indicators */}
      {sig && (
        <div style={{
          display: 'flex',
          justifyContent: 'center',
          gap: 16,
          margin: '16px 0',
          padding: 16,
          backgroundColor: '#f8f9fa',
          borderRadius: 12,
          boxShadow: '0 2px 8px rgba(0,0,0,0.1)'
        }}>
          <Thermometer
            value={sig.scores.rsi}
            min={0}
            max={100}
            label="RSI"
            type="rsi"
            dangerZones={{ sell: 70, buy: 30 }}
          />
          <Thermometer
            value={sig.scores.funding}
            min={-0.1}
            max={0.1}
            label="Funding Rate"
            unit="%"
            type="funding"
            dangerZones={{ sell: 0.05, buy: -0.05 }}
          />
          <MACDIndicator
            dif={sig.scores.dif}
            dea={sig.scores.dea}
            hist={sig.scores.macd_hist}
            maxAbs={macdMaxAbs}
          />

          {/* Overall Signal Display */}
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            minWidth: 120,
            padding: 16,
            backgroundColor: sig.action === 'buy' ? '#26a69a22' : sig.action === 'sell' ? '#ef535022' : '#66666622',
            borderRadius: 12,
            border: `3px solid ${sig.action === 'buy' ? '#26a69a' : sig.action === 'sell' ? '#ef5350' : '#666666'}`,
            boxShadow: '0 2px 8px rgba(0,0,0,0.15)'
          }}>
            <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 8, color: '#333' }}>
              OVERALL SIGNAL
            </div>
            <div style={{
              fontSize: 24,
              fontWeight: 800,
              color: sig.action === 'buy' ? '#26a69a' : sig.action === 'sell' ? '#ef5350' : '#666666',
              marginBottom: 8
            }}>
              {sig.action.toUpperCase()}
            </div>
            <div style={{ fontSize: 10, color: '#666', textAlign: 'center', lineHeight: 1.3 }}>
              {sig.reasons.slice(0, 2).join(' • ')}
            </div>
          </div>
        </div>
      )}

      {/* Error Display */}
      {error && (
        <div style={{
          marginTop: 8,
          padding: 12,
          backgroundColor: '#ffebee',
          color: '#c62828',
          borderRadius: 8,
          border: '1px solid #ffcdd2'
        }}>
          Error: {error}
        </div>
      )}

      {/* Charts */}
      <div style={{ marginTop: 16 }}>
        <div style={{ marginBottom: 8 }}>
          {figPrice && (
            <Plot
              data={figPrice.data as any}
              layout={figPrice.layout as any}
              config={plotConfig}
              onRelayout={handleRelayout}
              style={{ width: '100%' }}
              key={`price-${symbol}-${tf}`}
            />
          )}
        </div>
        <div>
          {figInd && (
            <Plot
              data={figInd.data as any}
              layout={figInd.layout as any}
              config={plotConfig}
              onRelayout={handleRelayout}
              style={{ width: '100%' }}
              key={`indicators-${symbol}-${tf}`}
            />
          )}
        </div>
      </div>
    </div>
  )
}
