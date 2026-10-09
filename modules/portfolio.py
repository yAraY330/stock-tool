import json
from pathlib import Path
import streamlit as st

_DATA = Path(__file__).parent.parent / "portfolio.json"


# ── 環境偵測 ───────────────────────────────────────────────────
def _use_sheets() -> bool:
    """有設定 Google Sheets secrets 就用雲端，否則用本機 JSON。"""
    try:
        return "sheet_id" in st.secrets
    except Exception:
        return False


# ── Google Sheets（雲端模式）─────────────────────────────────
@st.cache_resource
def _sheets_client():
    import gspread
    from google.oauth2.service_account import Credentials
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )
    return gspread.authorize(creds)


@st.cache_resource
def _get_ws():
    book = _sheets_client().open_by_key(st.secrets["sheet_id"])
    try:
        return book.worksheet("portfolio")
    except Exception:
        return book.add_worksheet(title="portfolio", rows=1, cols=1)


def _empty() -> dict:
    return {"holdings": [], "watchlist": [], "favorites": [],
            "sold": [], "quick_view_extras": [], "snapshot": None, "kb_read": []}


@st.cache_data(ttl=30)
def _load_sheets() -> dict:
    try:
        raw = _get_ws().cell(1, 1).value
        if raw:
            return json.loads(raw)
    except Exception:
        pass
    return _empty()


# ── 本機 JSON（開發模式）─────────────────────────────────────
def _load_file() -> dict:
    if _DATA.exists():
        try:
            return json.loads(_DATA.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return _empty()


# ── 統一讀寫入口 ──────────────────────────────────────────────
def _load() -> dict:
    return _load_sheets() if _use_sheets() else _load_file()


def _save(data: dict) -> None:
    if _use_sheets():
        _get_ws().update_cell(1, 1, json.dumps(data, ensure_ascii=False))
        _load_sheets.clear()
    else:
        _DATA.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )


# ── 持倉 ─────────────────────────────────────────────────────
def get_holdings() -> list:
    return _load()["holdings"]


def add_holding(code: str, name: str, shares: float, avg_cost: float,
                date: str = "", note: str = "", account: str = "預設帳號",
                stop_profit: float = 0.0, stop_loss: float = 0.0,
                buy_reason: str = "", dividends: float = 0.0) -> None:
    data = _load()
    entry: dict = {
        "code": code, "name": name,
        "shares": shares, "avg_cost": avg_cost,
        "date": date, "note": note, "account": account,
    }
    if stop_profit > 0:
        entry["stop_profit"] = stop_profit
    if stop_loss > 0:
        entry["stop_loss"] = stop_loss
    if buy_reason:
        entry["buy_reason"] = buy_reason
    if dividends > 0:
        entry["dividends"] = dividends
    data["holdings"].append(entry)
    _save(data)


def update_holding(idx: int, **fields) -> None:
    data = _load()
    if 0 <= idx < len(data["holdings"]):
        data["holdings"][idx].update(fields)
        _save(data)


def remove_holding(idx: int) -> None:
    data = _load()
    if 0 <= idx < len(data["holdings"]):
        data["holdings"].pop(idx)
        _save(data)


def get_accounts(holdings: list) -> list[str]:
    seen = []
    for h in holdings:
        a = h.get("account", "預設帳號")
        if a not in seen:
            seen.append(a)
    return seen


def rename_account(old_name: str, new_name: str) -> None:
    data = _load()
    for h in data["holdings"]:
        if h.get("account", "預設帳號") == old_name:
            h["account"] = new_name
    _save(data)


# ── 最愛 ─────────────────────────────────────────────────────
def get_favorites() -> list:
    return _load().get("favorites", [])


def toggle_favorite(code: str) -> None:
    data = _load()
    favs = data.get("favorites", [])
    if code in favs:
        favs.remove(code)
    else:
        favs.append(code)
    data["favorites"] = favs
    _save(data)


# ── 觀察清單 ──────────────────────────────────────────────────
def get_watchlist() -> list:
    return _load()["watchlist"]


def add_to_watchlist(code: str, name: str, note: str = "",
                     target_price: float = 0.0) -> None:
    data = _load()
    if not any(w["code"] == code for w in data["watchlist"]):
        entry: dict = {"code": code, "name": name, "note": note}
        if target_price > 0:
            entry["target_price"] = target_price
        data["watchlist"].append(entry)
        _save(data)


def update_watchlist_item(idx: int, **fields) -> None:
    data = _load()
    if 0 <= idx < len(data["watchlist"]):
        data["watchlist"][idx].update(fields)
        _save(data)


def remove_from_watchlist(idx: int) -> None:
    data = _load()
    if 0 <= idx < len(data["watchlist"]):
        data["watchlist"].pop(idx)
        _save(data)


# ── 賣出記錄 ──────────────────────────────────────────────────
def get_sold() -> list:
    return _load().get("sold", [])


