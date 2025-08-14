"""
Signal calculation service to avoid code duplication between API and frontend
"""
from typing import Dict, List, Tuple, Any
import pandas as pd
from .indicators import rsi, macd
from .exchanges import fetch_funding_rate, fetch_funding_rate_cached

def calculate_signal(df: pd.DataFrame, symbol: str, exchange: str = "binance") -> Dict[str, Any]:
    """
    Calculate trading signal based on RSI, MACD, and funding rate

    Args:
        df: OHLCV DataFrame with close prices
        symbol: Trading pair symbol
        exchange: Exchange name

    Returns:
        Dict containing signal data: action, reasons, scores, levels

    Raises:
        Exception: If signal calculation fails
    """
    try:
        close = df["close"]
        rsi_v = rsi(close)
        dif, dea, hist = macd(close)

        # Get latest indicator values
        rsi_latest = float(rsi_v.iloc[-1])
        hist_latest = float(hist.iloc[-1])
        dif_latest = float(dif.iloc[-1])
        dea_latest = float(dea.iloc[-1])

        # Get funding rate with caching (5-minute cache)
        funding = fetch_funding_rate_cached(symbol.replace("/", ""), exchange=exchange, cache_seconds=300)
        funding_rate = float(funding["lastFundingRate"]) if funding and "lastFundingRate" in funding else 0.0

        # Calculate signal
        reasons, action = [], "wait"

        # Sell signal: RSI overbought + positive funding rate (long overheated) + MACD negative momentum
        if (rsi_latest > 75 and funding_rate > 0.0005 and hist_latest < 0):
            action = "sell"
            reasons += [
                "RSI>75 overbought",
                "Funding>0.05% long overheated",
                "MACD histogram turned negative, momentum weakening"
            ]
        # Buy signal: RSI oversold + negative funding rate (short overheated) + MACD positive momentum
        elif (rsi_latest < 40 and funding_rate < 0 and hist_latest > 0):
            action = "buy"
            reasons += [
                "RSI<40 oversold",
                "Funding<0 short overheated",
                "MACD histogram turned positive, momentum recovering"
            ]
        else:
            reasons += ["No confluence detected"]

        # Calculate support/resistance levels
        window = min(60, len(df))
        support = float(df["low"].tail(window).min())
        resistance = float(df["high"].tail(window).max())

        return {
            "action": action,
            "reasons": reasons,
            "scores": {
                "rsi": rsi_latest,
                "funding": funding_rate,
                "macd_hist": hist_latest,
                "dif": dif_latest,
                "dea": dea_latest
            },
            "levels": {
                "support": support,
                "resistance": resistance
            }
        }

    except Exception as e:
        raise Exception(f"Signal calculation failed: {str(e)}")
