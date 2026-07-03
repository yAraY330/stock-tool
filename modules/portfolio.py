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


@st.cache_data(ttl=30)
def _load_sheets() -> dict:
    try:
        raw = _get_ws().cell(1, 1).value
        if raw:
            return json.loads(raw)
    except Exception:
        pass
    return {"holdings": [], "watchlist": [], "favorites": []}


# ── 本機 JSON（開發模式）─────────────────────────────────────
def _load_file() -> dict:
    if _DATA.exists():
        try:
            return json.loads(_DATA.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"holdings": [], "watchlist": [], "favorites": []}


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
                date: str = "", note: str = "", account: str = "預設帳號") -> None:
    data = _load()
    data["holdings"].append({
        "code": code, "name": name,
        "shares": shares, "avg_cost": avg_cost,
        "date": date, "note": note, "account": account,
    })
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
