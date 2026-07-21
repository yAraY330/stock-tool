import datetime
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from modules.data import get_stock_info, get_price_history, format_ticker
from modules.evaluator import evaluate, price_position
from modules.market import get_all_prices, get_current_prices, get_ohlc_batch, fmt_pct
from modules.recommender import get_recommendations, RISK_FILTER, CATEGORIES
from modules.knowledge import CHAPTERS
from modules.portfolio import (
    get_holdings, add_holding, remove_holding, rename_account, update_holding,
    get_favorites, toggle_favorite,
    get_watchlist, add_to_watchlist, update_watchlist_item, remove_from_watchlist,
    get_accounts,
    get_quick_view_extras, add_quick_view_extra, remove_quick_view_extra,
    get_sold, sell_holding,
)

st.set_page_config(page_title="yAraY的台股溝", page_icon="📊", layout="wide")

# ── 色票常數（單一真相來源）────────────────────────────────────
C = {
    "up":         "#ff3b3b",  # 漲（紅）
    "down":       "#22e55c",  # 跌（亮綠）
    "accent_bg":  "#ffffff",  # 強調色塊背景（白）
    "accent_fg":  "#000000",  # 強調色塊文字（黑）
    "bg":         "#000000",  # 全部背景（純黑）
    "border":     "#222222",  # 邊框
    "text":       "#f1f5f9",  # 主要文字
    "text_sub":   "#666666",  # 次要文字
    "tab_off":    "#888888",  # tab 未選中文字
    "heading":    "#5eead4",  # h2/h3 標題（青綠）
}

st.markdown("""
<style>
/* ── 全域容器 ── */
.main .block-container {
    padding-top: 1.2rem;
    padding-bottom: 2rem;
    max-width: 1200px;
}

/* ── 標題 ── */
.stApp h1 {
    color: #f1f5f9;
    font-size: 2rem !important;
    font-weight: 800 !important;
    letter-spacing: -0.5px;
}

/* ── 子標題 ── */
.stApp h2, .stApp h3 {
    color: #5eead4 !important;
    font-weight: 600 !important;
}

/* ── Tab 列：方形 ── */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    background-color: #000000;
    padding: 5px;
    border-radius: 8px;
    border: 1px solid #222222;
}
.stTabs [data-baseweb="tab"] {
    height: 36px;
    border-radius: 4px;
    padding: 0 16px;
    font-size: 0.84rem;
    font-weight: 500;
    color: #888888;
    background: transparent;
    border: none;
    transition: all 0.15s ease;
}
.stTabs [aria-selected="true"] {
    background: #ffffff !important;
    color: #000000 !important;
    font-weight: 600 !important;
    box-shadow: none;
}

/* ── Metric 卡片 ── */
[data-testid="metric-container"] {
    background: #000000;
    border: 1px solid #222222;
    border-radius: 6px;
    padding: 1rem 1.25rem !important;
    box-shadow: none;
    transition: border-color 0.2s ease;
}
[data-testid="metric-container"]:hover {
    border-color: #444444;
}

/* ── Expander 卡片 ── */
details {
    border: 1px solid #222222 !important;
    border-radius: 6px !important;
    background: #000000 !important;
    margin-bottom: 6px !important;
    transition: border-color 0.2s ease;
}
details:hover {
    border-color: #444444 !important;
}
details > summary {
    padding: 0.7rem 1rem !important;
    border-radius: 6px !important;
    font-weight: 500;
}
details[open] > summary {
    border-radius: 6px 6px 0 0 !important;
    border-bottom: 1px solid #222222 !important;
    color: #f1f5f9;
}

/* ── 分隔線 ── */
hr {
    border-color: #222222 !important;
    margin: 1rem 0 !important;
}

/* ── 按鈕 ── */
.stButton > button {
    border-radius: 4px !important;
    font-weight: 500 !important;
    transition: all 0.15s ease !important;
    border: 1px solid #333333 !important;
}
.stButton > button[kind="primary"] {
    background: #ffffff !important;
    color: #000000 !important;
    border: none !important;
    box-shadow: none !important;
}
.stButton > button[kind="primary"]:hover {
    background: #e0e0e0 !important;
    transform: none;
}

/* ── 警告橫幅 ── */
.stAlert {
    border-radius: 4px !important;
    border-left: 3px solid #333333 !important;
}

/* ── 下載按鈕 ── */
.stDownloadButton > button {
    border-radius: 4px !important;
    border: 1px solid #ffffff !important;
    background: transparent !important;
    color: #ffffff !important;
}

/* ── 手機響應式 ── */
@media screen and (max-width: 768px) {
    .main .block-container {
        padding-left: 0.6rem !important;
        padding-right: 0.6rem !important;
        padding-top: 0.75rem !important;
    }
    .stApp h1 {
        font-size: 1.45rem !important;
        letter-spacing: -0.3px;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 0 3px !important;
        font-size: 0.6rem !important;
        height: 34px !important;
    }
    .stButton > button {
        min-height: 44px !important;
        font-size: 0.88rem !important;
    }
    [data-testid="metric-container"] {
        padding: 0.7rem 0.85rem !important;
    }
    details > summary {
        font-size: 0.88rem !important;
        line-height: 1.5 !important;
        padding: 0.85rem 0.9rem !important;
    }
    input[type="text"], input[type="number"] {
        font-size: 16px !important;
    }
}
</style>
""", unsafe_allow_html=True)

def _check_password() -> bool:
    if st.session_state.get("authenticated"):
        return True
    correct = None
    try:
        correct = st.secrets.get("app_password")
    except Exception:
        pass
    if not correct:
        st.session_state.authenticated = True
        return True
    st.markdown("## 🔐 yAraY的台股溝")
    pwd = st.text_input("請輸入密碼", type="password")
    if st.button("登入", type="primary", use_container_width=True):
        if pwd == correct:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("密碼錯誤")
    return False

if not _check_password():
    st.stop()

st.title("📊 yAraY的台股溝")
st.caption("⚠️ 本工具僅供個人記錄參考，不構成任何投資建議。")

for _k, _v in [("eval_ticker", ""), ("csv_imported", False), ("editing_idx", None)]:
    if _k not in st.session_state:
        st.session_state[_k] = _v


# ── 共用 helper ────────────────────────────────────────────────
def _build_by_code(items: list) -> dict:
    by_code: dict[str, dict] = {}
    for e in items:
        k = e["code"]
        if k not in by_code:
            by_code[k] = {"name": e["name"], "val": 0.0}
        by_code[k]["val"] += e["current_value"] or e["cost_basis"]
    return by_code


def _make_pie(by_code: dict, title: str, height: int = 300) -> go.Figure:
    fig = go.Figure(go.Pie(
        labels=[f"{v['name']}({k})" for k, v in by_code.items()],
        values=[v["val"] for v in by_code.values()],
        hole=0.45, textinfo="label+percent",
    ))
    fig.update_layout(title=title, height=height,
                      showlegend=False, margin=dict(l=0, r=0, t=40, b=0))
    return fig


def _make_candlestick(df: pd.DataFrame, height: int = 200) -> go.Figure:
    fig = go.Figure(go.Candlestick(
        x=df.index,
        open=df["Open"], high=df["High"],
        low=df["Low"],  close=df["Close"],
        increasing_line_color="#ff3b3b",   # 台灣：紅=漲
        decreasing_line_color="#22e55c",   # 台灣：綠=跌
    ))
    fig.update_layout(
        height=height, showlegend=False,
        xaxis_rangeslider_visible=False,
        margin=dict(l=0, r=0, t=10, b=0),
    )
    return fig


