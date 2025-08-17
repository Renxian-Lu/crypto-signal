from fastapi import FastAPI, Query
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from typing import Optional
from .models import SignalResponse
from .services.exchanges import fetch_ohlcv_cached, fetch_funding_rate
from .services.indicators import rsi, macd
from .services.signals import calculate_signal
import logging, asyncio, os

from .services.exchanges import fetch_ohlcv_cached, fetch_funding_rate_cached

# configure logging early (before app startup)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)

app = FastAPI(title="Crypto Signal API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
async def warm_caches():
    loop = asyncio.get_event_loop()
    pairs = [("BTC/USDT", "1h"), ("ETH/USDT", "4h")]
    try:
        tasks = [loop.run_in_executor(None, fetch_ohlcv_cached, sym, tf, 300, "binance") for sym, tf in pairs]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for (sym, tf), res in zip(pairs, results):
            if isinstance(res, Exception):
                logging.warning("Cache warm failed for %s %s: %s", sym, tf, res)
            else:
                rows = getattr(res, "shape", (0, 0))[0]
                logging.info("Cache warm completed for %s %s, rows=%d", sym, tf, rows)
    except Exception as e:
        logging.exception("Warm caches failed: %s", e)

@app.get("/", include_in_schema=False)
def index():
    return RedirectResponse(url="/docs")

@app.get("/api/ohlcv")
def get_ohlcv(symbol: str, timeframe: str = "1h", limit: int = 300, exchange: str = "binance"):
    try:
        df = fetch_ohlcv_cached(symbol, timeframe=timeframe, limit=limit, exchange=exchange)
        return {"symbol": symbol, "timeframe": timeframe, "exchange": exchange, "data": df.to_dict(orient="records")}
    except Exception as e:
        return {"error": f"Failed to fetch OHLCV data: {str(e)}", "symbol": symbol, "exchange": exchange}

@app.get("/api/indicators")
def get_indicators(symbol: str, timeframe: str = "1h", limit: int = 300, exchange: str = "binance",
                   indicators: Optional[str] = Query(None, description="Comma-separated: RSI,MACD")):
    try:
        df = fetch_ohlcv_cached(symbol, timeframe=timeframe, limit=limit, exchange=exchange)
        out = {"symbol": symbol, "timeframe": timeframe, "exchange": exchange}
        inds = [x.strip().upper() for x in indicators.split(",")] if indicators else ["RSI","MACD"]

        if "RSI" in inds:
            rsi_data = rsi(df["close"]).fillna(method="bfill")
            out["RSI"] = rsi_data.tolist()

        if "MACD" in inds:
            dif, dea, hist = macd(df["close"])
            out["MACD"] = {
                "dif": dif.fillna(method="bfill").tolist(),
                "dea": dea.fillna(method="bfill").tolist(),
                "hist": hist.fillna(method="bfill").tolist()
            }
        return out
    except Exception as e:
        return {"error": f"Failed to calculate indicators: {str(e)}", "symbol": symbol, "exchange": exchange}

@app.get("/api/funding")
def get_funding(symbol: str, exchange: str = "binance"):
    """Get funding rate data with caching for better performance."""
    try:
        sym = symbol.replace("/", "")
        data = fetch_funding_rate_cached(sym, exchange=exchange, cache_seconds=300)
        if data is None:
            return {"error": f"Funding rate not available for {symbol} on {exchange}",
                   "symbol": symbol, "exchange": exchange}
        return data
    except Exception as e:
        return {"error": f"Failed to fetch funding rate: {str(e)}",
               "symbol": symbol, "exchange": exchange}

@app.get("/api/signals", response_model=SignalResponse)
def get_signals(symbol: str, timeframe: str = "1h", limit: int = 300, exchange: str = "binance"):
    try:
        df = fetch_ohlcv_cached(symbol, timeframe=timeframe, limit=limit, exchange=exchange)
        signal_data = calculate_signal(df, symbol, exchange=exchange)

        return SignalResponse(
            symbol=symbol,
            timeframe=timeframe,
            action=signal_data["action"],
            scores=signal_data["scores"],
            reasons=signal_data["reasons"],
            levels=signal_data["levels"],
            meta={"limit": limit, "exchange": exchange}
        )
    except Exception as e:
        # Return a proper error response that matches SignalResponse structure
        return SignalResponse(
            symbol=symbol, timeframe=timeframe, action="wait",
            scores={"rsi": 0.0, "funding": 0.0, "macd_hist": 0.0, "dif": 0.0, "dea": 0.0},
            reasons=[f"Signal calculation failed: {str(e)}"],
            levels={"support": 0.0, "resistance": 0.0},
            meta={"limit": limit, "exchange": exchange, "error": str(e)}
        )

if os.getenv("SERVE_REACT", "0") == "1":
    # mount last so /api routes keep working
    app.mount("/", StaticFiles(directory="crypto-signal-frontend/dist", html=True), name="frontend")
