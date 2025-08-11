from fastapi import FastAPI, Query
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import pandas as pd
from .models import SignalResponse
from .services.exchanges import fetch_ohlcv_cached, fetch_funding_rate
from .services.indicators import rsi, macd
from starlette.middleware.wsgi import WSGIMiddleware
from flask import Flask, request as flask_request

from dash import Dash, dcc, html, Input, Output, State, no_update
import plotly.graph_objects as go
import requests

app = FastAPI(title="Crypto Signal API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

@app.get("/", include_in_schema=False)
def index():
    return RedirectResponse(url="/dash/")

@app.get("/api/ohlcv")
def get_ohlcv(symbol: str, timeframe: str = "1h", limit: int = 300, exchange: str = "binance"):
    df = fetch_ohlcv_cached(symbol, timeframe=timeframe, limit=limit, exchange=exchange)
    return {"symbol": symbol, "timeframe": timeframe, "exchange": exchange, "data": df.to_dict(orient="records")}

@app.get("/api/indicators")
def get_indicators(symbol: str, timeframe: str = "1h", limit: int = 300, exchange: str = "binance",
                   indicators: Optional[str] = Query(None, description="Comma-separated: RSI,MACD")):
    df = fetch_ohlcv_cached(symbol, timeframe=timeframe, limit=limit, exchange=exchange)
    out = {"symbol": symbol, "timeframe": timeframe, "exchange": exchange}
    inds = [x.strip().upper() for x in indicators.split(",")] if indicators else ["RSI","MACD"]
    if "RSI" in inds:
        out["RSI"] = rsi(df["close"]).fillna(method="bfill").tolist()
    if "MACD" in inds:
        dif, dea, hist = macd(df["close"])
        out["MACD"] = {"dif": dif.fillna(method="bfill").tolist(),
                       "dea": dea.fillna(method="bfill").tolist(),
                       "hist": hist.fillna(method="bfill").tolist()}
    return out

@app.get("/api/funding")
def get_funding(symbol: str, exchange: str = "binance"):
    sym = symbol.replace("/", "")
    data = fetch_funding_rate(sym, exchange=exchange)
    return data or {"error": "not available"}

@app.get("/api/signals", response_model=SignalResponse)
def get_signals(symbol: str, timeframe: str = "1h", limit: int = 300, exchange: str = "binance"):
    df = fetch_ohlcv_cached(symbol, timeframe=timeframe, limit=limit, exchange=exchange)
    close = df["close"]
    rsi_v = rsi(close)
    dif, dea, hist = macd(close)

    rsi_latest = float(rsi_v.iloc[-1]); hist_latest = float(hist.iloc[-1])
    dif_latest = float(dif.iloc[-1]);  dea_latest = float(dea.iloc[-1])

    funding = fetch_funding_rate(symbol.replace("/", ""), exchange=exchange)
    funding_rate = float(funding["lastFundingRate"]) if funding and "lastFundingRate" in funding else 0.0

    reasons, action = [], "wait"
    if (rsi_latest > 75 and funding_rate > 0.0005 and hist_latest < 0):
        action = "sell"; reasons += ["RSI>75 overbought","Funding>0.05% long overheated","MACD histogram turned negative, momentum weakening"]
    elif (rsi_latest < 40 and funding_rate < 0 and hist_latest > 0):
        action = "buy";  reasons += ["RSI<40 oversold","Funding<0 short overheated","MACD histogram turned positive, momentum recovering"]
    else:
        reasons += ["No confluence detected"]

    window = min(60, len(df))
    support = float(df["low"].tail(window).min())
    resistance = float(df["high"].tail(window).max())

    return SignalResponse(
        symbol=symbol, timeframe=timeframe, action=action,
        scores={"rsi": rsi_latest, "funding": funding_rate, "macd_hist": hist_latest, "dif": dif_latest, "dea": dea_latest},
        reasons=reasons, levels={"support": support, "resistance": resistance},
        meta={"limit": limit, "exchange": exchange}
    )

# ---- Dash lightweight shell (mounted at /dash) ----
from dash import Dash, dcc, html, Input, Output, State, no_update
import plotly.graph_objects as go
import requests

def create_dash_app() -> Dash:
    flask_server = Flask(__name__)
    # Mount Dash at root of the Flask server; FastAPI will mount it at /dash
    app_dash = Dash(
        __name__,
        server=flask_server,
        routes_pathname_prefix="/",       # inside Flask
        requests_pathname_prefix="/dash/",# external URL prefix
    )

    symbols = ["BTC/USDT","ETH/USDT","SOL/USDT"]; tfs = ["1h","4h","1d"]
    app_dash.layout = html.Div(style={"fontFamily":"sans-serif","padding":"16px"}, children=[
        html.H2("Crypto Signals Dashboard (Step 1)"),
        html.Div([
            dcc.Dropdown(symbols, value="ETH/USDT", id="symbol"),
            dcc.Dropdown(tfs, value="1h", id="timeframe"),
            html.Button("Refresh", id="refresh", n_clicks=0),
        ], style={"display":"grid","gridTemplateColumns":"1fr 1fr auto","gap":"8px","maxWidth":"600px"}),
        html.Div(id="signal_text", style={"marginTop":"8px","fontWeight":"bold"}),
        dcc.Graph(id="price_chart"), dcc.Graph(id="indicator_chart"),
        dcc.Interval(id="auto_update", interval=60_000, n_intervals=0)
    ])

    @app_dash.callback(
        [Output("price_chart","figure"), Output("indicator_chart","figure"), Output("signal_text","children")],
        [Input("refresh","n_clicks"), Input("auto_update","n_intervals")],
        [State("symbol","value"), State("timeframe","value")]
    )
    def update(n, n2, symbol, timeframe):
        try:
            df = fetch_ohlcv_cached(symbol, timeframe=timeframe, limit=300, exchange="binance")
            if df is None or df.empty:
                return no_update, no_update, "No data"

            # Indicators
            rsi_series = rsi(df["close"])
            dif, dea, hist = macd(df["close"])

            # Price figure
            fig_price = go.Figure([
                go.Candlestick(x=df["ts"], open=df["open"], high=df["high"], low=df["low"], close=df["close"])
            ])
            fig_price.update_layout(margin=dict(l=20, r=20, t=20, b=20), height=400)

            # Indicator figure
            fig_ind = go.Figure()
            fig_ind.add_trace(go.Scatter(x=df["ts"], y=rsi_series, name="RSI"))
            fig_ind.add_trace(go.Bar(x=df["ts"], y=hist, name="MACD Hist"))
            fig_ind.update_layout(margin=dict(l=20, r=20, t=20, b=20), height=300)

            # Simple signal
            rsi_latest = float(rsi_series.iloc[-1])
            hist_latest = float(hist.iloc[-1])
            dif_latest = float(dif.iloc[-1])
            dea_latest = float(dea.iloc[-1])
            funding = fetch_funding_rate(symbol.replace("/", ""), exchange="binance")
            funding_rate = float(funding["lastFundingRate"]) if funding and "lastFundingRate" in funding else 0.0

            reasons, action = [], "wait"
            if (rsi_latest > 75 and funding_rate > 0.05 and hist_latest < 0):
                action = "sell"; reasons += [
                    "RSI>75 overbought",
                    "Funding>0.05% long overheated",
                    "MACD histogram turned negative, momentum weakening"
                ]
            elif (rsi_latest < 40 and funding_rate < 0 and hist_latest > 0):
                action = "buy"; reasons += [
                    "RSI<40 oversold",
                    "Funding<0 short overheated",
                    "MACD histogram turned positive, momentum recovering"
                ]
            else:
                reasons += ["No confluence detected"]

            txt = f"Signal: {action.upper()} | Reasons: " + "; ".join(reasons)
            return fig_price, fig_ind, txt
        except Exception as e:
            return no_update, no_update, f"Error: {e}"

    return app_dash

dash_app = create_dash_app()
# Mount the Dash (Flask) server under /dash
app.mount("/dash", WSGIMiddleware(dash_app.server))