# ── 買入點提醒（頁面頂部，每次開 app 自動檢查）────────────────
_wl_targets = [w for w in get_watchlist() if float(w.get("target_price", 0)) > 0]
if _wl_targets:
    _alert_tickers = tuple(sorted({format_ticker(w["code"]) for w in _wl_targets}))
    try:
        _alert_prices = get_current_prices(_alert_tickers)
        for _w in _wl_targets:
            _cur = _alert_prices.get(format_ticker(_w["code"]), {}).get("price")
            _tgt = float(_w["target_price"])
            if _cur and _cur <= _tgt:
                st.warning(
                    f"⚡ **買入點提醒**：{_w['name']}（{_w['code']}）"
                    f"現價 **NT$ {_cur:,.1f}** 已達到你設定的目標 NT$ {_tgt:,.1f}"
                )
    except Exception:
        pass

# ── 停利／停損提醒 ────────────────────────────────────────────
_sl_holdings = [h for h in get_holdings() if h.get("stop_profit") or h.get("stop_loss")]
if _sl_holdings:
    _sl_tickers = tuple(sorted({format_ticker(h["code"]) for h in _sl_holdings}))
    try:
        _sl_prices = get_current_prices(_sl_tickers)
        for _h in _sl_holdings:
            _cur = _sl_prices.get(format_ticker(_h["code"]), {}).get("price")
            if not _cur:
                continue
            if _h.get("stop_profit") and _cur >= _h["stop_profit"]:
                st.success(
                    f"🎯 **停利提醒**：{_h['name']}（{_h['code']}）"
                    f"現價 **NT$ {_cur:,.1f}** 已達停利點 NT$ {_h['stop_profit']:,.1f}"
                )
            if _h.get("stop_loss") and _cur <= _h["stop_loss"]:
                st.error(
                    f"🛑 **停損提醒**：{_h['name']}（{_h['code']}）"
                    f"現價 **NT$ {_cur:,.1f}** 已達停損點 NT$ {_h['stop_loss']:,.1f}"
                )
    except Exception:
        pass

tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(["📊 持倉", "⚡ 速覽", "➕ 新增", "👁️ 觀察", "🔍 評估", "🎯 推薦", "📚 知識"])


