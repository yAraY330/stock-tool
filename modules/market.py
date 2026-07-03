import pandas as pd
import yfinance as yf
import streamlit as st


@st.cache_data(ttl=300)
def get_all_prices(tickers: tuple) -> dict:
    raw = yf.download(list(tickers), period="3mo", auto_adjust=True, progress=False)
    close_raw = raw["Close"].ffill()
    if isinstance(close_raw, pd.Series):
        close_raw = close_raw.to_frame(name=tickers[0])
    close = close_raw.dropna(axis=1, how="all")

    result = {}
    for ticker in close.columns:
        prices = close[ticker].dropna()
        if len(prices) < 5:
            continue
        p_now = float(prices.iloc[-1])
        p_1w  = float(prices.iloc[-6]  if len(prices) >= 6  else prices.iloc[0])
        p_1m  = float(prices.iloc[-23] if len(prices) >= 23 else prices.iloc[0])
        p_3m  = float(prices.iloc[0])
        result[ticker] = {
            "price":  round(p_now, 1),
            "w1_pct": round((p_now - p_1w) / p_1w * 100, 2),
            "m1_pct": round((p_now - p_1m) / p_1m * 100, 2),
            "m3_pct": round((p_now - p_3m) / p_3m * 100, 2),
        }
    return result


@st.cache_data(ttl=300)
def get_ohlc_batch(tickers: tuple, period: str = "1mo") -> dict:
    """Returns {ticker: DataFrame(Open,High,Low,Close)} for K-line charts."""
    raw = yf.download(list(tickers), period=period, auto_adjust=True, progress=False)
    is_single = len(tickers) == 1
    result = {}
    for ticker in tickers:
        try:
            o = raw["Open"]  if is_single else raw["Open"][ticker]
            h = raw["High"]  if is_single else raw["High"][ticker]
            lo = raw["Low"]  if is_single else raw["Low"][ticker]
            c = raw["Close"] if is_single else raw["Close"][ticker]
            df = pd.DataFrame({"Open": o, "High": h, "Low": lo, "Close": c},
                              index=raw.index).dropna()
            if not df.empty:
                result[ticker] = df
        except Exception:
            pass
    return result


@st.cache_data(ttl=60)
def get_current_prices(tickers: tuple) -> dict:
    """只拉現價，5 天資料，速度比 get_all_prices 快（用於持倉頁）。"""
    raw = yf.download(list(tickers), period="5d", auto_adjust=True, progress=False)
    close_raw = raw["Close"].ffill()
    if isinstance(close_raw, pd.Series):
        close_raw = close_raw.to_frame(name=tickers[0])
    close = close_raw.dropna(axis=1, how="all")
    result = {}
    for ticker in close.columns:
        prices = close[ticker].dropna()
        if prices.empty:
            continue
        result[ticker] = {"price": round(float(prices.iloc[-1]), 1)}
    return result


def fmt_pct(val: float) -> str:
    arrow = "▲" if val > 0 else ("▼" if val < 0 else "—")
    return f"{arrow} {abs(val):.2f}%"
