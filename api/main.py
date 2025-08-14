from fastapi import FastAPI, Query
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import pandas as pd
from .models import SignalResponse
from .services.exchanges import fetch_ohlcv_cached, fetch_funding_rate
from .services.indicators import rsi, macd
from .services.signals import calculate_signal
from starlette.middleware.wsgi import WSGIMiddleware
from flask import Flask, request as flask_request

from dash import Dash, dcc, html, Input, Output, State, no_update
import plotly.graph_objects as go
import requests

from .services.exchanges import fetch_ohlcv_cached, fetch_funding_rate_cached

app = FastAPI(title="Crypto Signal API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

@app.get("/", include_in_schema=False)
def index():
    return RedirectResponse(url="/dash/")

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
        """
        Updates the price and indicator figures along with a textual signal summary for a given symbol and timeframe.

        This function fetches OHLCV (Open, High, Low, Close, Volume) data for the specified symbol and timeframe,
        calculates technical indicators (RSI and MACD), and generates visualizations for price and indicators.
        It also computes trading signals and annotates the price chart with support/resistance levels and buy/sell markers.

        Args:
            n (int): Unused parameter, reserved for future use.
            n2 (int): Unused parameter, reserved for future use.
            symbol (str): The trading pair symbol (e.g., "BTC/USDT").
            timeframe (str): The timeframe for the OHLCV data (e.g., "1h", "4h").

        Returns:
            tuple: A tuple containing:
                - fig_price (plotly.graph_objects.Figure): The price chart with candlesticks and annotations.
                - fig_ind (plotly.graph_objects.Figure): The indicator chart with RSI and MACD histogram.
                - txt (str): A textual summary of the trading signal or an error message.

        Raises:
            Exception: If data fetching or signal calculation fails, an error message is returned in the textual summary.

        Notes:
            - The function uses cached data fetching to improve performance.
            - Signal calculation logic is reused from the API's signal endpoint.
            - Visualizations are created using Plotly for interactive charts.
        """
        try:
            # Fetch data using the existing cached function
            df = fetch_ohlcv_cached(symbol, timeframe=timeframe, limit=300, exchange="binance")
            if df is None or df.empty:
                return no_update, no_update, "Data fetch failed - please try again later"

            # Get indicators using API logic (but call functions directly to avoid HTTP overhead)
            rsi_series = rsi(df["close"])
            dif, dea, hist = macd(df["close"])

            # Price figure
            fig_price = go.Figure([
                go.Candlestick(x=df["ts"], open=df["open"], high=df["high"], low=df["low"], close=df["close"])
            ])
            fig_price.update_layout(margin=dict(l=20, r=20, t=20, b=20), height=400)

            # Indicator figure with better context
            hist_vals = hist.tolist()
            hist_colors = ["#2ca02c" if v >= 0 else "#d62728" for v in hist_vals]

            fig_ind = go.Figure()
            fig_ind.add_trace(go.Scatter(x=df["ts"], y=rsi_series, name="RSI", line=dict(color="#1f77b4")))
            fig_ind.add_trace(go.Bar(x=df["ts"], y=hist_vals, name="MACD Hist", marker_color=hist_colors))
            # Helpful guide lines/regions
            fig_ind.add_hline(y=70, line_dash="dot", line_color="red")
            fig_ind.add_hline(y=30, line_dash="dot", line_color="green")
            fig_ind.add_hrect(y0=70, y1=100, line_width=0, fillcolor="rgba(255,0,0,0.08)")
            fig_ind.add_hrect(y0=0, y1=30, line_width=0, fillcolor="rgba(0,128,0,0.08)")
            fig_ind.add_hline(y=0, line_dash="dot", line_color="#888")
            fig_ind.update_layout(margin=dict(l=20, r=20, t=20, b=20), height=300)

            # Get signal using the same logic as /api/signals endpoint
            try:
                signal_data = calculate_signal(df, symbol, exchange="binance")

                # Draw support/resistance on price chart
                support = signal_data["levels"]["support"]
                resistance = signal_data["levels"]["resistance"]
                fig_price.add_hline(y=support, line_color="green", line_dash="dot", annotation_text="Support")
                fig_price.add_hline(y=resistance, line_color="red", line_dash="dot", annotation_text="Resistance")

                # Mark the last candle if buy/sell
                last_ts = df["ts"].iloc[-1]
                last_close = df["close"].iloc[-1]
                if signal_data["action"] == "buy":
                    fig_price.add_trace(go.Scatter(
                        x=[last_ts], y=[last_close],
                        mode="markers", name="BUY",
                        marker=dict(symbol="triangle-up", size=14, color="#2ca02c")
                    ))
                elif signal_data["action"] == "sell":
                    fig_price.add_trace(go.Scatter(
                        x=[last_ts], y=[last_close],
                        mode="markers", name="SELL",
                        marker=dict(symbol="triangle-down", size=14, color="#d62728")
                    ))

                # Display the values
                rsi_val = signal_data['scores']['rsi']
                funding_val = signal_data['scores']['funding']
                macd_hist_val = signal_data['scores']['macd_hist']

                txt = f"Signal: {signal_data['action'].upper()} | "
                txt += f"RSI: {rsi_val:.1f} | "
                txt += f"Funding: {funding_val:.4%} | "
                txt += f"MACD: {macd_hist_val:.4f} | "
                txt += "Reasons: " + "; ".join(signal_data['reasons'])

            except Exception as e:
                txt = f"Signal calculation failed: {str(e)}"

            return fig_price, fig_ind, txt

        except Exception as e:
            return no_update, no_update, f"Data fetch failed - please try again later: {str(e)}"

    return app_dash

dash_app = create_dash_app()
# Mount the Dash (Flask) server under /dash
app.mount("/dash", WSGIMiddleware(dash_app.server))