# ── Tab 1: 持倉管理 ───────────────────────────────────────────
with tab1:
    st.header("我的持倉")
    holdings  = get_holdings()
    favorites = get_favorites()

    if holdings:
        accounts = get_accounts(holdings)

        # 控制列：帳號選擇 + 排序
        ctrl1, ctrl2 = st.columns([2, 3])
        with ctrl1:
            if len(accounts) > 1:
                selected_account = st.radio("帳號", ["全部帳號"] + accounts, horizontal=True)
            else:
                selected_account = "全部帳號"
        with ctrl2:
            sort_mode = st.radio(
                "排序方式",
                ["預設", "損益高→低", "帳號分組", "最愛優先"],
                horizontal=True, key="sort_mode",
            )

        # 批次拉取：統一對所有持倉
        unique_tickers = tuple(sorted({format_ticker(h["code"]) for h in holdings}))
        with st.spinner("更新市場價格中..."):
            try:
                prices_map = get_current_prices(unique_tickers)
            except Exception:
                prices_map = {}
        try:
            ohlc_map = get_ohlc_batch(unique_tickers)
        except Exception:
            ohlc_map = {}

        # 建立 enriched（含真實 index）
        all_enriched = []
        for real_idx, h in enumerate(holdings):
            ticker     = format_ticker(h["code"])
            current    = prices_map.get(ticker, {}).get("price")
            shares     = h["shares"]
            avg_cost   = h["avg_cost"]
            cost_basis = shares * avg_cost
            if current and avg_cost:
                current_value = shares * current
                pnl     = current_value - cost_basis
                pnl_pct = (current - avg_cost) / avg_cost * 100
            else:
                current_value = pnl = pnl_pct = None
            all_enriched.append({
                **h,
                "real_idx":      real_idx,
                "ticker":        ticker,
                "current":       current,
                "cost_basis":    cost_basis,
                "current_value": current_value,
                "pnl":           pnl,
                "pnl_pct":       pnl_pct,
            })

        # 篩選帳號
        enriched = (
            all_enriched if selected_account == "全部帳號"
            else [e for e in all_enriched if e.get("account", "預設帳號") == selected_account]
        )

        # ── 群組化（依代碼合併多筆交易）──
        _seen_codes: list[str] = []
        _grp: dict[str, list] = {}
        for _e0 in enriched:
            _c0 = _e0["code"]
            if _c0 not in _grp:
                _grp[_c0] = []
                _seen_codes.append(_c0)
            _grp[_c0].append(_e0)

        _gsumm: dict[str, dict] = {}
        for _c0 in _seen_codes:
            _lots0   = _grp[_c0]
            _ts0     = sum(_e0["shares"] for _e0 in _lots0)
            _tc0     = sum(_e0["cost_basis"] for _e0 in _lots0)
            _wa0     = _tc0 / _ts0 if _ts0 else 0
            _priced0 = [_e0 for _e0 in _lots0 if _e0["current"] is not None]
            _cur0    = _priced0[0]["current"] if _priced0 else None
            _tv0     = _ts0 * _cur0 if _cur0 else None
            _tpg0    = _tv0 - _tc0 if _tv0 is not None else None
            _gp0     = (_cur0 - _wa0) / _wa0 * 100 if (_cur0 and _wa0) else None
            _gsumm[_c0] = {
                "name": _lots0[0]["name"], "ticker": _lots0[0]["ticker"],
                "tot_shares": _ts0, "tot_cost": _tc0, "w_avg": _wa0,
                "cur_price": _cur0, "tot_val": _tv0, "tot_pnl": _tpg0, "g_pct": _gp0,
            }

        # 排序（群組層級）
        if sort_mode == "損益高→低":
            _seen_codes = sorted(_seen_codes,
                key=lambda _c: _gsumm[_c]["tot_pnl"] if _gsumm[_c]["tot_pnl"] is not None else float("-inf"),
                reverse=True)
        elif sort_mode == "帳號分組":
            _seen_codes = sorted(_seen_codes,
                key=lambda _c: _grp[_c][0].get("account", ""))
        elif sort_mode == "最愛優先":
            _seen_codes = sorted(_seen_codes,
                key=lambda _c: (0 if _c in favorites else 1, _grp[_c][0].get("account", "")))

        # ── 總覽 ──
        total_cost  = sum(e["cost_basis"] for e in enriched)
        priced      = [e for e in enriched if e["current_value"] is not None]
        total_value = sum(e["current_value"] for e in priced) if priced else None
        total_pnl   = (total_value - sum(e["cost_basis"] for e in priced)) if total_value else None
        total_pct   = (total_pnl / sum(e["cost_basis"] for e in priced) * 100) if total_pnl else None

        label_prefix = "" if selected_account == "全部帳號" else f"{selected_account}．"
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(f"{label_prefix}投入成本", f"NT$ {total_cost:,.0f}")
        c2.metric(f"{label_prefix}總市值",   f"NT$ {total_value:,.0f}" if total_value else "—")
        if total_pnl is not None:
            c3.metric("未實現損益", f"NT$ {total_pnl:+,.0f}", delta=f"{total_pct:+.2f}%")
        c4.metric("持有檔數", f"{len(_seen_codes)} 支")

        # ── 今日結算（以股計算，避免多筆重複）──
        today_pnl_total = 0.0
        for _c0 in _seen_codes:
            _gs0  = _gsumm[_c0]
            _tdp0 = prices_map.get(_gs0["ticker"], {}).get("today_pct")
            if _tdp0 and _gs0["cur_price"]:
                today_pnl_total += _tdp0 / 100 * _gs0["cur_price"] * _gs0["tot_shares"]
        with st.expander(f"📈 今日結算　{'▲' if today_pnl_total >= 0 else '▼'} NT$ {today_pnl_total:+,.0f}"):
            for _c0 in _seen_codes:
                _gs0  = _gsumm[_c0]
                _tdp0 = prices_map.get(_gs0["ticker"], {}).get("today_pct")
                if _tdp0 is None or not _gs0["cur_price"]:
                    continue
                _day0  = _tdp0 / 100 * _gs0["cur_price"] * _gs0["tot_shares"]
                _arr0  = "▲" if _tdp0 > 0 else "▼"
                st.caption(f"{_gs0['name']}（{_c0}）　{_arr0} {abs(_tdp0):.2f}%　今日 {_day0:+,.0f} 元")

        # ── 集中度警示（以股計算）──
        if total_value:
            for _c0 in _seen_codes:
                _gs0 = _gsumm[_c0]
                if _gs0["tot_val"] and _gs0["tot_val"] / total_value > 0.4:
                    st.warning(
                        f"⚠️ **集中度警示**：{_gs0['name']}（{_c0}）"
                        f"佔總市值 {_gs0['tot_val']/total_value*100:.1f}%，超過 40%，注意風險集中。"
                    )

        # ── 圓餅圖：全部帳號→N 個，單帳號→1 個 ──
        if selected_account == "全部帳號" and len(accounts) > 1:
            n_cols   = min(len(accounts), 3)
            pie_cols = st.columns(n_cols)
            for i, acct in enumerate(accounts):
                acct_items = [e for e in all_enriched if e.get("account", "預設帳號") == acct]
                by_code    = _build_by_code(acct_items)
                if by_code:
                    with pie_cols[i % n_cols]:
                        st.plotly_chart(_make_pie(by_code, acct, height=280), use_container_width=True)
        else:
            by_code = _build_by_code(enriched)
            if by_code:
                st.plotly_chart(_make_pie(by_code, "持倉分配（市值比例）"), use_container_width=True)

        # ── 持倉明細（群組顯示）──
        st.subheader("持倉明細")

        for _code in _seen_codes:
            _lots   = _grp[_code]
            _gs     = _gsumm[_code]
            _is_fav = _code in favorites

            _detail_key = f"h_detail_{_code}"
            _is_open    = st.session_state.get(_detail_key, False)
            _badge_txt  = _code[:4]
            _fav_star   = "★ " if _is_fav else ""
            _val_str    = f"NT$ {_gs['tot_val']:,.0f}" if _gs["tot_val"] else "—"
            _pnl_clr    = (C["up"] if (_gs["tot_pnl"] or 0) > 0
                           else C["down"] if (_gs["tot_pnl"] or 0) < 0 else C["text_sub"])
            _pnl_arr    = "▲" if (_gs["tot_pnl"] or 0) > 0 else ("▼" if (_gs["tot_pnl"] or 0) < 0 else "")
            _pnl_disp   = (f"{_pnl_arr} NT${abs(_gs['tot_pnl']):,.0f} ({abs(_gs['g_pct']):.2f}%)"
                           if _gs["tot_pnl"] is not None else "—")
            _sub_parts  = [f"{_gs['tot_shares']:.4g} 股"]
            if len(_lots) > 1:
                _sub_parts.append(f"{len(_lots)} 筆")
            if selected_account == "全部帳號":
                _accts_s = "/".join(sorted({_e.get("account", "預設帳號") for _e in _lots}))
                _sub_parts.append(_accts_s)
            _sub_line   = " · ".join(_sub_parts)

            _rca, _rcb  = st.columns([9, 1])
            with _rca:
                st.markdown(f"""<div style="display:flex;align-items:center;gap:12px;padding:10px 2px;">
  <div style="width:44px;height:44px;border-radius:4px;background:#ffffff;display:flex;align-items:center;justify-content:center;font-size:0.72rem;font-weight:700;color:#000000;flex-shrink:0;font-family:monospace;">{_badge_txt}</div>
  <div style="flex:1;min-width:0;overflow:hidden;">
    <div style="font-weight:600;font-size:0.93rem;color:#f1f5f9;">{_fav_star}{_gs['name']}</div>
    <div style="font-size:0.76rem;color:#666666;">{_sub_line}</div>
  </div>
  <div style="text-align:right;flex-shrink:0;">
    <div style="font-weight:600;font-size:0.93rem;color:#f1f5f9;">{_val_str}</div>
    <div style="font-size:0.76rem;color:{_pnl_clr};">{_pnl_disp}</div>
  </div>
</div>""", unsafe_allow_html=True)
            with _rcb:
                if st.button("▲" if _is_open else "▼", key=f"tog_{_code}", use_container_width=True):
                    st.session_state[_detail_key] = not _is_open
                    st.rerun()
            st.markdown('<div style="border-top:1px solid #222222;margin-bottom:4px;"></div>', unsafe_allow_html=True)

            if _is_open:
                # ── 群組操作列：收藏、評估頁、基本面 ──
                _gba, _gbb, _gbc = st.columns(3)
                with _gba:
                    _fl = "★ 已收藏" if _is_fav else "☆ 最愛"
                    if st.button(_fl, key=f"fav_grp_{_code}", use_container_width=True):
                        toggle_favorite(_code)
                        st.rerun()
                with _gbb:
                    if st.button("🔍 評估頁", key=f"pe_grp_{_code}", use_container_width=True):
                        st.session_state.eval_ticker = _code.replace(".TW", "")
                        st.success("請切換到「股票評估」頁面")
                with _gbc:
                    _eval_key    = f"show_eval_grp_{_code}"
                    _eval_active = st.session_state.get(_eval_key, False)
                    _eval_label  = "📊 收起" if _eval_active else "📊 基本面"
                    if st.button(_eval_label, key=f"eval_btn_grp_{_code}", use_container_width=True):
                        st.session_state[_eval_key] = not _eval_active
                        st.rerun()

                # ── 群組損益概覽 ──
                if _gs["tot_pnl"] is not None:
                    _gc1, _gc2 = st.columns(2)
                    _gc1.metric("合計未實現損益",
                                f"NT$ {_gs['tot_pnl']:+,.0f}", delta=f"{_gs['g_pct']:+.2f}%")
                    _tdp2 = prices_map.get(_gs["ticker"], {}).get("today_pct")
                    if _tdp2 is not None and _gs["cur_price"]:
                        _day2 = _tdp2 / 100 * _gs["cur_price"] * _gs["tot_shares"]
                        _gc2.metric("今日損益（合計）",
                                    f"NT$ {_day2:+,.0f}", delta=f"{_tdp2:+.2f}%")

                # ── K 線圖（每股一次）──
                if _gs["ticker"] in ohlc_map:
                    st.caption("近一個月走勢（K 線）")
                    st.plotly_chart(
                        _make_candlestick(ohlc_map[_gs["ticker"]]),
                        use_container_width=True, key=f"kline_grp_{_code}",
                    )

                # ── 基本面（群組層級）──
                if st.session_state.get(f"show_eval_grp_{_code}", False):
                    st.divider()
                    with st.spinner("載入基本面資料..."):
                        try:
                            _info = get_stock_info(_gs["ticker"])
                        except Exception:
                            _info = None
                    if _info:
                        _pos = price_position(_info)
                        if _pos:
                            _prog = int(_pos["position_pct"])
                            _p1, _p2, _p3 = st.columns(3)
                            _p1.metric("52 週高", f"NT$ {_pos['high']:,.1f}")
                            _p2.metric("目前位置", f"{_prog}%")
                            _p3.metric("52 週低", f"NT$ {_pos['low']:,.1f}")
                            st.progress(min(max(_prog / 100, 0.0), 1.0))
                            st.caption(_pos["label"])
                        if _info.get("quote_type") == "ETF":
                            st.info("📌 ETF：本益比、淨利率等指標不適用")
                        for _m in evaluate(_info)[:4]:
                            st.caption(f"**{_m['label']}**　{_m['explanation']}")
                    else:
                        st.warning("無法載入基本面資料")

                # ── 各筆買入明細 ──
                st.divider()
                if len(_lots) > 1:
                    _wp = f"NT$ {_gs['cur_price']:,.2f}" if _gs["cur_price"] else "—"
                    st.caption(
                        f"**{len(_lots)} 筆買入紀錄**　加權均價 NT$ {_gs['w_avg']:,.2f}　現價 {_wp}"
                    )

                for _li, _e in enumerate(_lots):
                    _real_idx = _e["real_idx"]
                    _pnl      = _e["pnl"]
                    _pnl_pct  = _e["pnl_pct"]

                    if len(_lots) > 1:
                        # 多筆：精簡標頭 + 細節
                        _lpnl = (f"　{_pnl:+,.0f}（{_pnl_pct:+.2f}%）"
                                 if _pnl is not None else "")
                        st.markdown(
                            f"**第 {_li + 1} 筆：** "
                            f"{_e['shares']:.4g} 股 ＠ NT$ {_e['avg_cost']:,.2f}　"
                            f"買入 {_e.get('date', '—')}　"
                            f"{_e.get('account', '預設帳號')}{_lpnl}"
                        )
                        _extras = []
                        if _e.get("buy_reason"):
                            _extras.append(f"理由：{_e['buy_reason']}")
                        if _e.get("stop_profit"):
                            _extras.append(f"停利 NT${_e['stop_profit']:,.2f}")
                        if _e.get("stop_loss"):
                            _extras.append(f"停損 NT${_e['stop_loss']:,.2f}")
                        if _e.get("dividends"):
                            _extras.append(f"已收股利 NT${_e['dividends']:,.0f}")
                        if _extras:
                            st.caption("　　" + "　｜　".join(_extras))
                        if _pnl_pct is not None and _pnl_pct < -8 and _e.get("buy_reason"):
                            st.warning(
                                f"📋 **第 {_li+1} 筆已下跌 {_pnl_pct:.1f}%，買進理由：**\n\n"
                                f"> {_e['buy_reason']}\n\n**這個理由現在還成立嗎？**"
                            )
                    else:
                        # 單筆：完整資訊
                        _ca, _cb = st.columns([3, 2])
                        with _ca:
                            st.markdown(f"**帳號：** {_e.get('account', '預設帳號')}")
                            st.markdown(f"**平均成本：** NT$ {_e['avg_cost']:,.2f}")
                            _ps = f"NT$ {_e['current']:,.2f}" if _e["current"] else "無法取得"
                            st.markdown(f"**現價：** {_ps}")
                            st.markdown(f"**持股成本：** NT$ {_e['cost_basis']:,.0f}")
                            if _e["current_value"]:
                                st.markdown(f"**目前市值：** NT$ {_e['current_value']:,.0f}")
                            if _e["date"]:
                                st.markdown(f"**買入日期：** {_e['date']}")
                            if _e["note"]:
                                st.markdown(f"**備註：** {_e['note']}")
                            if _e.get("buy_reason"):
                                st.markdown(f"**買進理由：** {_e['buy_reason']}")
                            if _e.get("stop_profit"):
                                st.markdown(f"**停利價：** NT$ {_e['stop_profit']:,.2f}")
                            if _e.get("stop_loss"):
                                st.markdown(f"**停損價：** NT$ {_e['stop_loss']:,.2f}")
                            if _e.get("dividends"):
                                _tr = (_pnl + _e["dividends"]) if _pnl else _e["dividends"]
                                st.markdown(
                                    f"**已收股利：** NT$ {_e['dividends']:,.0f}"
                                    f"　（含股利損益 NT$ {_tr:+,.0f}）"
                                )
                        with _cb:
                            if _pnl is not None:
                                st.metric("未實現損益", f"NT$ {_pnl:+,.0f}", delta=f"{_pnl_pct:+.2f}%")
                            _tp_s = prices_map.get(_e["ticker"], {}).get("today_pct")
                            if _tp_s is not None and _e["current"]:
                                _day_s = _tp_s / 100 * _e["current"] * _e["shares"]
                                st.metric("今日損益", f"NT$ {_day_s:+,.0f}", delta=f"{_tp_s:+.2f}%")
                        if _pnl_pct is not None and _pnl_pct < -8 and _e.get("buy_reason"):
                            st.warning(
                                f"📋 **這支股票已下跌 {_pnl_pct:.1f}%，當初買進理由是：**\n\n"
                                f"> {_e['buy_reason']}\n\n**這個理由現在還成立嗎？**"
                            )

                    # ── 操作按鈕（每筆都有）──
                    _ba, _bb, _bc = st.columns(3)
                    with _ba:
                        _is_editing = st.session_state.editing_idx == _real_idx
                        _el = "✏️ 收起" if _is_editing else "✏️ 編輯"
                        if st.button(_el, key=f"edit_btn_{_real_idx}", use_container_width=True):
                            st.session_state.editing_idx = None if _is_editing else _real_idx
                            st.rerun()
                    with _bb:
                        _sk = f"show_sell_{_real_idx}"
                        if _sk not in st.session_state:
                            st.session_state[_sk] = False
                        _sl2 = "💰 收起" if st.session_state[_sk] else "💰 賣出"
                        if st.button(_sl2, key=f"sell_btn_{_real_idx}", use_container_width=True):
                            st.session_state[_sk] = not st.session_state[_sk]
                            st.rerun()
                    with _bc:
                        if st.button("🗑️ 刪除", key=f"del_{_real_idx}", use_container_width=True):
                            remove_holding(_real_idx)
                            if st.session_state.editing_idx == _real_idx:
                                st.session_state.editing_idx = None
                            st.rerun()

                    # ── 賣出表單 ──
                    if st.session_state.get(f"show_sell_{_real_idx}", False):
                        st.divider()
                        with st.form(f"sell_form_{_real_idx}"):
                            _sf1, _sf2, _sf3 = st.columns(3)
                            with _sf1:
                                _s_shares = st.number_input(
                                    "賣出股數", min_value=0.01,
                                    max_value=float(_e["shares"]),
                                    value=float(_e["shares"]), step=1.0
                                )
                            with _sf2:
                                _s_price = st.number_input(
                                    "賣出均價", min_value=0.01,
                                    value=float(_e["current"] or _e["avg_cost"]),
                                    step=0.01, format="%.2f"
                                )
                            with _sf3:
                                _s_date = st.date_input("賣出日期", value=datetime.date.today())
                            _sell_ok = st.form_submit_button("確認賣出", type="primary", use_container_width=True)
                        if _sell_ok:
                            sell_holding(_real_idx, _s_price, str(_s_date), _s_shares)
                            st.session_state[f"show_sell_{_real_idx}"] = False
                            st.success(
                                f"✅ 已記錄賣出 {_s_shares:.4g} 股，"
                                f"損益 NT$ {(_s_price - _e['avg_cost']) * _s_shares:+,.0f}"
                            )
                            st.rerun()

                    # ── 編輯表單 ──
                    if st.session_state.editing_idx == _real_idx:
                        st.divider()
                        _cur_acct = _e.get("account", "預設帳號")
                        _ai = accounts.index(_cur_acct) if _cur_acct in accounts else 0
                        try:
                            _def_date = datetime.date.fromisoformat(_e.get("date", ""))
                        except (ValueError, TypeError):
                            _def_date = datetime.date.today()

                        with st.form(f"edit_form_{_real_idx}"):
                            _ef1, _ef2, _ef3, _ef4 = st.columns(4)
                            with _ef1:
                                _e_acct   = st.selectbox("帳號", accounts, index=_ai)
                            with _ef2:
                                _e_shares = st.number_input("股數", min_value=0.01,
                                                             value=float(_e["shares"]), step=1.0)
                            with _ef3:
                                _e_cost   = st.number_input("平均成本", min_value=0.01,
                                                             value=float(_e["avg_cost"]),
                                                             step=0.01, format="%.2f")
                            with _ef4:
                                _e_date   = st.date_input("買入日期", value=_def_date)
                            _ef5, _ef6, _ef7 = st.columns(3)
                            with _ef5:
                                _e_sp = st.number_input("停利價（0=未設）", min_value=0.0,
                                                         value=float(_e.get("stop_profit", 0)),
                                                         step=0.5, format="%.2f")
                            with _ef6:
                                _e_sl = st.number_input("停損價（0=未設）", min_value=0.0,
                                                         value=float(_e.get("stop_loss", 0)),
                                                         step=0.5, format="%.2f")
                            with _ef7:
                                _e_div = st.number_input("已收股利（元）", min_value=0.0,
                                                          value=float(_e.get("dividends", 0)),
                                                          step=100.0, format="%.0f")
                            _e_reason = st.text_input("買進理由", value=_e.get("buy_reason", ""),
                                                       placeholder="例：本益比偏低、財報轉機")
                            _sv_col, _cl_col = st.columns(2)
                            with _sv_col:
                                _save_clicked   = st.form_submit_button("💾 儲存",
                                                      type="primary", use_container_width=True)
                            with _cl_col:
                                _cancel_clicked = st.form_submit_button("✖ 取消",
                                                      use_container_width=True)

                        if _save_clicked:
                            update_holding(_real_idx, shares=_e_shares, avg_cost=_e_cost,
                                           account=_e_acct, date=str(_e_date),
                                           stop_profit=_e_sp, stop_loss=_e_sl,
                                           dividends=_e_div, buy_reason=_e_reason)
                            st.session_state.editing_idx = None
                            st.rerun()
                        if _cancel_clicked:
                            st.session_state.editing_idx = None
                            st.rerun()

                    if len(_lots) > 1 and _li < len(_lots) - 1:
                        st.divider()

        # ── 已賣出紀錄 ──
        _sold = get_sold()
        if _sold:
            st.divider()
            with st.expander(f"📋 已賣出紀錄（共 {len(_sold)} 筆）"):
                sold_rows = []
                for s in _sold:
                    sold_rows.append({
                        "股票":    f"{s['name']}（{s['code']}）",
                        "帳號":    s.get("account", ""),
                        "股數":    s["shares"],
                        "買入均價": f"NT$ {s['avg_cost']:,.2f}",
                        "賣出均價": f"NT$ {s['sell_price']:,.2f}",
                        "買入日":  s.get("buy_date", ""),
                        "賣出日":  s.get("sell_date", ""),
                        "已實現損益": f"NT$ {s['pnl']:+,.0f}",
                    })
                st.dataframe(pd.DataFrame(sold_rows), use_container_width=True, hide_index=True)
                total_realized = sum(s["pnl"] for s in _sold)
                total_div      = sum(s.get("dividends", 0) for s in _sold)
                st.metric("已實現總損益", f"NT$ {total_realized:+,.0f}")
                if total_div > 0:
                    st.metric("歷史股利合計", f"NT$ {total_div:,.0f}")

        # ── 帳號管理 ──
        st.divider()
        with st.expander("⚙️ 帳號管理"):
            rename_acct = st.selectbox("選擇要改名的帳號", accounts, key="rename_select")
            rename_new  = st.text_input("新名稱", key="rename_input", placeholder="例：永豐金、凱基")
            if st.button("確認改名", key="rename_btn"):
                new_stripped = rename_new.strip()
                if not new_stripped:
                    st.error("請輸入新名稱")
                elif new_stripped == rename_acct:
                    st.warning("新名稱與原名稱相同")
                elif new_stripped in accounts:
                    st.error(f"「{new_stripped}」已存在，請換一個名稱")
                else:
                    rename_account(rename_acct, new_stripped)
                    st.success(f"已將「{rename_acct}」改為「{new_stripped}」")
                    st.rerun()

    else:
        st.info("目前沒有持倉記錄。請前往「➕ 新增持倉」頁面新增你的第一筆。")


