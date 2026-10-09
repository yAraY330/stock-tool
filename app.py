import datetime
import re
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from modules.data import get_stock_info, get_price_history, format_ticker
from modules.evaluator import evaluate, price_position
from modules.market import (
    get_all_prices, get_current_prices, get_ohlc_batch, fmt_pct, get_snapshot_data,
)
from modules.snapshot import build_snapshot, decide_write
from modules.knowledge import CHAPTERS
from modules.portfolio import (
    get_holdings, add_holding, remove_holding, rename_account, update_holding,
    get_favorites, toggle_favorite,
    get_watchlist, add_to_watchlist, update_watchlist_item, remove_from_watchlist,
    get_accounts,
    get_quick_view_extras, add_quick_view_extra, remove_quick_view_extra,
    get_sold, sell_holding,
    add_dividend, remove_dividend,
    get_snapshot, save_snapshot,
    get_kb_read, mark_kb_read,
)
from modules import ui
from modules.ui import C   # 色票（單一真相來源在 modules/ui.py）

st.set_page_config(page_title="yAraY的台股溝", page_icon="📈", layout="wide")
st.markdown(ui.global_css(), unsafe_allow_html=True)


# 登入頁跑馬燈：只放公開的大盤與熱門權值股（登入前誰都看得到，不能露出個人持股）
_LOGIN_TICKERS = {
    "^TWII": "加權", "2330.TW": "2330 台積電", "0050.TW": "0050 台灣50", "2317.TW": "2317 鴻海",
    "2454.TW": "2454 聯發科", "0056.TW": "0056 高股息", "2881.TW": "2881 富邦金", "2308.TW": "2308 台達電",
}
_TZ8 = datetime.timezone(datetime.timedelta(hours=8))


def _login_quotes() -> list:
    """[(名稱, 價格字串, 今日漲跌%)]；抓不到（例如被限速）就回傳空清單，登入頁改成不畫跑馬燈。"""
    try:
        prices = get_current_prices(tuple(_LOGIN_TICKERS))
    except Exception:
        return []
    out = []
    for t, name in _LOGIN_TICKERS.items():
        p = prices.get(t, {}).get("price")
        if p:
            out.append((name, f"{p:,.0f}" if p >= 1000 else f"{p:,.1f}", prices[t].get("today_pct")))
    return out


def _date_label() -> str:
    now = datetime.datetime.now(_TZ8)
    return f"{now:%m.%d} {now:%a}".upper()


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
    # 登入頁：上下各兩排號子跑馬燈，中間「台股溝」，下面是密碼欄
    errs = st.session_state.get("login_err", 0)
    quotes = _login_quotes()
    st.markdown(ui.login_css(errs) + ui.ticker_block(quotes, "top") + ui.ticker_block(quotes, "bottom")
                + '<div style="height:max(150px, 22vh)"></div>', unsafe_allow_html=True)
    with st.container(key="login_box"):
        st.markdown(ui.login_brand(_date_label()), unsafe_allow_html=True)
        with st.form("login_form", border=False, clear_on_submit=True):   # 用 form：按 Enter 就能登入
            pwd = st.text_input("密碼", type="password", placeholder="輸入後按 Enter")
            ok = st.form_submit_button("進入", type="primary", use_container_width=True)
        if errs:
            msg = f"密碼不對。已經第 {errs} 次了，確認一下大小寫？" if errs >= 3 else "密碼不對，再試一次。"
            st.markdown(f'<div style="margin-top:4px;font-size:13px;color:{C["up"]}">{msg}</div>',
                        unsafe_allow_html=True)
    if ok:
        if pwd == correct:
            st.session_state.authenticated = True
            st.session_state.pop("login_err", None)
            st.session_state.play_entry = True    # 下一輪播一次進場動畫
        else:
            st.session_state.login_err = errs + 1   # 重跑後表單會晃一下並顯示錯誤
        st.rerun()
    return False

if not _check_password():
    st.stop()

# 進場動畫「離站」：只在剛登入那一輪播一次，放在頁面內容之前，動畫期間資料照常載入
if st.session_state.pop("play_entry", False):
    st.markdown(ui.entry_overlay(_login_quotes(), _date_label()), unsafe_allow_html=True)

PAGES = ["持倉", "速覽", "新增", "觀察", "評估", "知識"]
for _k, _v in [("eval_ticker", ""), ("csv_imported", False), ("editing_idx", None)]:
    if _k not in st.session_state:
        st.session_state[_k] = _v
if st.session_state.get("sidebar_nav") not in PAGES:     # 舊版 emoji 選項或第一次開
    st.session_state.sidebar_nav = PAGES[0]
# 跨頁跳轉：導覽列畫出來之後就不能改它的值，所以先記在 _nav_to，下一輪在這裡（導覽列建立前）才切換
if st.session_state.get("_nav_to") in PAGES:
    st.session_state.sidebar_nav = st.session_state.pop("_nav_to")


# ── 共用 helper ────────────────────────────────────────────────
def _dark_fig(fig: go.Figure, height: int) -> go.Figure:
    fig.update_layout(
        height=height, showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=C["text_sub"], family="Noto Sans TC, sans-serif", size=11),
        margin=dict(l=0, r=0, t=10, b=0),
    )
    fig.update_xaxes(gridcolor="#1A1918", zeroline=False, showline=False)
    fig.update_yaxes(gridcolor="#1A1918", zeroline=False, showline=False)
    return fig


def _make_candlestick(df: pd.DataFrame, height: int = 200) -> go.Figure:
    fig = go.Figure(go.Candlestick(
        x=df.index,
        open=df["Open"], high=df["High"],
        low=df["Low"],  close=df["Close"],
        increasing_line_color=C["up"],   increasing_fillcolor=C["up"],    # 台灣：紅=漲
        decreasing_line_color=C["down"], decreasing_fillcolor=C["down"],  # 台灣：綠=跌
    ))
    _dark_fig(fig, height)
    fig.update_layout(xaxis_rangeslider_visible=False)
    # 把 x 軸鎖到實際資料範圍，去掉台股 13:30 收盤後的空白留白
    if len(df.index) > 0:
        fig.update_xaxes(range=[df.index.min(), df.index.max()])
    return fig


def _safe_key(code: str) -> str:
    return re.sub(r"[^0-9A-Za-z]", "_", code)


def _html(s: str) -> None:
    st.markdown(s, unsafe_allow_html=True)


def _day_contrib(groups: dict, prices_map: dict) -> dict:
    """每檔今天貢獻多少損益（以股計算）。抓不到今日漲跌的不列入。"""
    out = {}
    for code, gs in groups.items():
        pct = prices_map.get(gs["ticker"], {}).get("today_pct")
        if pct is not None and gs["cur_price"]:
            prev = gs["cur_price"] / (1 + pct / 100)
            out[code] = (gs["cur_price"] - prev) * gs["tot_shares"]
    return out


def _focus_line(contrib: dict, names: dict) -> str:
    if not contrib:
        return ""
    best = max(contrib, key=contrib.get)
    worst = min(contrib, key=contrib.get)
    parts = []
    if contrib[best] > 0:
        parts.append(f'<span>最大貢獻　<span style="color:{C["text"]}">{names[best]}</span> '
                     f'<span class="n" style="color:{C["up"]}">{ui.signed(contrib[best])}</span></span>')
    if contrib[worst] < 0:
        parts.append(f'<span>最大拖累　<span style="color:{C["text"]}">{names[worst]}</span> '
                     f'<span class="n" style="color:{C["down"]}">{ui.signed(contrib[worst])}</span></span>')
    if not parts:
        return ""
    return ('<div style="margin-top:14px;display:flex;flex-wrap:wrap;gap:4px 16px;font-size:13px;'
            f'color:{C["text_sub"]}">' + "".join(parts) + "</div>")


