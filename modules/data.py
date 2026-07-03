import yfinance as yf
import pandas as pd
import streamlit as st


@st.cache_data(ttl=300)
def get_stock_info(ticker: str) -> dict:
    """拉取台股基本資料，ticker 格式如 '0050.TW'"""
    stock = yf.Ticker(ticker)
    info = stock.info

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
    """把使用者輸入的代碼轉成 yfinance 格式"""
    code = code.strip().upper()
    if not code.endswith(".TW"):
        code = code + ".TW"
    return code
