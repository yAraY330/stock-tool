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


def _strip_suffix(t: str) -> str:
    if t.endswith(".TWO"):
        return t[:-4]
    if t.endswith(".TW"):
        return t[:-3]
    return t


def _parse_snapshot(prices: pd.Series) -> dict | None:
    """從單檔 1 年收盤序列算出快照所需欄位。資料不足回 None。"""
    prices = prices.dropna()
    n = len(prices)
    if n < 2:
        return None
    p_now  = float(prices.iloc[-1])
    p_prev = float(prices.iloc[-2])

    def _pct(offset: int) -> float | None:
        base = float(prices.iloc[-1 - offset]) if n > offset else float(prices.iloc[0])
        return round((p_now - base) / base * 100, 2) if base else None

    return {
        "price":       round(p_now, 1),
        "prev_close":  round(p_prev, 1),
        "today_pct":   round((p_now - p_prev) / p_prev * 100, 2) if p_prev else None,
        "w1_pct":      _pct(5),    # 約 1 週前（iloc[-6]）
        "m1_pct":      _pct(22),   # 約 1 月前（iloc[-23]）
        "m3_pct":      _pct(63),   # 約 3 月前（iloc[-64]）
        "week52_high": round(float(prices.max()), 1),
        "week52_low":  round(float(prices.min()), 1),
        "history_20d": [round(float(x), 1) for x in prices.iloc[-20:].tolist()],  # 舊→新
    }


def compute_snapshot_data(tickers: tuple) -> dict:
    """每日快照用（純運算、無 Streamlit / session 依賴，可離線 headless 呼叫）：
    一次 1 年下載同時取得現價、漲跌幅、52 週高低、近 20 日收盤。
    沿用 .TWO fallback。回傳
        {"market_date": "YYYY-MM-DD", "quotes": {code_無後綴: {...}},
         "stale_codes": [...], "suspect_codes": [...]}。

    刻意不 .ffill()：批次下載時 ETF 常缺最新一天的列，個股有 → 若 ffill 會把
    ETF 前一日收盤補進最新日期那格，偽造出 price==prev_close、today_pct==0 的
    假報價（非交易日污染的根因）。改成每檔用自己去 NaN 後的真實序列，並記錄
    各自的實際最後資料日期。
    - market_date：所有抓到的檔中最新的那個日期（真正來自資料，非寫死）。
    - stale_codes：該檔自己的最後日期 < market_date（確定拿到舊資料）。
    - suspect_codes：price==prev_close 且 today_pct==0（平盤保險絲，疑似；也可能
      只是真的收平盤，故與 stale 分開列，不併入同一清單）。"""
    raw = yf.download(list(tickers), period="1y", auto_adjust=True, progress=False)
    close_raw = raw["Close"]
    if isinstance(close_raw, pd.Series):
        close_raw = close_raw.to_frame(name=tickers[0])

    quotes: dict = {}
    last_dates: dict = {}
    missing: list = []

    def _absorb(frame: pd.DataFrame, col: str, code: str) -> bool:
        series = frame.get(col, pd.Series(dtype=float)).dropna()
        parsed = _parse_snapshot(series)
        if parsed:
            quotes[code] = parsed
            last_dates[code] = series.index[-1]
            return True
        return False

    for ticker in tickers:
        if not _absorb(close_raw, ticker, _strip_suffix(ticker)):
            missing.append(ticker)

    if missing:
        two_map = {t[:-3] + ".TWO": t for t in missing
                   if t.endswith(".TW") and not t.endswith(".TWO")}
        if two_map:
            try:
                raw2 = yf.download(list(two_map), period="1y", auto_adjust=True, progress=False)
                c2 = raw2["Close"]
                if isinstance(c2, pd.Series):
                    c2 = c2.to_frame(name=list(two_map)[0])
                for two_t, orig_t in two_map.items():
                    _absorb(c2, two_t, _strip_suffix(orig_t))
            except Exception:
                pass

    market_ts = max(last_dates.values()) if last_dates else None
    market_date = market_ts.strftime("%Y-%m-%d") if market_ts is not None else None

    stale_codes, suspect_codes = [], []
    for code, q in quotes.items():
        if market_ts is not None and last_dates[code] < market_ts:
            stale_codes.append(code)                     # 確定舊資料
        elif (q["price"] is not None and q["prev_close"] is not None
              and q["price"] == q["prev_close"] and q["today_pct"] == 0):
            suspect_codes.append(code)                   # 疑似平盤指紋

    return {"market_date": market_date, "quotes": quotes,
            "stale_codes": sorted(stale_codes), "suspect_codes": sorted(suspect_codes)}


@st.cache_data(ttl=300)
def get_snapshot_data(tickers: tuple) -> dict:
    """Streamlit 端入口：加 5 分鐘快取，運算與回傳與 compute_snapshot_data 完全相同。"""
    return compute_snapshot_data(tickers)


def fmt_pct(val: float) -> str:
    arrow = "▲" if val > 0 else ("▼" if val < 0 else "—")
    return f"{arrow} {abs(val):.2f}%"
