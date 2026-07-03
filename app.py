import datetime
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from modules.data import get_stock_info, get_price_history, format_ticker
from modules.evaluator import evaluate, price_position
from modules.market import get_all_prices, get_current_prices, get_ohlc_batch, fmt_pct
from modules.portfolio import (
    get_holdings, add_holding, remove_holding, rename_account, update_holding,
    get_favorites, toggle_favorite,
    get_watchlist, add_to_watchlist, update_watchlist_item, remove_from_watchlist,
    get_accounts,
)

st.set_page_config(page_title="yAraY的台股溝", page_icon="📊", layout="wide")

st.markdown("""
<style>
/* ── 全域容器 ── */
.main .block-container {
    padding-top: 1.2rem;
    padding-bottom: 2rem;
    max-width: 1200px;
}

/* ── 標題漸層 ── */
.stApp h1 {
    background: linear-gradient(90deg, #a78bfa 0%, #ec4899 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    font-size: 2rem !important;
    font-weight: 800 !important;
    letter-spacing: -0.5px;
}

/* ── 子標題顏色 ── */
.stApp h2, .stApp h3 {
    color: #c4b5fd !important;
    font-weight: 600 !important;
}

/* ── Tab 列：藥丸形式 ── */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    background-color: #1a1a2e;
    padding: 5px;
    border-radius: 14px;
    border: 1px solid #2d2d44;
}
.stTabs [data-baseweb="tab"] {
    height: 38px;
    border-radius: 10px;
    padding: 0 18px;
    font-size: 0.84rem;
    font-weight: 500;
    color: #94a3b8;
    background: transparent;
    border: none;
    transition: all 0.2s ease;
}
.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, #7c3aed, #8b5cf6) !important;
    color: #ffffff !important;
    font-weight: 600 !important;
    box-shadow: 0 2px 12px rgba(139, 92, 246, 0.4);
}

/* ── Metric 卡片 ── */
[data-testid="metric-container"] {
    background: linear-gradient(135deg, #1e1e2e 0%, #16213e 100%);
    border: 1px solid #2d2d44;
    border-radius: 14px;
    padding: 1rem 1.25rem !important;
    box-shadow: 0 4px 20px rgba(139, 92, 246, 0.08);
    transition: box-shadow 0.2s ease;
}
[data-testid="metric-container"]:hover {
    box-shadow: 0 4px 24px rgba(139, 92, 246, 0.2);
}

/* ── Expander 卡片 ── */
details {
    border: 1px solid #2d2d44 !important;
    border-radius: 12px !important;
    background: #1a1a2e !important;
    margin-bottom: 6px !important;
    transition: border-color 0.2s ease;
}
details:hover {
    border-color: #6d28d9 !important;
}
details > summary {
    padding: 0.7rem 1rem !important;
    border-radius: 12px !important;
    font-weight: 500;
}
details[open] > summary {
    border-radius: 12px 12px 0 0 !important;
    border-bottom: 1px solid #2d2d44 !important;
    color: #c4b5fd;
}

/* ── 分隔線 ── */
hr {
    border-color: #2d2d44 !important;
    margin: 1rem 0 !important;
}

/* ── 按鈕 ── */
.stButton > button {
    border-radius: 8px !important;
    font-weight: 500 !important;
    transition: all 0.2s ease !important;
}
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #7c3aed, #8b5cf6) !important;
    border: none !important;
    box-shadow: 0 2px 10px rgba(139, 92, 246, 0.3) !important;
}
.stButton > button[kind="primary"]:hover {
    box-shadow: 0 4px 16px rgba(139, 92, 246, 0.5) !important;
    transform: translateY(-1px);
}

/* ── 警告橫幅 ── */
.stAlert {
    border-radius: 10px !important;
    border-left: 4px solid #8b5cf6 !important;
}

/* ── 下載按鈕 ── */
.stDownloadButton > button {
    border-radius: 8px !important;
    border: 1px solid #4c1d95 !important;
    background: transparent !important;
    color: #a78bfa !important;
}

/* ── 手機響應式 ── */
@media screen and (max-width: 768px) {
    /* 容器縮邊距，讓內容更寬 */
    .main .block-container {
        padding-left: 0.6rem !important;
        padding-right: 0.6rem !important;
        padding-top: 0.75rem !important;
    }

    /* 標題縮小 */
    .stApp h1 {
        font-size: 1.45rem !important;
        letter-spacing: -0.3px;
    }

    /* Tab 文字縮小，讓四個 tab 都放得下 */
    .stTabs [data-baseweb="tab"] {
        padding: 0 8px !important;
        font-size: 0.73rem !important;
        height: 36px !important;
    }

    /* 按鈕放大觸控區域（iOS 建議最少 44px） */
    .stButton > button {
        min-height: 44px !important;
        font-size: 0.88rem !important;
    }

    /* Metric 卡片在手機上縮小內距 */
    [data-testid="metric-container"] {
        padding: 0.7rem 0.85rem !important;
    }

    /* Expander 標題字加大易點選 */
    details > summary {
        font-size: 0.88rem !important;
        line-height: 1.5 !important;
        padding: 0.85rem 0.9rem !important;
    }

    /* 表單 input 放大，避免 iOS 自動縮放 */
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
        increasing_line_color="#ef4444",   # 台灣：紅=漲
        decreasing_line_color="#22c55e",   # 台灣：綠=跌
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

tab1, tab2, tab3, tab4 = st.tabs(["📊 持倉管理", "➕ 新增持倉", "👁️ 觀察清單", "🔍 股票評估"])


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

        # 排序
        if sort_mode == "損益高→低":
            enriched = sorted(enriched,
                key=lambda e: e["pnl"] if e["pnl"] is not None else float("-inf"), reverse=True)
        elif sort_mode == "帳號分組":
            enriched = sorted(enriched, key=lambda e: e.get("account", ""))
        elif sort_mode == "最愛優先":
            enriched = sorted(enriched,
                key=lambda e: (0 if e["code"] in favorites else 1, e.get("account", "")))

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
        c4.metric("持有檔數", f"{len({e['code'] for e in enriched})} 支")

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

        # ── 持倉明細 ──
        st.subheader("持倉明細")

        # 速覽表：一眼掃完所有持股
        _tbl_rows = []
        for e in enriched:
            _arrow = "▲" if e["pnl"] and e["pnl"] > 0 else ("▼" if e["pnl"] and e["pnl"] < 0 else "")
            _row = {"股票": f"{e['name']}（{e['code']}）"}
            if len(accounts) > 1:
                _row["帳號"] = e.get("account", "預設帳號")
            _row["現價"]  = f"NT$ {e['current']:,.1f}" if e["current"] else "—"
            _row["損益"]  = f"{_arrow} {e['pnl']:+,.0f}" if e["pnl"] is not None else "—"
            _row["損益%"] = f"{_arrow} {e['pnl_pct']:+.2f}%" if e["pnl_pct"] is not None else "—"
            _tbl_rows.append(_row)
        st.dataframe(pd.DataFrame(_tbl_rows), use_container_width=True, hide_index=True)
        st.divider()

        for e in enriched:
            real_idx = e["real_idx"]
            pnl      = e["pnl"]
            pnl_pct  = e["pnl_pct"]
            is_fav   = e["code"] in favorites
            fav_char = "★" if is_fav else "☆"
            icon     = "🟢" if pnl and pnl > 0 else ("🔴" if pnl and pnl < 0 else "⚪")
            pnl_str  = f"　{pnl:+,.0f} 元（{pnl_pct:+.2f}%）" if pnl is not None else ""
            acct_tag = f"［{e.get('account', '預設帳號')}］　" if selected_account == "全部帳號" else ""
            title    = f"{fav_char} {icon} {acct_tag}{e['name']}（{e['code']}）　{e['shares']:.4g} 股{pnl_str}"

            with st.expander(title):
                # ── 功能列（3 + 2 兩排，手機友善）──
                ba, bb, bc = st.columns(3)
                with ba:
                    fav_label = "★ 已收藏" if is_fav else "☆ 最愛"
                    if st.button(fav_label, key=f"fav_{real_idx}", use_container_width=True):
                        toggle_favorite(e["code"])
                        st.rerun()
                with bb:
                    is_editing = st.session_state.editing_idx == real_idx
                    edit_label = "✏️ 收起" if is_editing else "✏️ 編輯"
                    if st.button(edit_label, key=f"edit_btn_{real_idx}", use_container_width=True):
                        st.session_state.editing_idx = None if is_editing else real_idx
                        st.rerun()
                with bc:
                    eval_key    = f"show_eval_{real_idx}"
                    eval_active = st.session_state.get(eval_key, False)
                    eval_label  = "📊 收起" if eval_active else "📊 基本面"
                    if st.button(eval_label, key=f"eval_btn_{real_idx}", use_container_width=True):
                        st.session_state[eval_key] = not eval_active
                        st.rerun()

                bd, be, _ = st.columns(3)
                with bd:
                    clean = e["code"].replace(".TW", "")
                    if st.button("🔍 評估頁", key=f"pe_{real_idx}", use_container_width=True):
                        st.session_state.eval_ticker = clean
                        st.success("請切換到「股票評估」頁面")
                with be:
                    if st.button("🗑️ 刪除", key=f"del_{real_idx}", use_container_width=True):
                        remove_holding(real_idx)
                        if st.session_state.editing_idx == real_idx:
                            st.session_state.editing_idx = None
                        st.rerun()

                # ── 編輯模式 ──
                if st.session_state.editing_idx == real_idx:
                    st.divider()
                    current_acct = e.get("account", "預設帳號")
                    acct_idx = accounts.index(current_acct) if current_acct in accounts else 0
                    try:
                        default_date = datetime.date.fromisoformat(e.get("date", ""))
                    except (ValueError, TypeError):
                        default_date = datetime.date.today()

                    with st.form(f"edit_form_{real_idx}"):
                        ef1, ef2, ef3, ef4 = st.columns(4)
                        with ef1:
                            e_acct   = st.selectbox("帳號", accounts, index=acct_idx)
                        with ef2:
                            e_shares = st.number_input("股數", min_value=0.01,
                                                        value=float(e["shares"]), step=1.0)
                        with ef3:
                            e_cost   = st.number_input("平均成本", min_value=0.01,
                                                        value=float(e["avg_cost"]),
                                                        step=0.01, format="%.2f")
                        with ef4:
                            e_date   = st.date_input("買入日期", value=default_date)
                        sv_col, cl_col = st.columns(2)
                        with sv_col:
                            save_clicked   = st.form_submit_button("💾 儲存",
                                                type="primary", use_container_width=True)
                        with cl_col:
                            cancel_clicked = st.form_submit_button("✖ 取消",
                                                use_container_width=True)

                    if save_clicked:
                        update_holding(real_idx, shares=e_shares,
                                       avg_cost=e_cost, account=e_acct, date=str(e_date))
                        st.session_state.editing_idx = None
                        st.rerun()
                    if cancel_clicked:
                        st.session_state.editing_idx = None
                        st.rerun()

                else:
                    # ── 一般資訊 ──
                    ca, cb = st.columns([3, 2])
                    with ca:
                        st.markdown(f"**帳號：** {e.get('account', '預設帳號')}")
                        st.markdown(f"**平均成本：** NT$ {e['avg_cost']:,.2f}")
                        price_str = f"NT$ {e['current']:,.2f}" if e["current"] else "無法取得"
                        st.markdown(f"**現價：** {price_str}")
                        st.markdown(f"**持股成本：** NT$ {e['cost_basis']:,.0f}")
                        if e["current_value"]:
                            st.markdown(f"**目前市值：** NT$ {e['current_value']:,.0f}")
                        if e["date"]:
                            st.markdown(f"**買入日期：** {e['date']}")
                        if e["note"]:
                            st.markdown(f"**備註：** {e['note']}")
                    with cb:
                        if pnl is not None:
                            st.metric("未實現損益", f"NT$ {pnl:+,.0f}", delta=f"{pnl_pct:+.2f}%")

                # ── K 線圖（自動顯示，資料已批次快取）──
                if e["ticker"] in ohlc_map:
                    st.caption("近一個月走勢（K 線）")
                    st.plotly_chart(
                        _make_candlestick(ohlc_map[e["ticker"]]),
                        use_container_width=True, key=f"kline_{real_idx}",
                    )

                # ── 內嵌基本面（按鈕展開）──
                if st.session_state.get(f"show_eval_{real_idx}", False):
                    st.divider()
                    with st.spinner("載入基本面資料..."):
                        try:
                            info = get_stock_info(e["ticker"])
                        except Exception:
                            info = None
                    if info:
                        pos = price_position(info)
                        if pos:
                            progress = int(pos["position_pct"])
                            p1, p2, p3 = st.columns(3)
                            p1.metric("52 週高", f"NT$ {pos['high']:,.1f}")
                            p2.metric("目前位置", f"{progress}%")
                            p3.metric("52 週低", f"NT$ {pos['low']:,.1f}")
                            st.progress(min(max(progress / 100, 0.0), 1.0))
                            st.caption(pos["label"])
                        is_etf = info.get("quote_type") == "ETF"
                        if is_etf:
                            st.info("📌 ETF：本益比、淨利率等指標不適用")
                        for m in evaluate(info)[:4]:
                            st.caption(f"**{m['label']}**　{m['explanation']}")
                    else:
                        st.warning("無法載入基本面資料")

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


# ── Tab 2: 新增持倉 ───────────────────────────────────────────
with tab2:
    st.header("新增持倉")

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
        new_note  = st.text_input("備註（選填）", placeholder="例：定期定額、逢低加碼")
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
                        new_shares, new_cost, str(new_date), new_note, account_name)
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


# ── Tab 3: 觀察清單 ───────────────────────────────────────────
with tab3:
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


# ── Tab 4: 股票評估 ───────────────────────────────────────────
with tab4:
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
                    line=dict(color="#1f77b4", width=2),
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