# ── Tab 2: 速覽 ──────────────────────────────────────────────
with tab2:
    st.header("速覽表")

    sv_holdings = get_holdings()
    sv_extras   = get_quick_view_extras()
    sv_holding_codes = {h["code"] for h in sv_holdings}

    sv_holding_tickers = tuple(sorted({format_ticker(h["code"]) for h in sv_holdings}))
    sv_extra_tickers   = tuple(sorted({format_ticker(e["code"]) for e in sv_extras}))
    sv_all_tickers     = tuple(sorted(set(sv_holding_tickers) | set(sv_extra_tickers)))

    if sv_all_tickers:
        with st.spinner("載入資料中..."):
            try:
                sv_prices = get_current_prices(sv_all_tickers)
            except Exception:
                sv_prices = {}

        # ── 建立持倉 P&L 查詢表（依代碼合併多筆）──
        sv_pnl_map = {}
        for h in sv_holdings:
            ticker = format_ticker(h["code"])
            cur    = sv_prices.get(ticker, {}).get("price")
            code   = h["code"]
            if code not in sv_pnl_map:
                sv_pnl_map[code] = {"tot_shares": 0, "tot_cost": 0, "cur": cur}
            sv_pnl_map[code]["tot_shares"] += h["shares"]
            sv_pnl_map[code]["tot_cost"]   += h["shares"] * h["avg_cost"]
        for _sc, _sd in sv_pnl_map.items():
            _sc_cur = _sd["cur"]
            if _sc_cur and _sd["tot_shares"]:
                _sd["tot_val"] = _sc_cur * _sd["tot_shares"]
                _sd["pnl"]     = _sd["tot_val"] - _sd["tot_cost"]
                _sd["pnl_pct"] = _sd["pnl"] / _sd["tot_cost"] * 100
            else:
                _sd["tot_val"] = _sd["pnl"] = _sd["pnl_pct"] = None

        # ── K 線區間 ──
        _period_map   = {"當日": ("1d", "15m"), "週": ("5d", "1d"), "月": ("1mo", "1d")}
        sv_period_sel = st.radio("K 線區間", list(_period_map), horizontal=True, index=2)
        _kline_period, _kline_interval = _period_map[sv_period_sel]
        with st.spinner("載入 K 線資料中..."):
            try:
                sv_ohlc = get_ohlc_batch(sv_all_tickers, period=_kline_period, interval=_kline_interval)
            except Exception:
                sv_ohlc = {}

        # ── 顯示順序：持倉優先，再額外追蹤 ──
        sv_display, sv_seen = [], set()
        for h in sv_holdings:
            if h["code"] not in sv_seen:
                sv_display.append({"code": h["code"], "name": h["name"], "is_holding": True})
                sv_seen.add(h["code"])
        for e in sv_extras:
            if e["code"] not in sv_seen:
                sv_display.append({"code": e["code"], "name": e["name"], "is_holding": False})
                sv_seen.add(e["code"])

        # ── 合併卡片（資訊 + K 線）──
        for i in range(0, len(sv_display), 2):
            cols = st.columns(2)
            for j, item in enumerate(sv_display[i:i + 2]):
                ticker    = format_ticker(item["code"])
                price_now = sv_prices.get(ticker, {}).get("price")
                today_pct = sv_prices.get(ticker, {}).get("today_pct")
                price_str = f"NT$ {price_now:,.1f}" if price_now else "—"
                td_clr    = C["up"] if (today_pct or 0) > 0 else (C["down"] if (today_pct or 0) < 0 else C["text_sub"])
                td_arr    = "▲" if (today_pct or 0) > 0 else ("▼" if (today_pct or 0) < 0 else "")
                td_str    = f"{td_arr} {abs(today_pct):.2f}%" if today_pct is not None else "—"
                badge_txt = item["code"][:4]
                fav_star  = "★ " if item["is_holding"] else ""

                with cols[j]:
                    with st.container(border=True):
                        st.markdown(f"""<div style="display:flex;align-items:center;gap:10px;padding:4px 2px 4px 2px;">
  <div style="width:38px;height:38px;border-radius:4px;background:#ffffff;display:flex;align-items:center;justify-content:center;font-size:0.68rem;font-weight:700;color:#000000;flex-shrink:0;font-family:monospace;">{badge_txt}</div>
  <div style="flex:1;min-width:0;">
    <div style="font-weight:600;font-size:0.85rem;color:#f1f5f9;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{fav_star}{item['name']}</div>
    <div style="font-size:0.7rem;color:#666666;">{item['code']}</div>
  </div>
  <div style="text-align:right;flex-shrink:0;">
    <div style="font-weight:700;font-size:0.88rem;color:#f1f5f9;">{price_str}</div>
    <div style="font-size:0.7rem;color:{td_clr};">{td_str}</div>
  </div>
</div>""", unsafe_allow_html=True)
                        if ticker in sv_ohlc:
                            st.plotly_chart(
                                _make_candlestick(sv_ohlc[ticker], height=150),
                                use_container_width=True,
                                key=f"sv_kline_{item['code']}",
                            )
                        else:
                            st.caption("無法載入 K 線資料")
                        if item["is_holding"] and item["code"] in sv_pnl_map:
                            _pd = sv_pnl_map[item["code"]]
                            if _pd["pnl"] is not None:
                                _p_clr = C["up"] if _pd["pnl"] > 0 else C["down"]
                                _p_arr = "▲" if _pd["pnl"] > 0 else "▼"
                                st.markdown(
                                    f'<div style="display:flex;justify-content:space-between;'
                                    f'padding:2px 2px 4px 2px;font-size:0.75rem;">'
                                    f'<span style="color:#666666;">未實現損益</span>'
                                    f'<span style="color:{_p_clr};font-weight:600;">'
                                    f'{_p_arr} NT${abs(_pd["pnl"]):,.0f} ({abs(_pd["pnl_pct"]):.2f}%)'
                                    f'</span></div>',
                                    unsafe_allow_html=True,
                                )
                        if not item["is_holding"]:
                            if st.button("移除", key=f"sv_rm_{item['code']}", use_container_width=True):
                                remove_quick_view_extra(item["code"])
                                st.rerun()
    else:
        st.info("持倉為空。新增持倉後，速覽表會自動顯示。")

    # ── 新增額外追蹤股票 ──
    st.divider()
    st.subheader("➕ 新增其他股票到速覽表")
    with st.form("sv_add_form", clear_on_submit=True):
        sv_code      = st.text_input("股票代碼", placeholder="例：0050、2330")
        sv_submitted = st.form_submit_button("加入", type="primary", use_container_width=True)

    if sv_submitted:
        if not sv_code.strip():
            st.error("請輸入股票代碼")
        else:
            sv_ticker_input = format_ticker(sv_code.strip())
            existing_codes  = {e["code"] for e in sv_extras} | sv_holding_codes
            if sv_code.strip().upper() in existing_codes:
                st.warning("此股票已在速覽表中")
            else:
                try:
                    sv_info = get_stock_info(sv_ticker_input)
                    sv_name = sv_info.get("name") or sv_code.strip().upper()
                    if not sv_info.get("price"):
                        st.error("找不到此股票代碼，請確認後再試")
                    else:
                        add_quick_view_extra(sv_code.strip().upper(), sv_name)
                        st.success(f"✅ 已加入：{sv_name}（{sv_code.strip().upper()}）")
                        st.rerun()
                except Exception:
                    st.error("查詢失敗，請確認代碼是否正確")