def _page_head(title: str, right: str = "") -> None:
    _html(f'<div style="display:flex;justify-content:space-between;align-items:baseline;margin:8px 0 18px">'
          f'<h1 style="margin:0">{title}</h1><span style="font-size:13px;color:{C["text_sub"]}">{right}</span></div>')


# ── 頂部提醒：買入點、停利、停損（每次開 app 自動檢查）──────────────
_ALERTS: list = []
_wl_targets = [w for w in get_watchlist() if float(w.get("target_price", 0)) > 0]
if _wl_targets:
    _alert_tickers = tuple(sorted({format_ticker(w["code"]) for w in _wl_targets}))
    try:
        _alert_prices = get_current_prices(_alert_tickers)
        for _w in _wl_targets:
            _cur = _alert_prices.get(format_ticker(_w["code"]), {}).get("price")
            _tgt = float(_w["target_price"])
            if _cur and _cur <= _tgt:
                _ALERTS.append(("buy", f"{_w['name']}（{_w['code']}）到了目標買入價",
                                f"現價 NT$ {_cur:,.1f}，你設的目標是 NT$ {_tgt:,.1f}。"))
    except Exception:
        pass

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
                _ALERTS.append(("profit", f"{_h['name']}（{_h['code']}）到了停利點",
                                f"現價 NT$ {_cur:,.1f}，你設的停利是 NT$ {_h['stop_profit']:,.1f}。"))
            if _h.get("stop_loss") and _cur <= _h["stop_loss"]:
                _why = "當初的買進理由還成立嗎？" if _h.get("buy_reason") else ""
                _ALERTS.append(("loss", f"{_h['name']}（{_h['code']}）跌破停損",
                                f"現價 NT$ {_cur:,.1f}，你設的停損是 NT$ {_h['stop_loss']:,.1f}。{_why}"))
    except Exception:
        pass

# ── 底部導覽（CSS 固定在畫面底部，見 modules/ui.py）──────────────
page = st.radio(
    "navigation", PAGES, horizontal=True,
    label_visibility="collapsed", key="sidebar_nav",
)


# ── 每日快照（供台股晨報日報讀取）────────────────────────────
_TZ8 = datetime.timezone(datetime.timedelta(hours=8))
_SNAP_MAX_AGE_MIN = 30


def _snapshot_fresh(snap: dict | None) -> bool:
    """既有快照是否仍新鮮（updated_at 未滿 30 分鐘）。"""
    if not snap or not snap.get("updated_at"):
        return False
    try:
        ts = datetime.datetime.fromisoformat(snap["updated_at"])
    except (ValueError, TypeError):
        return False
    now = datetime.datetime.now(ts.tzinfo or _TZ8)
    return (now - ts).total_seconds() < _SNAP_MAX_AGE_MIN * 60


def _maybe_write_snapshot(holdings: list, *, force: bool = False) -> str | None:
    """組並寫入每日快照。回傳訊息（供手動按鈕顯示）或 None（靜默跳過）。
    節流：同 session 最多一次、既有快照未滿 30 分鐘就跳過（force 可略過）。
    失敗或全抓不到行情時：保留舊快照、不寫入、不破壞任何資料。"""
    if not holdings:
        return None
    if not force:
        if st.session_state.get("_snap_written"):
            return None
        if _snapshot_fresh(get_snapshot()):
            st.session_state["_snap_written"] = True
            return None
    try:
        # 報價範圍＝holdings ∪ watchlist（positions 仍只算 holdings）
        codes = {h["code"] for h in holdings} | {w["code"] for w in get_watchlist()}
        tickers = tuple(sorted({format_ticker(c) for c in codes}))
        snap_data = get_snapshot_data(tickers)          # 慢、在寫入鎖外
        quotes = snap_data.get("quotes", {})
        if not quotes:                                   # 全抓不到 → 保留舊快照
            st.session_state["_snap_written"] = True     # 本 session 不再重試洗版
            return "暫時抓不到行情，保留既有快照未更新" if force else None
        now = datetime.datetime.now(_TZ8)
        new_payload = build_snapshot(holdings, quotes,
                                     snap_data.get("market_date"), now,
                                     snap_data.get("stale_codes", []),
                                     snap_data.get("suspect_codes", []))
        payload = decide_write(new_payload, get_snapshot(), now)  # 覆寫守門
        save_snapshot(payload)                           # 只覆寫 snapshot 鍵
        st.session_state["_snap_written"] = True
        if payload.get("skip_reason"):
            return (f"未覆寫（{payload['skip_reason']}），"
                    f"保留既有快照、僅更新 last_attempt_at") if force else None
        return f"快照已更新（{payload['updated_at'][:16]}，狀態 {payload['status']}）"
    except Exception as _err:
        return f"快照更新失敗，既有資料未受影響：{_err}" if force else None


# ── 跨頁跳轉（觀察／評估 共用）─────────────────────────────────
def _go_eval(code: str) -> None:
    st.session_state.eval_ticker = code
    st.session_state._nav_to = "評估"
    st.rerun()


def _go_add(code: str) -> None:
    st.session_state.add_code = code       # 新增頁的代碼欄 key，跳過去就預填好
    st.session_state._nav_to = "新增"
    st.rerun()


