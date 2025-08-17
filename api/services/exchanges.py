import time
from typing import Dict, Any, Optional
import pandas as pd
import ccxt, requests
import logging
from cachetools import TTLCache, cached

logger = logging.getLogger(__name__)
_funding_cache = {}

def fetch_funding_rate_cached(symbol: str, exchange: str = "binance", cache_seconds: int = 300) -> Optional[Dict]:
    """
    Cache funding rate for specified duration to reduce API calls.

    Args:
        symbol: Trading pair symbol (e.g., 'BTCUSDT')
        exchange: Exchange name (default: 'binance')
        cache_seconds: Cache duration in seconds (default: 300 = 5 minutes)

    Returns:
        Dict containing funding rate data or None if fetch fails
    """
    cache_key = f"{symbol}_{exchange}"
    current_time = time.time()

    # Check if we have valid cached data
    if cache_key in _funding_cache:
        cached_data, timestamp = _funding_cache[cache_key]
        if current_time - timestamp < cache_seconds:
            logger.debug("Returning cached funding rate for %s@%s", symbol, exchange)
            return cached_data

    # Fetch fresh data
    try:
        fresh_data = fetch_funding_rate(symbol, exchange)
        if fresh_data:
            _funding_cache[cache_key] = (fresh_data, current_time)
        return fresh_data
    except Exception as e:
        logger.exception("Error fetching funding rate for %s@%s", symbol, exchange)
        # Return cached data if available, even if expired, as fallback
        if cache_key in _funding_cache:
            cached_data, _ = _funding_cache[cache_key]
            logger.warning("Returning stale cached funding rate for %s@%s due to fetch error", symbol, exchange)
            return cached_data
        raise e

def get_exchange(name: str = "binance"):
    ex = getattr(ccxt, name)()
    ex.enableRateLimit = True
    return ex

_ohlcv_cache = TTLCache(maxsize=256, ttl=300)
@cached(_ohlcv_cache)
def fetch_ohlcv_cached(symbol: str, timeframe: str = "1h", limit: int = 500, exchange: str = "binance") -> pd.DataFrame:
    """
    Fetch OHLCV data with caching and error handling

    Args:
        symbol: Trading pair symbol (e.g., 'BTC/USDT')
        timeframe: Timeframe for data (e.g., '1h', '4h', '1d')
        limit: Number of candles to fetch
        exchange: Exchange name

    Returns:
        DataFrame with OHLCV data

    Raises:
        Exception: If data fetch fails with descriptive error message
    """
    try:
        start = time.time()
        ex = get_exchange(exchange)
        data = ex.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        if not data:
            raise Exception(f"No OHLCV data returned for {symbol} on {exchange}")

        df = pd.DataFrame(data, columns=["ts", "open", "high", "low", "close", "volume"])
        df["ts"] = pd.to_datetime(df["ts"], unit="ms")

        if df.empty:
            raise Exception(f"Empty OHLCV data received for {symbol} on {exchange}")

        return df
    except Exception as e:
        logger.exception("Failed to fetch OHLCV for %s %s on %s", symbol, timeframe, exchange)
        raise Exception(f"Failed to fetch OHLCV data for {symbol} from {exchange}: {str(e)}")
    finally:
        logger.info("fetch_ohlcv_cached %s %s took %.2fs", symbol, timeframe, time.time() - start)

def fetch_funding_rate(symbol: str, exchange: str = "binance") -> Optional[Dict[str, Any]]:
    """
    Fetch funding rate data from exchange

    Args:
        symbol: Symbol without slash (e.g., 'ETHUSDT' for Binance)
        exchange: Exchange name

    Returns:
        Dict with funding rate data or None if failed

    Note:
        Binance returns lastFundingRate as decimal (0.0001 = 0.01%)
    """
    if exchange.lower() == "binance":
        url = "https://fapi.binance.com/fapi/v1/premiumIndex"
        params = {"symbol": symbol.replace("/", "").upper()}
        try:
            r = requests.get(url, params=params, timeout=10)
            r.raise_for_status()
            data = r.json()

            if not data:
                logger.warning("Empty funding rate response for %s", symbol)
                return None

            return {
                "symbol": data.get("symbol"),
                "markPrice": float(data.get("markPrice", 0.0)),
                "lastFundingRate": float(data.get("lastFundingRate", 0.0)),
                "nextFundingTime": int(data.get("nextFundingTime", 0)),
                "time": int(data.get("time", 0)),
            }
        except requests.exceptions.RequestException as e:
            logger.warning("Network error fetching funding rate for %s: %s", symbol, str(e))
            return None
        except (ValueError, KeyError) as e:
            logger.error("Data parsing error for funding rate %s: %s", symbol, str(e))
            return None
        except Exception as e:
            logger.exception("Unexpected error fetching funding rate for %s: %s", symbol, str(e))
            return None
    else:
        logger.info("Funding rate not supported for exchange: %s", exchange)
        return None