# ── Tab 3: 新增持倉 ───────────────────────────────────────────
with tab3:
    st.header("新增持倉")

    _has_sheets = False
    try:
        _has_sheets = "sheet_id" in st.secrets
    except Exception:
        pass
    if not _has_sheets:
        st.warning(
            "💾 **資料暫存中** — 目前沒有設定 Google Sheets，"
            "資料存在本機，App 重新啟動後會消失。"
            "請參考專案中的 **SETUP.md** 完成 Google Sheets 設定以永久保存資料。"
        )

    st.subheader("手動新增")
    existing_accounts = get_accounts(get_holdings())
    with st.form("add_holding_form", clear_on_submit=True):
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            new_code   = st.text_input("股票代碼", placeholder="例：2330")
        with c2:
            new_shares = st.number_input("股數", min_value=0.0, step=1.0, format="%.4g")
        with c3:
            new_cost   = st.number_input("平均成本（元）", min_value=0.0, step=0.01, format="%.2f")
        with c4:
            new_date   = st.date_input("買入日期")
        with c5:
            acct_options = existing_accounts + (["＋新增帳號"] if existing_accounts else [])
            if acct_options:
                acct_select = st.selectbox("帳號", acct_options)
            else:
                acct_select = "＋新增帳號"
            if acct_select == "＋新增帳號" or not acct_options:
                new_account = st.text_input("帳號名稱", placeholder="例：永豐、富邦")
            else:
                new_account = acct_select
        ca1, ca2, ca3 = st.columns(3)
        with ca1:
            new_sp = st.number_input("停利價（選填，0=未設）", min_value=0.0, step=0.5, format="%.2f")
        with ca2:
            new_sl = st.number_input("停損價（選填，0=未設）", min_value=0.0, step=0.5, format="%.2f")
        with ca3:
            new_note = st.text_input("備註（選填）", placeholder="例：定期定額、逢低加碼")
        new_reason = st.text_input("買進理由（選填）", placeholder="例：本益比低於同業、財報轉機、殖利率高")
        submitted = st.form_submit_button("新增", type="primary", use_container_width=True)

    if submitted:
        account_name = new_account.strip() if new_account.strip() else "預設帳號"
        if not new_code.strip():
            st.error("請輸入股票代碼")
        elif new_shares <= 0:
            st.error("股數必須大於 0")
        elif new_cost <= 0:
            st.error("成本必須大於 0")
        else:
            ticker = format_ticker(new_code.strip())
            try:
                info       = get_stock_info(ticker)
                stock_name = info.get("name") or new_code.strip().upper()
            except Exception:
                stock_name = new_code.strip().upper()
            add_holding(new_code.strip().upper(), stock_name,
                        new_shares, new_cost, str(new_date), new_note, account_name,
                        stop_profit=new_sp, stop_loss=new_sl, buy_reason=new_reason.strip())
            st.success(f"✅ 已新增【{account_name}】{stock_name}（{new_code.strip().upper()}）{new_shares:.4g} 股")
            st.rerun()

    # ── 匯出現有持倉（換到雲端時用）──
    holdings_now = get_holdings()
    if holdings_now:
        st.divider()
        st.subheader("📤 匯出持倉 CSV")
        st.caption("換到雲端版時，先匯出、部署後再用「從 CSV 批次匯入」還原資料。")
        _df_exp = pd.DataFrame(holdings_now).reindex(
            columns=["code", "name", "shares", "avg_cost", "account", "date", "note"],
            fill_value="",
        )
        _df_exp.columns = ["股票代碼", "股票名稱", "股數", "平均成本", "帳號", "買入日期", "備註"]
        st.download_button(
            "⬇️ 下載持倉 CSV",
            data=_df_exp.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig"),
            file_name="我的持倉.csv",
            mime="text/csv",
        )

    st.divider()
    st.subheader("從 CSV 批次匯入")
    st.caption("適合一次匯入多筆持倉，例如從券商對帳單整理後匯入。")

    _TEMPLATE = (
        "股票代碼,股數,平均成本,帳號,買入日期,備註\n"
        "2330,100,850.00,永豐,2024-01-15,範例請刪除\n"
        "0050,500,145.00,富邦,2024-03-01,範例請刪除\n"
    )
    st.download_button(
        "📄 下載 CSV 範本",
        data=_TEMPLATE.encode("utf-8-sig"),
        file_name="持倉範本.csv",
        mime="text/csv",
    )
    st.markdown("**使用步驟：** ① 下載範本 → ② 用 Excel 填入資料（刪掉範例列）→ ③ 存成 CSV → ④ 上傳")

    uploaded = st.file_uploader("上傳 CSV 檔案", type=["csv"], key="csv_upload")

    if uploaded and not st.session_state.csv_imported:
        try:
            try:
                df_csv = pd.read_csv(uploaded, encoding="utf-8-sig", dtype=str)
            except UnicodeDecodeError:
                uploaded.seek(0)
                df_csv = pd.read_csv(uploaded, encoding="big5", dtype=str)

            required_cols = ["股票代碼", "股數", "平均成本"]
            missing_cols  = [c for c in required_cols if c not in df_csv.columns]
            if missing_cols:
                st.error(f"缺少必要欄位：{'、'.join(missing_cols)}　請使用官方範本格式")
            else:
                df_csv = df_csv.dropna(subset=required_cols)
                df_csv = df_csv[df_csv["股票代碼"].str.strip() != ""]
                try:
                    df_csv = df_csv[pd.to_numeric(df_csv["股數"],    errors="coerce") > 0]
                    df_csv = df_csv[pd.to_numeric(df_csv["平均成本"], errors="coerce") > 0]
                except Exception:
                    st.error("「股數」或「平均成本」欄位包含無效數字")
                    df_csv = pd.DataFrame()

                if not df_csv.empty:
                    st.caption(f"預覽（共 {len(df_csv)} 筆，確認無誤後點擊匯入）")
                    st.dataframe(df_csv.reset_index(drop=True), use_container_width=True, hide_index=True)

                    if st.button(f"✅ 確認匯入 {len(df_csv)} 筆", type="primary"):
                        with st.spinner("匯入中，自動查詢股票名稱..."):
                            for _, row in df_csv.iterrows():
                                code     = str(row["股票代碼"]).strip().upper()
                                shares   = float(row["股數"])
                                avg_cost = float(row["平均成本"])
                                account  = str(row.get("帳號", "")).strip()
                                date     = str(row.get("買入日期", "")).strip()
                                note     = str(row.get("備註", "")).strip()
                                if account in ("", "nan"):
                                    account = "預設帳號"
                                if date  == "nan": date  = ""
                                if note  == "nan": note  = ""
                                try:
                                    info = get_stock_info(format_ticker(code))
                                    name = info.get("name") or code
                                except Exception:
                                    name = code
                                add_holding(code, name, shares, avg_cost, date, note, account)
                        st.session_state.csv_imported = True
                        st.rerun()

        except Exception as ex:
            st.error(f"讀取 CSV 失敗：{ex}")

    if st.session_state.csv_imported:
        st.success("✅ 匯入完成！切換到「持倉管理」頁面查看結果。")
        if st.button("匯入另一份 CSV"):
            st.session_state.csv_imported = False
            st.rerun()


