import yfinance as yf
import pandas as pd
import streamlit as st


@st.cache_data(ttl=300)
def get_stock_info(ticker: str) -> dict:
    """拉取台股基本資料。.TW 查無報價時自動 fallback 嘗試 .TWO（上櫃）"""
    info = yf.Ticker(ticker).info
    if not (info.get("currentPrice") or info.get("regularMarketPrice")):
        if ticker.endswith(".TW") and not ticker.endswith(".TWO"):
            alt = ticker[:-3] + ".TWO"
            alt_info = yf.Ticker(alt).info
            if alt_info.get("currentPrice") or alt_info.get("regularMarketPrice"):
                info = alt_info
    return {
        "name": info.get("longName") or info.get("shortName", ticker),
        "price": info.get("currentPrice") or info.get("regularMarketPrice"),
        "pe_ratio": info.get("trailingPE"),
        "dividend_yield": info.get("dividendYield"),
        "market_cap": info.get("marketCap"),
        "52w_high": info.get("fiftyTwoWeekHigh"),
        "52w_low": info.get("fiftyTwoWeekLow"),
        "revenue_growth": info.get("revenueGrowth"),
        "profit_margins": info.get("profitMargins"),
        "beta": info.get("beta"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "quote_type": info.get("quoteType"),
    }


@st.cache_data(ttl=300)
def get_price_history(ticker: str, period: str = "1y") -> pd.DataFrame:
    """拉取歷史價格，period 可用 '1mo','3mo','6mo','1y','2y'"""
    stock = yf.Ticker(ticker)
    return stock.history(period=period)


def format_ticker(code: str) -> str:
    """把使用者輸入的代碼轉成 yfinance 格式（已含後綴則保留）"""
    code = code.strip().upper()
    if code.endswith(".TW") or code.endswith(".TWO"):
        return code
    return code + ".TW"
