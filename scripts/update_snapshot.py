#!/usr/bin/env python3
"""每天自動把台股快照算好並寫回 Google Sheet（headless，供 GitHub Actions 排程呼叫）。

與 app.py 互動時的快照寫入完全等價，但不依賴 Streamlit runtime / session_state，
也不套用「30 分鐘節流」——每次執行都重算並寫入。

寫回的 JSON 結構與 app.py 一致（欄位、鍵名不可改），下游台股日報依賴此結構：
    holdings / watchlist / snapshot.{updated_at,market_date,status,quotes,positions,totals}
只覆寫 `snapshot` 這一個鍵，其餘持倉資料原封不動。

認證：
    - GCP_SA_KEY               service account JSON 全文（CI 用，優先）
    - GOOGLE_APPLICATION_CREDENTIALS  指向 JSON 檔路徑（本機測試用，退而求其次）
Sheet：
    - SHEET_ID 環境變數可覆寫，預設為專案目標 Sheet。
    - 該 Sheet 必須「分享給 service account 的 email、權限＝編輯者」，否則寫不進去。

用法：
    python scripts/update_snapshot.py            # 算好並寫回 Sheet
    python scripts/update_snapshot.py --dry-run  # 只算並印出，不寫入（測試用）
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
from pathlib import Path

# 讓 `import modules.*` 能運作（本腳本位於 scripts/ 之下）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Windows 主控台預設 cp950，印 ✓ 等字元會在「寫入成功之後」崩潰、讓排程誤判失敗。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

import gspread
from google.oauth2.service_account import Credentials

from modules.data import format_ticker
from modules.market import compute_snapshot_data
from modules.snapshot import build_snapshot, decide_write

_TZ8 = datetime.timezone(datetime.timedelta(hours=8))
_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
_DEFAULT_SHEET_ID = "15Bmw-uno3yDFEv6siIiXVYFe2BmtwtAEAeDB9mjT3zI"
_WORKSHEET = "portfolio"


def _load_credentials() -> Credentials:
    raw = os.environ.get("GCP_SA_KEY")
    if raw:
        return Credentials.from_service_account_info(json.loads(raw), scopes=_SCOPES)
    path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if path and Path(path).exists():
        return Credentials.from_service_account_file(path, scopes=_SCOPES)
    sys.exit("✗ 找不到 service account 憑證：請設環境變數 GCP_SA_KEY 或 GOOGLE_APPLICATION_CREDENTIALS")


def _open_worksheet():
    gc = gspread.authorize(_load_credentials())
    sheet_id = os.environ.get("SHEET_ID", _DEFAULT_SHEET_ID)
    return gc.open_by_key(sheet_id).worksheet(_WORKSHEET)


def _read_data(ws) -> dict:
    raw = ws.cell(1, 1).value
    return json.loads(raw) if raw else {}


def build_payload(data: dict, now: datetime.datetime) -> dict | None:
    """從 Sheet data 算出快照 payload；抓不到任何行情回 None（呼叫端保留舊快照）。

    報價範圍＝holdings ∪ watchlist（去重）；positions 仍只算 holdings（觀察清單
    沒有成本，硬算會產生誤導數字）。"""
    holdings = data.get("holdings", [])
    if not holdings:
        print("• Sheet 沒有持倉，跳過（不覆寫）")
        return None

    watchlist = data.get("watchlist", []) or []
    codes = {h["code"] for h in holdings} | {w["code"] for w in watchlist}
    tickers = tuple(sorted({format_ticker(c) for c in codes}))
    snap_data = compute_snapshot_data(tickers)
    quotes = snap_data.get("quotes", {})
    if not quotes:
        print("⚠ 全抓不到行情，保留舊快照未更新")
        return None

    return build_snapshot(
        holdings, quotes,
        snap_data.get("market_date"), now,
        snap_data.get("stale_codes", []),
        snap_data.get("suspect_codes", []),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="更新台股快照並寫回 Google Sheet")
    parser.add_argument("--dry-run", action="store_true",
                        help="只算並印出 payload，不寫入 Sheet")
    args = parser.parse_args()

    ws = _open_worksheet()
    data = _read_data(ws)
    existing = data.get("snapshot")
    now = datetime.datetime.now(_TZ8)

    new_payload = build_payload(data, now)

    if new_payload is None:
        # 沒算出新快照（沒持倉或全抓不到行情）。若已有舊快照，仍前進
        # last_attempt_at 讓下游知道「排程有跑、只是這次沒資料」；否則沒東西可寫。
        if not existing:
            print("• 無新快照且無既有快照，不寫入")
            return 1
        final = dict(existing)
        final["last_attempt_at"] = now.isoformat()
        final["skip_reason"] = "no_quotes"
        wrote_new = False
    else:
        final = decide_write(new_payload, existing, now)
        wrote_new = final.get("skip_reason") is None

    if wrote_new:
        print(f"• 算好快照：updated_at={final['updated_at']} "
              f"market_date={final['market_date']} status={final['status']} "
              f"positions={len(final['positions'])} quotes={len(final['quotes'])} "
              f"stale={final['stale_codes']} suspect={final['suspect_codes']}")
    else:
        print(f"• 決定不覆寫（skip_reason={final['skip_reason']}）："
              f"保留既有 market_date={existing.get('market_date')}，"
              f"只前進 last_attempt_at={final['last_attempt_at']}")

    if args.dry_run:
        print("• --dry-run：不寫入 Sheet")
        return 0

    # 覆寫防護：寫入前重讀最新一次，只覆寫 snapshot 鍵；
    # 若重讀拿不到任何持倉，極可能是暫時讀取失敗，寧可不寫以免抹掉 Sheet 上的持倉。
    latest = _read_data(ws)
    if final.get("positions") and not latest.get("holdings"):
        print("⚠ 重讀拿不到持倉，放棄寫入以免抹掉資料")
        return 1
    latest["snapshot"] = final
    ws.update_cell(1, 1, json.dumps(latest, ensure_ascii=False))
    print("✓ 已寫回 Sheet")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
