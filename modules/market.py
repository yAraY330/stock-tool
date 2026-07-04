import pandas as pd
import yfinance as yf
import streamlit as st


def _parse_all_prices(close: pd.DataFrame, orig_key: str, col: str) -> dict | None:
    prices = close.get(col, pd.Series()).dropna()
    if len(prices) < 5:
        return None
    p_now = float(prices.iloc[-1])
    p_1w  = float(prices.iloc[-6]  if len(prices) >= 6  else prices.iloc[0])
    p_1m  = float(prices.iloc[-23] if len(prices) >= 23 else prices.iloc[0])
    p_3m  = float(prices.iloc[0])
    return {
        "price":  round(p_now, 1),
        "w1_pct": round((p_now - p_1w) / p_1w * 100, 2),
        "m1_pct": round((p_now - p_1m) / p_1m * 100, 2),
        "m3_pct": round((p_now - p_3m) / p_3m * 100, 2),
    }


@st.cache_data(ttl=300)
def get_all_prices(tickers: tuple) -> dict:
    raw = yf.download(list(tickers), period="3mo", auto_adjust=True, progress=False)
    close_raw = raw["Close"].ffill()
    if isinstance(close_raw, pd.Series):
        close_raw = close_raw.to_frame(name=tickers[0])
    close = close_raw.dropna(axis=1, how="all")

    result, missing = {}, []
    for ticker in tickers:
        parsed = _parse_all_prices(close, ticker, ticker)
        if parsed:
            result[ticker] = parsed
        else:
            missing.append(ticker)

    if missing:
        two_map = {t[:-3] + ".TWO": t for t in missing
                   if t.endswith(".TW") and not t.endswith(".TWO")}
        if two_map:
            try:
                raw2 = yf.download(list(two_map), period="3mo", auto_adjust=True, progress=False)
                c2 = raw2["Close"].ffill()
                if isinstance(c2, pd.Series):
                    c2 = c2.to_frame(name=list(two_map)[0])
                c2 = c2.dropna(axis=1, how="all")
                for two_t, orig_t in two_map.items():
                    parsed = _parse_all_prices(c2, orig_t, two_t)
                    if parsed:
                        result[orig_t] = parsed
            except Exception:
                pass

    return result


def _extract_ohlc(raw: pd.DataFrame, ticker: str, is_single: bool) -> pd.DataFrame:
    o  = raw["Open"]  if is_single else raw["Open"][ticker]
    h  = raw["High"]  if is_single else raw["High"][ticker]
    lo = raw["Low"]   if is_single else raw["Low"][ticker]
    c  = raw["Close"] if is_single else raw["Close"][ticker]
    return pd.DataFrame({"Open": o, "High": h, "Low": lo, "Close": c},
                        index=raw.index).dropna()


@st.cache_data(ttl=300)
def get_ohlc_batch(tickers: tuple, period: str = "1mo", interval: str = "1d") -> dict:
    """Returns {ticker: DataFrame(Open,High,Low,Close)} for K-line charts."""
    raw = yf.download(list(tickers), period=period, interval=interval, auto_adjust=True, progress=False)
    is_single = len(tickers) == 1
    result, missing = {}, []
    for ticker in tickers:
        try:
            df = _extract_ohlc(raw, ticker, is_single)
            if not df.empty:
                result[ticker] = df
            else:
                missing.append(ticker)
        except Exception:
            missing.append(ticker)

    if missing:
        two_map = {t[:-3] + ".TWO": t for t in missing
                   if t.endswith(".TW") and not t.endswith(".TWO")}
        if two_map:
            try:
                raw2 = yf.download(list(two_map), period=period, interval=interval,
                                   auto_adjust=True, progress=False)
                is_single2 = len(two_map) == 1
                for two_t, orig_t in two_map.items():
                    try:
                        df = _extract_ohlc(raw2, two_t, is_single2)
                        if not df.empty:
                            result[orig_t] = df
                    except Exception:
                        pass
            except Exception:
                pass

    return result


def _parse_current_price(close: pd.DataFrame, col: str) -> dict | None:
    prices = close.get(col, pd.Series()).dropna()
    if prices.empty:
        return None
    p_now  = float(prices.iloc[-1])
    p_prev = float(prices.iloc[-2]) if len(prices) >= 2 else None
    today_pct = round((p_now - p_prev) / p_prev * 100, 2) if p_prev else None
    return {"price": round(p_now, 1), "today_pct": today_pct}


@st.cache_data(ttl=60)
def get_current_prices(tickers: tuple) -> dict:
    """只拉現價，用於持倉頁。查無資料時自動 fallback .TWO（上櫃）。"""
    raw = yf.download(list(tickers), period="10d", auto_adjust=True, progress=False)
    close_raw = raw["Close"].ffill()
    if isinstance(close_raw, pd.Series):
        close_raw = close_raw.to_frame(name=tickers[0])
    close = close_raw.dropna(axis=1, how="all")

    result, missing = {}, []
    for ticker in tickers:
        parsed = _parse_current_price(close, ticker)
        if parsed:
            result[ticker] = parsed
        else:
            missing.append(ticker)

    if missing:
        two_map = {t[:-3] + ".TWO": t for t in missing
                   if t.endswith(".TW") and not t.endswith(".TWO")}
        if two_map:
            try:
                raw2 = yf.download(list(two_map), period="10d", auto_adjust=True, progress=False)
                c2 = raw2["Close"].ffill()
                if isinstance(c2, pd.Series):
                    c2 = c2.to_frame(name=list(two_map)[0])
                c2 = c2.dropna(axis=1, how="all")
                for two_t, orig_t in two_map.items():
                    parsed = _parse_current_price(c2, two_t)
                    if parsed:
                        result[orig_t] = parsed
            except Exception:
                pass

    return result


def fmt_pct(val: float) -> str:
    arrow = "▲" if val > 0 else ("▼" if val < 0 else "—")
    return f"{arrow} {abs(val):.2f}%"