# ── Tab 4: 觀察清單 ───────────────────────────────────────────
with tab4:
    st.header("觀察清單")
    watchlist = get_watchlist()

    if watchlist:
        wl_tickers = tuple(format_ticker(w["code"]) for w in watchlist)
        with st.spinner("更新報價中..."):
            try:
                wl_prices = get_all_prices(wl_tickers)
            except Exception:
                wl_prices = {}

        for i, w in enumerate(watchlist):
            ticker    = format_ticker(w["code"])
            pd_       = wl_prices.get(ticker, {})
            price     = pd_.get("price")
            w1        = pd_.get("w1_pct")
            m1        = pd_.get("m1_pct")
            price_str = f"NT$ {price:,.1f}" if price else "—"
            w1_str    = fmt_pct(w1) if w1 is not None else "—"
            m1_str    = fmt_pct(m1) if m1 is not None else "—"

            with st.expander(
                f"👁️ {w['name']}（{w['code']}）　"
                f"現價 {price_str}　1週 {w1_str}　1月 {m1_str}"
            ):
                if w.get("note"):
                    st.markdown(f"**備註：** {w['note']}")
                ca, cb, cc = st.columns(3)
                with ca:
                    if price:
                        st.metric("現價", f"NT$ {price:,.1f}")
                with cb:
                    if w1 is not None:
                        st.metric("本週", fmt_pct(w1))
                with cc:
                    if m1 is not None:
                        st.metric("本月", fmt_pct(m1))
                # ── 目標買入價 ──
                target = float(w.get("target_price", 0))
                if target > 0:
                    if price and price <= target:
                        st.success(f"⚡ 已達到目標買入價 NT$ {target:,.2f}！現價 NT$ {price:,.1f}")
                    elif price:
                        st.info(f"🎯 目標買入價：NT$ {target:,.2f}　（現價還需再跌 NT$ {price - target:,.1f}）")
                    else:
                        st.info(f"🎯 目標買入價：NT$ {target:,.2f}")

                tgt_key = f"edit_tgt_{i}"
                if tgt_key not in st.session_state:
                    st.session_state[tgt_key] = False

                wb1, wb2, wb3 = st.columns(3)
                with wb1:
                    tgt_label = "✏️ 收起" if st.session_state[tgt_key] else "🎯 目標價"
                    if st.button(tgt_label, key=f"tgt_btn_{i}", use_container_width=True):
                        st.session_state[tgt_key] = not st.session_state[tgt_key]
                        st.rerun()
                with wb2:
                    if st.button("🔍 評估", key=f"we_{i}", use_container_width=True):
                        st.session_state.eval_ticker = w["code"]
                        st.success("請切換到「股票評估」頁面")
                with wb3:
                    if st.button("🗑️ 移除", key=f"wr_{i}", use_container_width=True):
                        remove_from_watchlist(i)
                        st.rerun()

                if st.session_state[tgt_key]:
                    with st.form(f"tgt_form_{i}"):
                        new_target = st.number_input(
                            "目標買入價（填 0 表示取消設定）",
                            min_value=0.0, value=target, step=0.5, format="%.2f",
                        )
                        if st.form_submit_button("💾 儲存", type="primary",
                                                  use_container_width=True):
                            update_watchlist_item(i, target_price=new_target)
                            st.session_state[tgt_key] = False
                            st.rerun()
    else:
        st.info("觀察清單是空的，請使用下方表單新增你想追蹤的股票。")

    st.divider()
    st.subheader("➕ 新增觀察標的")
    with st.form("add_watchlist_form", clear_on_submit=True):
        wc1, wc2, wc3 = st.columns([1, 2, 1])
        with wc1:
            wl_code   = st.text_input("股票代碼", placeholder="例：0050")
        with wc2:
            wl_note   = st.text_input("備註（選填）", placeholder="例：等拉回再買")
        with wc3:
            wl_target = st.number_input(
                "目標買入價（選填）", min_value=0.0, step=0.5, format="%.2f",
                help="股價跌至此價位時，app 頂端會出現提醒。填 0 表示不設定。",
            )
        wl_submitted = st.form_submit_button("加入觀察", type="primary", use_container_width=True)

    if wl_submitted:
        if not wl_code.strip():
            st.error("請輸入股票代碼")
        else:
            ticker = format_ticker(wl_code.strip())
            try:
                info    = get_stock_info(ticker)
                wl_name = info.get("name") or wl_code.strip().upper()
                if not info.get("price"):
                    st.error("找不到此股票代碼，請確認後再試")
                else:
                    add_to_watchlist(wl_code.strip().upper(), wl_name, wl_note, wl_target)
                    st.success(f"✅ 已加入觀察清單：{wl_name}（{wl_code.strip().upper()}）")
                    st.rerun()
            except Exception:
                st.error("查詢失敗，請確認代碼是否正確")


