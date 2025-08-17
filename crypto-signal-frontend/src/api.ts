import axios from 'axios'

const baseURL = import.meta.env.VITE_API_BASE_URL ?? '/api'

export const api = axios.create({
  baseURL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.code === 'ECONNREFUSED') {
      console.error('Backend server is not running. Please start the FastAPI server.')
    }
    return Promise.reject(error)
  }
)

export type OHLCV = { ts: string; open: number; high: number; low: number; close: number; volume?: number }
export type Indicators = { RSI?: number[]; MACD?: { dif: number[]; dea: number[]; hist: number[] } }
export type Signal = {
  action: 'buy' | 'sell' | 'wait'
  scores: { rsi: number; funding: number; macd_hist: number; dif: number; dea: number }
  reasons: string[]
  levels: { support: number; resistance: number }
}

export async function fetchOHLCV(symbol: string, timeframe = '1h', limit = 300) {
  const { data } = await api.get('/ohlcv', { params: { symbol, timeframe, limit } })
  return data.data as OHLCV[]
}

export async function fetchIndicators(symbol: string, timeframe = '1h', limit = 300) {
  const { data } = await api.get('/indicators', { params: { symbol, timeframe, limit, indicators: 'RSI,MACD' } })
  return data as Indicators
}

export async function fetchSignal(symbol: string, timeframe = '1h', limit = 300) {
  const { data } = await api.get('/signals', { params: { symbol, timeframe, limit } })
  return data as Signal
}
