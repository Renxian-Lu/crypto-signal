from functools import lru_cache
from typing import Dict, Any, Optional
import pandas as pd
import ccxt, requests

def get_exchange(name: str = "binance"):
    ex = getattr(ccxt, name)()
    ex.enableRateLimit = True
    return ex

@lru_cache(maxsize=64)
def fetch_ohlcv_cached(symbol: str, timeframe: str = "1h", limit: int = 500, exchange: str = "binance") -> pd.DataFrame:
    ex = get_exchange(exchange)
    data = ex.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(data, columns=["ts", "open", "high", "low", "close", "volume"])
    df["ts"] = pd.to_datetime(df["ts"], unit="ms")
    return df

def fetch_funding_rate(symbol: str, exchange: str = "binance") -> Optional[Dict[str, Any]]:
    """
    Binance perpetual funding rate: symbol should be like 'ETHUSDT' (no slash)
    """
    if exchange.lower() == "binance":
        url = "https://fapi.binance.com/fapi/v1/premiumIndex"
        params = {"symbol": symbol.replace("/", "").upper()}
        try:
            r = requests.get(url, params=params, timeout=10)
            r.raise_for_status()
            data = r.json()
            return {
                "symbol": data.get("symbol"),
                "markPrice": float(data.get("markPrice", 0.0)),
                "lastFundingRate": float(data.get("lastFundingRate", 0.0)),
                "nextFundingTime": int(data.get("nextFundingTime", 0)),
                "time": int(data.get("time", 0)),
            }
        except Exception:
            return None
    return None