# ── Tab 5: 股票評估 ───────────────────────────────────────────
with tab5:
    st.header("股票評估工具")
    st.write("輸入台股代碼，解讀這支股票的基本面數字。")

    ticker_input = st.text_input(
        "台股代碼（例：0050、2330、00878）",
        value=st.session_state.eval_ticker,
        placeholder="輸入代碼後按 Enter 或點擊評估",
    )

    if st.button("評估這支股票", type="primary") and ticker_input:
        ticker = format_ticker(ticker_input)
        info, history = None, None
        with st.spinner(f"正在拉取 {ticker} 的資料..."):
            try:
                info    = get_stock_info(ticker)
                history = get_price_history(ticker, "1y")
            except Exception as e:
                st.error(f"資料拉取失敗：{e}")

        if info is not None and not info.get("price"):
            st.error("找不到這個代碼的資料，請確認輸入是否正確。")
            info = None

        if info is not None:
            st.subheader(f"{info['name']} （{ticker_input.upper()}）")
            if info.get("sector"):
                st.caption(f"產業：{info['sector']} — {info.get('industry', '')}")

            pos = price_position(info)
            if pos:
                col1, col2, col3 = st.columns(3)
                col1.metric("目前股價", f"NT$ {pos['price']:,.1f}")
                col2.metric("52週高點", f"NT$ {pos['high']:,.1f}")
                col3.metric("52週低點", f"NT$ {pos['low']:,.1f}")
                progress = int(pos["position_pct"])
                st.progress(min(max(progress / 100, 0.0), 1.0))
                st.caption(f"目前股價在52週區間的 {progress}% 位置 — {pos['label']}")

            if history is not None and not history.empty:
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=history.index, y=history["Close"],
                    mode="lines", name="收盤價",
                    line=dict(color="#5eead4", width=2),
                ))
                fig.update_layout(
                    title="近一年股價走勢",
                    xaxis_title="日期", yaxis_title="股價（NTD）",
                    height=350, margin=dict(l=0, r=0, t=40, b=0),
                )
                st.plotly_chart(fig, use_container_width=True)

            st.divider()
            st.subheader("基本面指標解讀")
            is_etf = info.get("quote_type") == "ETF"
            if is_etf:
                st.info("📌 ETF 是一籃子股票，不是單一公司，所以本益比、淨利率、營收成長率這類指標通常沒有資料。這是正常現象。")
            for m in evaluate(info):
                with st.expander(f"📊 {m['label']}　→　{m['explanation']}"):
                    st.info(f"💬 新手小知識：{m['beginner_tip']}")