def sell_holding(idx: int, sell_price: float, sell_date: str,
                 shares_to_sell: float = 0.0) -> None:
    data = _load()
    if not (0 <= idx < len(data["holdings"])):
        return
    h = data["holdings"][idx]
    actual = min(shares_to_sell if shares_to_sell > 0 else h["shares"], h["shares"])
    data.setdefault("sold", []).append({
        "code":       h["code"],
        "name":       h["name"],
        "shares":     actual,
        "avg_cost":   h["avg_cost"],
        "sell_price": sell_price,
        "buy_date":   h.get("date", ""),
        "sell_date":  sell_date,
        "account":    h.get("account", "預設帳號"),
        "buy_reason": h.get("buy_reason", ""),
        "dividends":  h.get("dividends", 0.0),
        "pnl":        round((sell_price - h["avg_cost"]) * actual, 2),
    })
    remaining = round(h["shares"] - actual, 6)
    if remaining <= 0:
        data["holdings"].pop(idx)
    else:
        data["holdings"][idx]["shares"] = remaining
    _save(data)


# ── 配息明細 ──────────────────────────────────────────────────
# dividend_log 是每筆配息的明細（可回溯是哪一次除息）；
# dividends 欄位保留為累計值（＝log 加總），向後相容舊資料與讀取端。
def _sync_dividends(h: dict) -> None:
    """依 dividend_log 重算 dividends 累計值。"""
    log = h.get("dividend_log", [])
    h["dividends"] = round(sum(x.get("amount", 0) for x in log), 2)


def add_dividend(idx: int, date: str, amount: float,
                 per_share: float | None = None, note: str = "") -> None:
    data = _load()
    if not (0 <= idx < len(data["holdings"])):
        return
    h = data["holdings"][idx]
    entry: dict = {"date": date, "amount": round(amount, 2)}
    if per_share is not None and per_share > 0:
        entry["per_share"] = per_share
    if note:
        entry["note"] = note
    h.setdefault("dividend_log", []).append(entry)
    _sync_dividends(h)
    _save(data)


def remove_dividend(idx: int, log_idx: int) -> None:
    data = _load()
    if not (0 <= idx < len(data["holdings"])):
        return
    h = data["holdings"][idx]
    log = h.get("dividend_log", [])
    if 0 <= log_idx < len(log):
        log.pop(log_idx)
        h["dividend_log"] = log
        _sync_dividends(h)
        _save(data)


# ── 速覽表額外追蹤 ────────────────────────────────────────────
def get_quick_view_extras() -> list:
    return _load().get("quick_view_extras", [])


def add_quick_view_extra(code: str, name: str) -> None:
    data = _load()
    extras = data.get("quick_view_extras", [])
    if not any(e["code"] == code for e in extras):
        extras.append({"code": code, "name": name})
        data["quick_view_extras"] = extras
        _save(data)


def remove_quick_view_extra(code: str) -> None:
    data = _load()
    extras = data.get("quick_view_extras", [])
    data["quick_view_extras"] = [e for e in extras if e["code"] != code]
    _save(data)


# ── 每日快照（供台股晨報日報讀取）────────────────────────────
# ── 知識頁已讀進度（題目 id 形如 "2-1"＝第 3 章第 2 題）──────────────
def get_kb_read() -> list:
    return _load().get("kb_read", [])


def mark_kb_read(qid: str) -> None:
    """只動 kb_read 這個鍵；寫法同 save_snapshot，先清快取重讀再寫。"""
    if _use_sheets():
        _load_sheets.clear()
    data = _load()
    # 防呆：重讀拿不到任何持倉與觀察 → 可能是雲端讀取失敗，寫回會抹掉資料，寧可不寫
    if _use_sheets() and not data.get("holdings") and not data.get("watchlist"):
        return
    read = data.get("kb_read", [])
    if qid not in read:
        data["kb_read"] = read + [qid]
        _save(data)


def get_snapshot() -> dict | None:
    return _load().get("snapshot")


def save_snapshot(snapshot: dict) -> None:
    """只覆寫 snapshot 這一個鍵，其餘持倉資料原封不動。

    覆寫防護：Sheets 模式先清 30 秒快取、重讀最新，才寫回，避免蓋掉使用者
    剛做的變更。呼叫此函式前 snapshot 必須已組好，讀寫之間不要做耗時運算。
    """
    if _use_sheets():
        _load_sheets.clear()
    data = _load()
    # 防呆：快照裡有部位、重讀卻拿不到任何持倉 → 極可能是雲端讀取暫時失敗，
    # 此時寫回會把 Sheet 上的持倉整個抹掉，寧可不寫（保留舊資料）。
    if snapshot.get("positions") and not data.get("holdings"):
        return
    data["snapshot"] = snapshot
    _save(data)