# ── 持倉管理 ─────────────────────────────────────────────────
if page == "持倉":
    holdings  = get_holdings()
    favorites = get_favorites()

    if holdings:
        accounts = get_accounts(holdings)
        hero_slot  = st.container()      # 首屏數字要等算完才填，先佔位
        alert_slot = st.container()

        # 控制列：帳號選擇 + 排序
        ctrl1, ctrl2 = st.columns([2, 3])
        with ctrl1:
            if len(accounts) > 1:
                selected_account = st.radio("帳號", ["全部帳號"] + accounts, horizontal=True)
            else:
                selected_account = "全部帳號"
        with ctrl2:
            sort_mode = st.radio(
                "排序",
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
        try:   # 今日走勢線；與速覽「當日」同參數，共用快取
            intra_map = get_ohlc_batch(unique_tickers, period="1d", interval="15m")
        except Exception:
            intra_map = {}

        # 自動寫入每日快照（受節流保護：同 session 一次、未滿 30 分鐘跳過）
        _maybe_write_snapshot(holdings)

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
            _tdv0    = sum(_e0.get("dividends", 0) for _e0 in _lots0)   # 該股累計配息
            _tret0   = (_tpg0 + _tdv0) if _tpg0 is not None else None   # 含息報酬
            _trp0    = (_tret0 / _tc0 * 100) if (_tret0 is not None and _tc0) else None
            _gsumm[_c0] = {
                "name": _lots0[0]["name"], "ticker": _lots0[0]["ticker"],
                "tot_shares": _ts0, "tot_cost": _tc0, "w_avg": _wa0,
                "cur_price": _cur0, "tot_val": _tv0, "tot_pnl": _tpg0, "g_pct": _gp0,
                "tot_div": _tdv0, "tot_return": _tret0, "tot_return_pct": _trp0,
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
        total_cost   = sum(e["cost_basis"] for e in enriched)
        priced       = [e for e in enriched if e["current_value"] is not None]
        _priced_cost = sum(e["cost_basis"] for e in priced) if priced else 0
        total_value  = sum(e["current_value"] for e in priced) if priced else None
        total_pnl    = (total_value - _priced_cost) if total_value is not None else None
        total_pct    = (total_pnl / _priced_cost * 100) if (total_pnl is not None and _priced_cost) else None
        # 含息報酬：只在有現價的持股上計算，讓分子分母一致
        total_div    = sum(e.get("dividends", 0) for e in priced)
        total_return = (total_pnl + total_div) if total_pnl is not None else None
        total_ret_pct = (total_return / _priced_cost * 100) if (total_return is not None and _priced_cost) else None
        _has_div     = total_div > 0

        # ── 今日損益（以股計算，避免多筆重複）──
        _contrib = _day_contrib({c: _gsumm[c] for c in _seen_codes}, prices_map)
        today_pnl_total = sum(_contrib.values())
        _prev_total = (total_value or 0) - today_pnl_total
        today_pct = today_pnl_total / _prev_total * 100 if _prev_total else None

        # 今日走勢：各檔 15 分 K × 股數 加總，減去昨收市值
        _intra_html = ""
        try:
            _series, _base = [], 0.0
            for _c0 in _seen_codes:
                _gs0 = _gsumm[_c0]
                _df0 = intra_map.get(_gs0["ticker"])
                if _c0 not in _contrib or _df0 is None or _df0.empty:
                    continue
                _series.append(_df0["Close"] * _gs0["tot_shares"])
                _base += _gs0["tot_val"] - _contrib[_c0]
            if _series:
                _tot = pd.concat(_series, axis=1).ffill().dropna().sum(axis=1)
                if len(_tot) >= 2:
                    _intra_html = ui.intraday_chart(
                        [float(v) - _base for v in _tot],
                        _tot.index[0].strftime("%H:%M"), _tot.index[-1].strftime("%H:%M"))
        except Exception:
            _intra_html = ""

        label_prefix = "" if selected_account == "全部帳號" else f"{selected_account}　"
        _stats = [
            ("總市值", f"{total_value:,.0f}" if total_value is not None else "—", C["text"], None, None),
            ("投入成本", f"{total_cost:,.0f}", C["text"], None, None),
            ("未實現損益（價差）", ui.signed(total_pnl), ui.tone(total_pnl),
             f"{total_pct:+.2f}%" if total_pct is not None else None, ui.tone(total_pnl)),
        ]
        if _has_div:
            _stats.append(("含息報酬", ui.signed(total_return), ui.tone(total_return),
                           (f"{total_ret_pct:+.2f}%　已收配息 {total_div:,.0f}" if total_ret_pct is not None else None),
                           C["text_sub"]))
        else:
            _stats.append(("持有檔數", f"{len(_seen_codes)} 檔", C["text"], None, None))

        _today_line = (f'<div class="n" style="margin-top:10px;font-size:15px;color:{ui.tone(today_pnl_total)}">'
                       f'{today_pct:+.2f}%<span style="color:{C["text_sub"]}">　持股 {len(_seen_codes)} 檔</span></div>'
                       if today_pct is not None else "")
        with hero_slot:
            _html(
                f'<div style="display:flex;justify-content:space-between;font-size:13px;color:{C["text_sub"]};margin-top:8px">'
                f'<span>yAraY 的台股溝</span><span>{label_prefix}{datetime.datetime.now(_TZ8).month} 月 {datetime.datetime.now(_TZ8).day} 日</span></div>'
                f'<div style="margin-top:28px;font-size:14px;color:{C["text_sub"]}">今天</div>'
                + ui.odometer(today_pnl_total) + _today_line + _intra_html
                + _focus_line(_contrib, {c: _gsumm[c]["name"] for c in _seen_codes})
                + ui.stat_grid(_stats)
            )
            if _has_div:
                st.caption("除息當天股價會被扣掉，含息報酬才是你的真實處境。")

        # ── 提醒（全域提醒＋集中度）──
        _conc = []
        if total_value:
            for _c0 in _seen_codes:
                _gs0 = _gsumm[_c0]
                if _gs0["tot_val"] and _gs0["tot_val"] / total_value > 0.4:
                    _conc.append(("concentration", f"{_gs0['name']} 佔了 {_gs0['tot_val'] / total_value * 100:.1f}%",
                                  "超過總市值 40%，風險集中。加碼前可以先到「新增」預覽加入後的比例。"))
        with alert_slot:
            _html(ui.alerts(_ALERTS + _conc))

        # ── 持倉明細（群組顯示）──
        _html(f'<div style="display:grid;grid-template-columns:minmax(0,1fr) 64px 104px;column-gap:12px;'
              f'margin-top:22px;padding-bottom:6px;font-size:12px;color:{C["faint"]};border-bottom:1px solid {C["line"]}">'
              f'<span>持倉　點一檔看明細</span><span style="text-align:center">5 日</span>'
              f'<span style="text-align:right">市值／損益</span></div>')

        for _ri, _code in enumerate(_seen_codes):
            _lots   = _grp[_code]
            _gs     = _gsumm[_code]
            _is_fav = _code in favorites

            _detail_key = f"h_detail_{_code}"
            _is_open    = st.session_state.get(_detail_key, False)
            _val_str    = f"{_gs['tot_val']:,.0f}" if _gs["tot_val"] else "—"
            _pnl_disp   = (f"{ui.signed(_gs['tot_pnl'])}　{_gs['g_pct']:+.1f}%"
                           if _gs["tot_pnl"] is not None and _gs["g_pct"] is not None else "—")
            _sub_parts  = [f"{_code}　{_gs['tot_shares']:,.4g} 股"]
            if len(_lots) > 1:
                _sub_parts.append(f"{len(_lots)} 筆")
            if selected_account == "全部帳號":
                _sub_parts.append("/".join(sorted({_e.get("account", "預設帳號") for _e in _lots})))
            _closes = (ohlc_map[_gs["ticker"]]["Close"].dropna().tail(5).tolist()
                       if _gs["ticker"] in ohlc_map else [])

            with st.container(key=f"hrow_{_safe_key(_code)}"):
                _html(ui.holding_row(_gs["name"], "　".join(_sub_parts), ui.spark(_closes, _ri),
                                     _val_str, _pnl_disp, ui.tone(_gs["tot_pnl"]), _is_fav))
                if st.button(f"{'收起' if _is_open else '展開'} {_gs['name']}",
                             key=f"hrowbtn_{_safe_key(_code)}"):
                    st.session_state[_detail_key] = not _is_open
                    st.rerun()
            _html(f'<div style="border-top:1px solid {C["line"]}"></div>')


            if _is_open:
                # ── 群組操作列：收藏、評估頁、基本面 ──
                _gba = _gbb = _gbc = st.container(horizontal=True)
                with _gba:
                    _fl = "取消收藏" if _is_fav else "收藏"
                    if st.button(_fl, key=f"fav_grp_{_code}", use_container_width=True):
                        toggle_favorite(_code)
                        st.rerun()
                with _gbb:
                    if st.button("評估頁", key=f"pe_grp_{_code}", use_container_width=True):
                        st.session_state.eval_ticker = _code.replace(".TW", "")
                        st.session_state._nav_to = "評估"
                        st.rerun()
                with _gbc:
                    _eval_key    = f"show_eval_grp_{_code}"
                    _eval_active = st.session_state.get(_eval_key, False)
                    _eval_label  = "收起基本面" if _eval_active else "基本面"
                    if st.button(_eval_label, key=f"eval_btn_grp_{_code}", use_container_width=True):
                        st.session_state[_eval_key] = not _eval_active
                        st.rerun()

                # ── 群組損益概覽 ──
                if _gs["tot_pnl"] is not None:
                    _gc1, _gc2 = st.columns(2)
                    _gc1.metric("合計未實現損益（價差）",
                                f"NT$ {_gs['tot_pnl']:+,.0f}", delta=f"{_gs['g_pct']:+.2f}%",
                                delta_color="inverse")   # 台股：紅漲綠跌
                    _tdp2 = prices_map.get(_gs["ticker"], {}).get("today_pct")
                    if _tdp2 is not None and _gs["cur_price"]:
                        _day2 = _tdp2 / 100 * _gs["cur_price"] * _gs["tot_shares"]
                        _gc2.metric("今日損益（合計）",
                                    f"NT$ {_day2:+,.0f}", delta=f"{_tdp2:+.2f}%",
                                    delta_color="inverse")
                # 含息報酬（有配息才顯示）
                if _gs.get("tot_div", 0) > 0 and _gs.get("tot_return") is not None:
                    _rp = (f"（{_gs['tot_return_pct']:+.2f}%）"
                           if _gs.get("tot_return_pct") is not None else "")
                    st.caption(
                        f"含息報酬 **NT$ {_gs['tot_return']:+,.0f}**{_rp}"
                        f"　·　已收配息 NT$ {_gs['tot_div']:,.0f}"
                    )

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
                            st.info("ETF：本益比、淨利率等指標不適用")
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
                            _tr_m = (_pnl + _e["dividends"]) if _pnl is not None else _e["dividends"]
                            _extras.append(
                                f"已收股利 NT${_e['dividends']:,.0f}"
                                f"（含息 {_tr_m:+,.0f}）"
                            )
                        if _extras:
                            st.caption("　　" + "　｜　".join(_extras))
                        if _pnl_pct is not None and _pnl_pct < -8 and _e.get("buy_reason"):
                            st.warning(
                                f"**第 {_li+1} 筆已下跌 {_pnl_pct:.1f}%，買進理由：**\n\n"
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
                                _tr = (_pnl + _e["dividends"]) if _pnl is not None else _e["dividends"]
                                st.markdown(
                                    f"**已收股利：** NT$ {_e['dividends']:,.0f}"
                                    f"　（含股利損益 NT$ {_tr:+,.0f}）"
                                )
                        with _cb:
                            if _pnl is not None:
                                st.metric("未實現損益", f"NT$ {_pnl:+,.0f}", delta=f"{_pnl_pct:+.2f}%", delta_color="inverse")
                            _tp_s = prices_map.get(_e["ticker"], {}).get("today_pct")
                            if _tp_s is not None and _e["current"]:
                                _day_s = _tp_s / 100 * _e["current"] * _e["shares"]
                                st.metric("今日損益", f"NT$ {_day_s:+,.0f}", delta=f"{_tp_s:+.2f}%", delta_color="inverse")
                        if _pnl_pct is not None and _pnl_pct < -8 and _e.get("buy_reason"):
                            st.warning(
                                f"**這支股票已下跌 {_pnl_pct:.1f}%，當初買進理由是：**\n\n"
                                f"> {_e['buy_reason']}\n\n**這個理由現在還成立嗎？**"
                            )

                    # ── 操作按鈕（每筆都有）──
                    _ba = _bb = _bc = _bd = st.container(horizontal=True)
                    with _ba:
                        _is_editing = st.session_state.editing_idx == _real_idx
                        _el = "收起編輯" if _is_editing else "編輯"
                        if st.button(_el, key=f"edit_btn_{_real_idx}", use_container_width=True):
                            st.session_state.editing_idx = None if _is_editing else _real_idx
                            st.rerun()
                    with _bb:
                        _dk = f"show_div_{_real_idx}"
                        if _dk not in st.session_state:
                            st.session_state[_dk] = False
                        _dl2 = "收起配息" if st.session_state[_dk] else "配息"
                        if st.button(_dl2, key=f"div_btn_{_real_idx}", use_container_width=True):
                            st.session_state[_dk] = not st.session_state[_dk]
                            st.rerun()
                    with _bc:
                        _sk = f"show_sell_{_real_idx}"
                        if _sk not in st.session_state:
                            st.session_state[_sk] = False
                        _sl2 = "收起賣出" if st.session_state[_sk] else "賣出"
                        if st.button(_sl2, key=f"sell_btn_{_real_idx}", use_container_width=True):
                            st.session_state[_sk] = not st.session_state[_sk]
                            st.rerun()
                    with _bd:
                        if st.button("刪除", key=f"del_{_real_idx}", use_container_width=True):
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
                                f"已記錄賣出 {_s_shares:.4g} 股，"
                                f"損益 NT$ {(_s_price - _e['avg_cost']) * _s_shares:+,.0f}"
                            )
                            st.rerun()

                    # ── 配息登錄表單 ──
                    if st.session_state.get(f"show_div_{_real_idx}", False):
                        st.divider()
                        st.caption("配息明細（手動登錄，不自動抓取）")
                        _dlog = _e.get("dividend_log", [])
                        if _dlog:
                            for _di, _d in enumerate(_dlog):
                                _dca, _dcb = st.columns([9, 1])
                                _ps_s = f"　每股 NT${_d['per_share']:g}" if _d.get("per_share") else ""
                                _nt_s = f"　·　{_d['note']}" if _d.get("note") else ""
                                _dca.caption(
                                    f"・{_d.get('date', '—')}　NT$ {_d.get('amount', 0):,.0f}{_ps_s}{_nt_s}"
                                )
                                if _dcb.button("刪除", key=f"deldiv_{_real_idx}_{_di}",
                                               use_container_width=True):
                                    remove_dividend(_real_idx, _di)
                                    st.rerun()
                            st.caption(f"**累計已收配息：NT$ {sum(x.get('amount', 0) for x in _dlog):,.0f}**")
                        elif _e.get("dividends"):
                            st.caption(
                                f"目前累計 NT$ {_e['dividends']:,.0f}（早期以總額登錄）。"
                                "下方新增後會改用逐筆明細管理。"
                            )
                        with st.form(f"div_form_{_real_idx}"):
                            _df1, _df2, _df3 = st.columns(3)
                            with _df1:
                                _d_date = st.date_input("除息／入帳日", value=datetime.date.today(),
                                                        key=f"ddate_{_real_idx}")
                            with _df2:
                                _d_per = st.number_input("每股配息（元，選填）", min_value=0.0,
                                                         value=0.0, step=0.1, format="%.4f",
                                                         key=f"dper_{_real_idx}")
                            with _df3:
                                _d_amt = st.number_input("配息金額（元）", min_value=0.0,
                                                         value=0.0, step=100.0, format="%.0f",
                                                         key=f"damt_{_real_idx}")
                            _d_note = st.text_input("備註（選填）", key=f"dnote_{_real_idx}",
                                                    placeholder="例：2026 Q2 季配")
                            st.caption("留空金額、只填每股配息時，系統會用「每股 × 本筆股數」自動換算。")
                            _div_ok = st.form_submit_button("登錄配息", type="primary",
                                                            use_container_width=True)
                        if _div_ok:
                            _amt = _d_amt
                            _per = _d_per if _d_per > 0 else None
                            if _amt <= 0 and _per:
                                _amt = round(_per * _e["shares"], 2)
                            if _amt <= 0:
                                st.error("請輸入配息金額，或填每股配息讓系統換算。")
                            else:
                                add_dividend(_real_idx, str(_d_date), _amt,
                                             per_share=_per, note=_d_note.strip())
                                st.session_state[f"show_div_{_real_idx}"] = False
                                st.success(f"已登錄配息 NT$ {_amt:,.0f}")
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
                            _has_dlog = bool(_e.get("dividend_log"))
                            with _ef7:
                                if _has_dlog:
                                    _e_div = None
                                    st.markdown("**已收股利（元）**")
                                    st.markdown(
                                        f"NT$ {_e.get('dividends', 0):,.0f}　"
                                        "<small>由配息明細計算<br>請用「配息」編輯</small>",
                                        unsafe_allow_html=True,
                                    )
                                else:
                                    _e_div = st.number_input("已收股利（元）", min_value=0.0,
                                                              value=float(_e.get("dividends", 0)),
                                                              step=100.0, format="%.0f")
                            _e_reason = st.text_input("買進理由", value=_e.get("buy_reason", ""),
                                                       placeholder="例：本益比偏低、財報轉機")
                            _sv_col, _cl_col = st.columns(2)
                            with _sv_col:
                                _save_clicked   = st.form_submit_button("儲存",
                                                      type="primary", use_container_width=True)
                            with _cl_col:
                                _cancel_clicked = st.form_submit_button("取消",
                                                      use_container_width=True)

                        if _save_clicked:
                            _upd = dict(shares=_e_shares, avg_cost=_e_cost,
                                        account=_e_acct, date=str(_e_date),
                                        stop_profit=_e_sp, stop_loss=_e_sl,
                                        buy_reason=_e_reason)
                            if not _has_dlog:          # 有配息明細時不從編輯框覆寫累計
                                _upd["dividends"] = _e_div
                            update_holding(_real_idx, **_upd)
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
            with st.expander(f"已賣出紀錄（共 {len(_sold)} 筆）"):
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

        # ── 日報快照 ──
        st.divider()
        with st.expander("日報快照（供台股晨報讀取）"):
            _snap_msg = st.session_state.pop("_snap_msg", None)
            if _snap_msg:
                st.info(_snap_msg)
            _snap_now = get_snapshot()
            if _snap_now and _snap_now.get("updated_at"):
                st.caption(
                    f"最後更新：{_snap_now['updated_at'][:16]}　·　"
                    f"行情日：{_snap_now.get('market_date', '—')}　·　"
                    f"狀態：{_snap_now.get('status', '—')}"
                )
            else:
                st.caption("尚未產生快照。開啟此頁會自動產生（30 分鐘內只寫一次）。")
            st.caption("快照讓雲端日報拿得到你的行情與損益（日報連不到 Yahoo）。手動更新可立即重寫。")
            if st.button("立即更新快照", key="snap_force_btn"):
                _msg = _maybe_write_snapshot(holdings, force=True)
                if _msg:
                    st.session_state["_snap_msg"] = _msg
                st.rerun()

        # ── 帳號管理 ──
        st.divider()
        with st.expander("帳號管理"):
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
        st.info("目前沒有持倉。點下方「新增」加入第一筆。")


# ── 速覽 ─────────────────────────────────────────────────────
elif page == "速覽":
    _now8 = datetime.datetime.now(_TZ8)
    _page_head("速覽", f"{_now8.month} 月 {_now8.day} 日")
    _html(ui.alerts(_ALERTS))

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

        # ── 持倉 P&L 與股數（依代碼合併多筆）──
        sv_pnl_map = {}
        for h in sv_holdings:
            ticker = format_ticker(h["code"])
            cur    = sv_prices.get(ticker, {}).get("price")
            code   = h["code"]
            if code not in sv_pnl_map:
                sv_pnl_map[code] = {"tot_shares": 0, "tot_cost": 0, "cur": cur, "cur_price": cur,
                                    "ticker": ticker, "name": h["name"]}
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

        # ── 今日焦點：最大貢獻／拖累 ──
        _sv_contrib = _day_contrib(sv_pnl_map, sv_prices)
        if _sv_contrib:
            _today_sum = sum(_sv_contrib.values())
            _best  = max(_sv_contrib, key=_sv_contrib.get)
            _worst = min(_sv_contrib, key=_sv_contrib.get)

            def _focus_cell(label: str, code: str) -> str:
                v = _sv_contrib[code]
                pct = sv_prices.get(sv_pnl_map[code]["ticker"], {}).get("today_pct")
                share = (f"佔今日獲利 {v / _today_sum * 100:.0f}%" if v > 0 and _today_sum > 0
                         else f"今日 {pct:+.2f}%" if pct is not None else "")
                return (f'<div style="background:{C["raised"]};padding:16px 14px;min-width:0">'
                        f'<div style="font-size:13px;color:{C["text_sub"]}">{label}</div>'
                        f'<div style="margin-top:10px;font-size:16px;font-weight:500;white-space:nowrap;overflow:hidden;'
                        f'text-overflow:ellipsis">{sv_pnl_map[code]["name"]}</div>'
                        f'<div class="n" style="font-size:30px;font-weight:300;line-height:1.2;color:{ui.tone(v)}">{ui.signed(v)}</div>'
                        f'<div class="n" style="font-size:12px;color:{C["text_sub"]}">{share}</div></div>')

            _cells = [_focus_cell("今天最大貢獻", _best)]
            if _worst != _best:
                _cells.append(_focus_cell("今天最大拖累", _worst))
            _html(f'<div style="display:grid;grid-template-columns:repeat({len(_cells)},minmax(0,1fr));gap:1px;'
                  f'background:{C["line"]};border:1px solid {C["line"]};margin-top:8px">' + "".join(_cells) + "</div>")

        # ── 近 6 週每日損益月曆（目前股數 × 每日收盤推算）──
        if sv_holding_tickers:
            try:
                _hist = get_ohlc_batch(sv_holding_tickers, period="3mo")
            except Exception:
                _hist = {}
            _vals = []
            for _sd in sv_pnl_map.values():
                _df = _hist.get(_sd["ticker"])
                if _df is not None and not _df.empty:
                    _vals.append(_df["Close"] * _sd["tot_shares"])
            if _vals:
                _port = pd.concat(_vals, axis=1).ffill().dropna().sum(axis=1)
                _chg  = _port.diff().dropna()
                _daily = {ts.date(): float(v) for ts, v in _chg.items()}
                _today8 = _now8.date()
                _cut = _today8 - datetime.timedelta(days=_today8.weekday(), weeks=5)
                _sum_m = {}
                for _d, _v in _daily.items():
                    if _d >= _cut:
                        _sum_m[_d.month] = _sum_m.get(_d.month, 0) + _v
                _msum = "　".join(f"{m} 月 {ui.signed(v)}" for m, v in sorted(_sum_m.items()))
                _html(f'<div style="display:flex;justify-content:space-between;align-items:baseline;margin:30px 0 12px">'
                      f'<h2 style="margin:0">近 6 週每日損益</h2>'
                      f'<span class="n" style="font-size:12px;color:{C["faint"]}">{_msum}</span></div>'
                      + ui.pnl_calendar(_daily, _today8))
                st.caption("以目前持股回推各日收盤價估算，期間有買賣時會有誤差。外框＝今天。")

        # ── 個股走勢 ──
        _html('<h2 style="margin:30px 0 0">個股走勢</h2>')
        _period_map   = {"當日": ("1d", "15m"), "週": ("5d", "1d"), "月": ("1mo", "1d")}
        sv_period_sel = st.radio("區間", list(_period_map), horizontal=True, index=2,
                                 label_visibility="collapsed")
        _kline_period, _kline_interval = _period_map[sv_period_sel]
        with st.spinner("載入走勢中..."):
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

        _cards = []
        for i, item in enumerate(sv_display):
            ticker    = format_ticker(item["code"])
            price_now = sv_prices.get(ticker, {}).get("price")
            today_pct = sv_prices.get(ticker, {}).get("today_pct")
            _closes   = sv_ohlc[ticker]["Close"].dropna().tolist() if ticker in sv_ohlc else []
            _foot = ""
            if item["is_holding"] and item["code"] in sv_pnl_map and sv_pnl_map[item["code"]]["pnl"] is not None:
                _pd = sv_pnl_map[item["code"]]
                _foot = (f'<div style="display:flex;justify-content:space-between;margin-top:6px;font-size:12px;'
                         f'color:{C["text_sub"]}"><span>未實現</span><span class="n" style="color:{ui.tone(_pd["pnl"])}">'
                         f'{ui.signed(_pd["pnl"])}</span></div>')
            elif not item["is_holding"]:
                _foot = f'<div style="margin-top:6px;font-size:12px;color:{C["faint"]}">額外追蹤</div>'
            _cards.append(ui.stock_card(
                item["name"], item["code"],
                f"{price_now:,.2f}" if price_now else "—",
                f"{today_pct:+.2f}%" if today_pct is not None else "—", ui.tone(today_pct),
                ui.spark(_closes, i, w=140, h=40) if len(_closes) >= 2
                else f'<div style="height:40px;font-size:12px;color:{C["faint"]}">無法載入走勢</div>',
                _foot))
        _html(f'<div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1px;margin-top:12px;'
              f'background:{C["line"]};border:1px solid {C["line"]}">' + "".join(_cards) + "</div>")

        # 額外追蹤的移除按鈕
        _extras_shown = [e for e in sv_display if not e["is_holding"]]
        if _extras_shown:
            st.caption("移除額外追蹤")
            with st.container(horizontal=True):
                for item in _extras_shown:
                    if st.button(f"移除 {item['name']}", key=f"sv_rm_{item['code']}"):
                        remove_quick_view_extra(item["code"])
                        st.rerun()
    else:
        st.info("持倉為空。新增持倉後，速覽會自動顯示。")

    # ── 新增額外追蹤股票 ──
    _html('<h2 style="margin:28px 0 0">加入其他股票到速覽</h2>')
    with st.form("sv_add_form", clear_on_submit=True):
        sv_code      = st.text_input("股票代碼", placeholder="例：2454")
        sv_submitted = st.form_submit_button("加入", type="primary", use_container_width=True)

    if sv_submitted:
        if not sv_code.strip():
            st.error("請輸入股票代碼")
        else:
            sv_input_upper  = sv_code.strip().upper()
            extra_codes     = {e["code"] for e in sv_extras}
            if sv_input_upper in sv_holding_codes:
                st.info(f"{sv_input_upper} 已在你的持倉中，速覽會自動顯示，不需要另外新增。")
            elif sv_input_upper in extra_codes:
                st.warning(f"{sv_input_upper} 已在速覽的額外追蹤中。")
            else:
                add_quick_view_extra(sv_input_upper, sv_input_upper)
                st.success(f"已加入：{sv_input_upper}（名稱會在速覽載入時自動更新）")
                st.rerun()


# ── 新增持倉 ─────────────────────────────────────────────────
elif page == "新增":
    _page_head("新增持倉", "改數字看下方預覽")
    _html(ui.alerts(_ALERTS))

    _has_sheets = False
    try:
        _has_sheets = "sheet_id" in st.secrets
    except Exception:
        pass
    if not _has_sheets:
        st.warning(
            "資料暫存中：目前沒有設定 Google Sheets，資料存在本機，App 重新啟動後會消失。"
            "請參考專案中的 SETUP.md 完成 Google Sheets 設定以永久保存資料。"
        )

    # 新增成功後清空欄位（必須在欄位建立前清）
    # （直接刪 key 欄位不會清空，要寫回預設值）
    if st.session_state.pop("_add_reset", False):
        st.session_state.update({
            "add_code": "", "add_shares": 0.0, "add_cost": 0.0, "add_date": datetime.date.today(),
            "add_acct_new": "", "add_sp": 0.0, "add_sl": 0.0, "add_note": "", "add_reason": "",
        })
    _add_msg = st.session_state.pop("_add_msg", None)
    if _add_msg:
        st.success(_add_msg)

    existing_accounts = get_accounts(get_holdings())
    # 不用 st.form：每次輸入都要重算下方的分配預覽
    c1, c2 = st.columns(2)
    with c1:
        new_code   = st.text_input("股票代碼", placeholder="例：2330", key="add_code")
        new_cost   = st.number_input("平均成本（元）", min_value=0.0, step=0.01, format="%.2f", key="add_cost")
    with c2:
        new_shares = st.number_input("股數", min_value=0.0, step=1.0, format="%.4g", key="add_shares")
        new_date   = st.date_input("買入日期", key="add_date")
    acct_options = existing_accounts + (["＋新增帳號"] if existing_accounts else [])
    if acct_options:
        acct_select = st.radio("帳號", acct_options, horizontal=True, key="add_acct")
    else:
        acct_select = "＋新增帳號"
    if acct_select == "＋新增帳號" or not acct_options:
        new_account = st.text_input("帳號名稱", placeholder="例：永豐、富邦", key="add_acct_new")
    else:
        new_account = acct_select
    ca1, ca2 = st.columns(2)
    with ca1:
        new_sp = st.number_input("停利價（選填，0＝未設）", min_value=0.0, step=0.5, format="%.2f", key="add_sp")
    with ca2:
        new_sl = st.number_input("停損價（選填，0＝未設）", min_value=0.0, step=0.5, format="%.2f", key="add_sl")
    new_reason = st.text_input("買進理由（選填）", placeholder="例：本益比低於同業、財報轉機、殖利率高",
                               key="add_reason")
    st.caption("之後跌超過 8%，會拿這句話問你「還成立嗎」。")
    new_note = st.text_input("備註（選填）", placeholder="例：定期定額、逢低加碼", key="add_note")

    # ── 加入後的持倉分配預覽 ──
    _cur_hold = get_holdings()
    if _cur_hold:
        _pv_tickers = tuple(sorted({format_ticker(h["code"]) for h in _cur_hold}))
        try:
            _pv_prices = get_current_prices(_pv_tickers)
        except Exception:
            _pv_prices = {}
        _before: dict[str, list] = {}
        for h in _cur_hold:
            _p = _pv_prices.get(format_ticker(h["code"]), {}).get("price")
            _v = h["shares"] * (_p or h["avg_cost"])
            if h["code"] not in _before:
                _before[h["code"]] = [h["name"], 0.0, _p]
            _before[h["code"]][1] += _v
        _code_in = new_code.strip().upper()
        _add_val = 0.0
        if _code_in and new_shares > 0:
            _known_price = _before.get(_code_in, [None, 0, None])[2]
            _add_val = new_shares * (_known_price or new_cost)
        _after = {k: [v[0], v[1]] for k, v in _before.items()}
        if _add_val > 0:
            if _code_in in _after:
                _after[_code_in][1] += _add_val
            else:
                _after[_code_in] = [f"{_code_in}（新）", _add_val]
        _b_items = [(k, v[0], v[1]) for k, v in _before.items()]
        _a_items = [(k, v[0], v[1]) for k, v in _after.items()]
        _a_total = sum(v for _, _, v in _a_items) or 1
        _mine_pct = _after[_code_in][1] / _a_total * 100 if (_add_val > 0 and _code_in in _after) else None
        _any_over = any(v / _a_total > 0.4 for _, _, v in _a_items)

        _html(
            f'<div style="margin-top:26px;padding-top:18px;border-top:1px solid {C["line"]}">'
            '<h2 style="margin:0">加入後的持倉分配</h2>'
            f'<div style="margin-top:14px;display:grid;grid-template-columns:44px minmax(0,1fr);row-gap:10px;'
            f'align-items:center;font-size:12px;color:{C["faint"]}">'
            f'<span>現在</span>{ui.alloc_strip(_b_items, legend=False)}'
            f'<span>加入後</span>{ui.alloc_strip(_a_items, legend=False, mark=_code_in)}</div>'
            f'<div style="position:relative;margin:4px 0 0 44px;height:14px">'
            f'<span style="position:absolute;left:40%;top:0;bottom:0;width:1px;background:#6E6A64"></span>'
            f'<span style="position:absolute;left:40%;top:0;transform:translateX(4px);font-size:11px;color:{C["faint"]}">40% 上限</span></div>'
            f'<div style="margin-top:6px">{ui.alloc_strip(_a_items, legend=True)}</div></div>'
        )
        if _mine_pct is None:
            _v_title, _v_body, _v_bd = "輸入代碼與股數就會預覽", "", C["line"]
        elif _mine_pct > 40:
            _v_title = f"{_after[_code_in][0]} 加入後會佔 {_mine_pct:.1f}%，超過 40%"
            _v_body = f"這筆約 NT$ {_add_val:,.0f}。確定要再集中嗎？可以考慮減少股數，或先把買進理由寫清楚。"
            _v_bd = "#5A2A26"
        elif _any_over:
            _v_title, _v_body, _v_bd = "這筆沒問題，但其他持股已超過 40%", f"這筆約 NT$ {_add_val:,.0f}。", C["line"]
        else:
            _v_title, _v_body, _v_bd = "加入後各檔都在 40% 以內", f"這筆約 NT$ {_add_val:,.0f}。", C["line"]
        _v_clr = C["up"] if (_mine_pct or 0) > 40 else C["text"]
        _html(f'<div style="margin-top:16px;padding:12px 14px;border:1px solid {_v_bd};background:{C["raised"]}">'
              f'<div style="font-size:14px;font-weight:500;color:{_v_clr}">{_v_title}</div>'
              f'<div style="font-size:13px;color:{C["text_sub"]};margin-top:2px">{_v_body}</div></div>')

    submitted = st.button("新增這筆持倉", type="primary", use_container_width=True, key="add_submit")

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
            st.session_state["_add_msg"] = (f"已新增【{account_name}】{stock_name}"
                                            f"（{new_code.strip().upper()}）{new_shares:.4g} 股")
            st.session_state["_add_reset"] = True
            st.rerun()

    # ── 匯出現有持倉（換到雲端時用）──
    holdings_now = get_holdings()
    if holdings_now:
        st.divider()
        st.subheader("匯出持倉 CSV")
        st.caption("換到雲端版時，先匯出、部署後再用「從 CSV 批次匯入」還原資料。")
        _df_exp = pd.DataFrame(holdings_now).reindex(
            columns=["code", "name", "shares", "avg_cost", "account", "date", "note"],
            fill_value="",
        )
        _df_exp.columns = ["股票代碼", "股票名稱", "股數", "平均成本", "帳號", "買入日期", "備註"]
        st.download_button(
            "下載持倉 CSV",
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
        "下載 CSV 範本",
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

                    if st.button(f"確認匯入 {len(df_csv)} 筆", type="primary"):
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
        st.success("匯入完成！到「持倉」頁查看結果。")
        if st.button("匯入另一份 CSV"):
            st.session_state.csv_imported = False
            st.rerun()


# ── 觀察清單 ─────────────────────────────────────────────────
elif page == "觀察":
    watchlist = get_watchlist()
    _page_head("觀察", f"{len(watchlist)} 檔" if watchlist else "")
    _html(ui.alerts([a for a in _ALERTS if a[0] != "buy"]))   # 到價改用下方卡片呈現

    if watchlist:
        wl_tickers = tuple(sorted({format_ticker(w["code"]) for w in watchlist}))
        with st.spinner("更新報價中..."):
            try:
                wl_prices = get_all_prices(wl_tickers)
            except Exception:
                wl_prices = {}
            try:
                wl_ohlc = get_ohlc_batch(wl_tickers)
            except Exception:
                wl_ohlc = {}

        wl_rows = []
        for i, w in enumerate(watchlist):
            t      = format_ticker(w["code"])
            pd_    = wl_prices.get(t, {})
            price  = pd_.get("price")
            target = float(w.get("target_price", 0) or 0)
            dist   = (price - target) / target * 100 if (price and target > 0) else None
            wl_rows.append((i, w, t, price, pd_.get("w1_pct"), pd_.get("m1_pct"), target, dist))
        # 有距離的依距離排（越接近目標越前面），沒設目標或沒報價的排最後
        wl_rows.sort(key=lambda r: (r[7] is None, r[7] if r[7] is not None else 0))

        # ── 已到目標價：提醒先確認理由，不是叫你買 ──
        for i, w, t, price, w1, m1, target, dist in wl_rows:
            if dist is not None and dist <= 0:
                _html(ui.target_hit_card(w["name"], w["code"], f"{price:,.2f}", f"{target:,.2f}", w.get("note", "")))
                with st.container(horizontal=True):
                    if st.button("看評估", key=f"hit_eval_{i}", use_container_width=True):
                        _go_eval(w["code"])
                    if st.button("寫理由並新增", key=f"hit_add_{i}", type="primary", use_container_width=True):
                        _go_add(w["code"])

        _html(f'<div style="display:flex;justify-content:space-between;margin-top:18px;padding-bottom:6px;'
              f'font-size:12px;color:{C["faint"]};border-bottom:1px solid {C["line"]}">'
              f'<span>依距離目標價排序　點一檔看走勢</span><span>1 週　1 月</span></div>')
        for i, w, t, price, w1, m1, target, dist in wl_rows:
            _k        = _safe_key(w["code"])
            _open_key = f"w_open_{w['code']}"
            _is_open  = st.session_state.get(_open_key, False)
            # 整列可點：沿用持倉頁的 hrow_／hrowbtn_ 透明按鈕樣式
            with st.container(key=f"hrow_w{_k}"):
                _html(ui.watch_row(w["name"], w["code"], w.get("note", ""),
                                   f"{price:,.2f}" if price else "—", w1, m1, target, dist))
                if st.button(f"{'收起' if _is_open else '展開'} {w['name']}", key=f"hrowbtn_w{_k}"):
                    st.session_state[_open_key] = not _is_open
                    st.rerun()

            if _is_open:
                _closes = wl_ohlc[t]["Close"].dropna().tolist() if t in wl_ohlc else []
                _html(ui.target_chart(_closes, target))
                tgt_key = f"edit_tgt_{i}"
                _editing = st.session_state.get(tgt_key, False)
                with st.container(horizontal=True):
                    if st.button("收起" if _editing else "目標價", key=f"tgt_btn_{i}", use_container_width=True):
                        st.session_state[tgt_key] = not _editing
                        st.rerun()
                    if st.button("評估", key=f"we_{i}", use_container_width=True):
                        _go_eval(w["code"])
                    if st.button("移除", key=f"wr_{i}", use_container_width=True):
                        remove_from_watchlist(i)
                        st.session_state.pop(_open_key, None)
                        st.rerun()
                if _editing:
                    with st.form(f"tgt_form_{i}", border=False):
                        new_target = st.number_input(
                            "目標買入價（填 0 表示取消設定）",
                            min_value=0.0, value=target, step=0.5, format="%.2f",
                        )
                        if st.form_submit_button("儲存", type="primary", use_container_width=True):
                            update_watchlist_item(i, target_price=new_target)
                            st.session_state[tgt_key] = False
                            st.rerun()
            _html(f'<div style="border-top:1px solid {C["line"]}"></div>')
    else:
        st.info("觀察清單是空的，請使用下方表單新增你想追蹤的股票。")

    st.subheader("新增觀察標的")
    with st.form("add_watchlist_form", clear_on_submit=True, border=False):
        wc1, wc2 = st.columns(2)
        with wc1:
            wl_code   = st.text_input("股票代碼", placeholder="例：0050")
        with wc2:
            wl_target = st.number_input(
                "目標買入價（選填）", min_value=0.0, step=0.5, format="%.2f",
                help="股價跌至此價位時，app 頂端會出現提醒。填 0 表示不設定。",
            )
        wl_note = st.text_input("為什麼想觀察（選填）", placeholder="例：等拉回再買")
        wl_submitted = st.form_submit_button("加入觀察", type="primary", use_container_width=True)
    st.caption("跌到目標價時，每一頁頂端都會出現提醒。")

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
                    st.success(f"已加入觀察清單：{wl_name}（{wl_code.strip().upper()}）")
                    st.rerun()
            except Exception:
                st.error("查詢失敗，請確認代碼是否正確")


# ── 股票評估 ─────────────────────────────────────────────────
elif page == "評估":
    _page_head("評估", "解讀基本面數字")
    _html(ui.alerts(_ALERTS))

    # 從其他頁跳過來（觀察、持倉）：直接帶入代碼並查詢
    if st.session_state.eval_ticker:
        st.session_state.eval_code    = st.session_state.eval_ticker
        st.session_state.eval_current = st.session_state.eval_ticker
        st.session_state.eval_ticker  = ""

    def _pick_recent() -> None:
        _p = st.session_state.get("eval_recent_pick")
        if _p:
            st.session_state.eval_code    = _p
            st.session_state.eval_current = _p
        st.session_state.eval_recent_pick = None

    with st.form("eval_form", border=False):
        with st.container(horizontal=True, vertical_alignment="bottom"):
            _code_in = st.text_input("台股代碼", key="eval_code", placeholder="例：0050、2330、00878")
            _go = st.form_submit_button("評估", type="primary")
    if _go and _code_in.strip():
        st.session_state.eval_current = _code_in.strip().upper()
    _recent = st.session_state.get("eval_recent", [])
    if _recent:
        st.pills("最近查過", _recent, key="eval_recent_pick", on_change=_pick_recent)

    _cur = st.session_state.get("eval_current")
    if not _cur:
        st.caption("輸入台股代碼，解讀這支股票的基本面數字。")
    else:
        ticker = format_ticker(_cur)
        info, history = None, None
        with st.spinner(f"正在拉取 {_cur} 的資料..."):
            try:
                info    = get_stock_info(ticker)
                history = get_price_history(ticker, "1y")
            except Exception as e:
                st.error(f"資料拉取失敗：{e}")
        if info is not None and not info.get("price"):
            st.error("找不到這個代碼的資料，請確認輸入是否正確。")
            info = None

        if info is not None:
            st.session_state.eval_recent = ([_cur] + [c for c in _recent if c != _cur])[:3]
            is_etf = info.get("quote_type") == "ETF"
            kind   = "ETF" if is_etf else "・".join(x for x in (info.get("sector"), info.get("industry")) if x)
            closes = history["Close"].dropna() if history is not None and not history.empty else None
            today  = None
            if closes is not None and len(closes) >= 2:
                today = (closes.iloc[-1] - closes.iloc[-2]) / closes.iloc[-2] * 100
            _html(f'<div style="display:flex;justify-content:space-between;align-items:baseline;gap:12px;margin-top:18px">'
                  f'<span style="font-size:24px;font-weight:500">{info["name"]} <span class="n" style="font-size:14px;'
                  f'font-weight:400;color:{C["faint"]}">{_cur}</span></span>'
                  f'<span style="font-size:12px;color:{C["faint"]};text-align:right">{kind}</span></div>'
                  f'<div style="display:flex;align-items:baseline;gap:12px;margin-top:4px">'
                  f'<span class="n" style="font-size:52px;font-weight:300;letter-spacing:-0.02em;line-height:1.1">'
                  f'{info["price"]:,.2f}</span><span class="n" style="font-size:15px;color:{ui.tone(today)}">'
                  f'{"—" if today is None else f"{today:+.2f}%"}</span></div>')

            pos = price_position(info)
            if pos:
                _html(ui.range_bar(pos["low"], pos["high"], pos["price"], pos["label"] + "。"))

            if closes is not None and len(closes) >= 2:
                _rng = st.segmented_control("走勢", ["3 月", "6 月", "1 年"], default="1 年", key="eval_range")
                _n = {"3 月": 63, "6 月": 125}.get(_rng or "1 年", len(closes))
                _seg = closes.tail(_n)
                _html(ui.line_chart(_seg.tolist(), f"{_seg.index[0]:%Y/%m/%d}", f"{_seg.index[-1]:%m/%d}",
                                    f"{info['name']} 近{_rng or '1 年'}收盤走勢，最新 {_seg.iloc[-1]:,.2f}"))

            st.subheader("基本面指標　點一下看白話解釋")
            if is_etf:
                st.info("ETF 是一籃子股票，不是單一公司，所以本益比、淨利率、營收成長率這類指標通常沒有資料。這是正常現象。")
            _html(ui.metric_rows(evaluate(info)))

            _in_watch = any(w["code"] == _cur for w in get_watchlist())
            with st.container(horizontal=True):
                if st.button("已在觀察清單" if _in_watch else "加入觀察", key="eval_to_watch",
                             disabled=_in_watch, use_container_width=True):
                    add_to_watchlist(_cur, info["name"])
                    st.rerun()
                if st.button("新增持倉", key="eval_to_add", type="primary", use_container_width=True):
                    _go_add(_cur)
            st.caption("數字只是起點，不是買賣訊號。")


# ── 補知識 ───────────────────────────────────────────────────
elif page == "知識":
    _kb_read  = set(get_kb_read())
    _titles   = [re.sub(r"^第.章：", "", c["title"]) for c in CHAPTERS]
    _kb_total = sum(len(c["sections"]) for c in CHAPTERS)
    _kb_valid = {f"{ci}-{si}" for ci, c in enumerate(CHAPTERS) for si in range(len(c["sections"]))}
    _n_read   = len(_kb_read & _kb_valid)
    _page_head("知識", f"已讀 {_n_read} / {_kb_total}")
    _html(ui.read_progress(_n_read, _kb_total))

    _kb_q = st.text_input("找問題", placeholder="例：殖利率、手續費、大跌", key="kb_q").strip()
    st.session_state.setdefault("kb_chap", 0)

    def _kb_step(d: int) -> None:
        st.session_state.kb_chap = max(0, min(len(CHAPTERS) - 1, st.session_state.kb_chap + d))

    if _kb_q:
        _items = [(ci, si) for ci, c in enumerate(CHAPTERS) for si, s in enumerate(c["sections"])
                  if _kb_q in s["q"] or _kb_q in s["a"]]
        st.caption(f"「{_kb_q}」找到 {len(_items)} 題" if _items else f"「{_kb_q}」沒有相關的題目，換個說法試試")
    else:
        st.pills("章節", list(range(len(CHAPTERS))), key="kb_chap", required=True,
                 format_func=lambda i: f"{i + 1:02d} {_titles[i]}", label_visibility="collapsed")
        _ci = st.session_state.kb_chap
        _cn = sum(1 for si in range(len(CHAPTERS[_ci]["sections"])) if f"{_ci}-{si}" in _kb_read)
        _html(f'<div style="display:flex;justify-content:space-between;align-items:baseline;margin:18px 0 6px">'
              f'<span style="font-size:22px;font-weight:500"><span class="n" style="font-weight:300;color:{C["faint"]};'
              f'margin-right:10px">{_ci + 1:02d}</span>{_titles[_ci]}</span>'
              f'<span class="n" style="font-size:12px;color:{C["faint"]}">已讀 {_cn} / {len(CHAPTERS[_ci]["sections"])}</span></div>')
        _items = [(_ci, si) for si in range(len(CHAPTERS[_ci]["sections"]))]

    for ci, si in _items:
        _sec = CHAPTERS[ci]["sections"][si]
        _qid = f"{ci}-{si}"
        # 標題要固定不變：一改字（例如已讀變灰），Streamlit 會當成新元件，剛展開的又收起來
        _label = f"{ci + 1}.{si + 1}　{_sec['q']}"
        # 展開就記成已讀（存進 Sheet 的 kb_read）
        with st.expander(_label, key=f"kb_{_qid}", on_change=mark_kb_read, args=(_qid,)):
            st.markdown(_sec["a"])

    if not _kb_q:
        with st.container(horizontal=True):
            st.button("上一章", key="kb_prev", on_click=_kb_step, args=(-1,),
                      disabled=st.session_state.kb_chap == 0, use_container_width=True)
            st.button("下一章", key="kb_next", on_click=_kb_step, args=(1,),
                      disabled=st.session_state.kb_chap == len(CHAPTERS) - 1, use_container_width=True)


st.caption("本工具僅供個人記錄參考，不構成投資建議。")