# ── Tab 6: 新手推薦 ───────────────────────────────────────────
with tab6:
    st.header("新手股票推薦")
    st.caption("根據你的條件篩選台股標的，所有內容僅供參考，不構成投資建議。")

    rf1, rf2, rf3 = st.columns(3)
    with rf1:
        rec_risk = st.radio("風險偏好", list(RISK_FILTER.keys()), key="rec_risk")
    with rf2:
        rec_goal = st.radio("投資目標", ["長期增值", "被動收入", "短期獲利"], key="rec_goal")
    with rf3:
        rec_cat = st.selectbox("股票類別", CATEGORIES, key="rec_cat")

    picks, empty_msg = get_recommendations(rec_risk, rec_goal, rec_cat)

    st.divider()
    if empty_msg:
        st.warning(empty_msg)
    elif not picks:
        st.info("沒有符合條件的標的，請調整篩選條件。")
    else:
        st.success(f"找到 {len(picks)} 個符合條件的標的")
        _wl_codes = {w["code"] for w in get_watchlist()}
        for p in picks:
            base_code = p["code"].replace(".TWO", "").replace(".TW", "")
            icon = "📊" if p["type"] == "ETF" else "🏢"
            with st.expander(f"{icon} **{p['name']}**（{base_code}）　{p['dividend']}"):
                st.markdown(f"**為什麼推薦？** {p['why']}")
                st.markdown(f"**適合誰？** {p['suitable_for']}")
                if p.get("warning"):
                    st.warning(f"⚠️ {p['warning']}")
                rb1, rb2 = st.columns(2)
                with rb1:
                    if base_code in _wl_codes:
                        st.info("✅ 已在觀察清單中")
                    elif st.button("👁️ 加入觀察清單", key=f"rec_wl_{p['code']}", use_container_width=True):
                        add_to_watchlist(base_code, p["name"], "來自新手推薦")
                        st.rerun()
                with rb2:
                    if st.button("🔍 查看評估", key=f"rec_ev_{p['code']}", use_container_width=True):
                        st.session_state.eval_ticker = base_code
                        st.success("請切換到「股票評估」頁面")


# ── Tab 7: 補知識 ─────────────────────────────────────────────
with tab7:
    st.header("台股補知識")
    st.caption("從零開始學台股，點開每個問題查看解答。")

    for chapter in CHAPTERS:
        st.subheader(f"{chapter['icon']} {chapter['title']}")
        for sec in chapter["sections"]:
            with st.expander(f"❓ {sec['q']}"):
                st.markdown(sec["a"])
        st.divider()
