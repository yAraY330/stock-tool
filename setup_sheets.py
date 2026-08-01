# -*- coding: utf-8 -*-
"""台股溝 × Google Sheets 設定腳本

兩件事，預設只做第 1 件（安全、可重複跑）：
  1. 產生 .streamlit/secrets.toml（換機器 / 重裝時會用到）——預設動作。
  2. 把本機 portfolio.json 的持倉/清單灌進 Sheet（一次性搬遷 / 災難復原）——
     需加 --migrate 才會做，且採「安全合併」：先讀現有 Sheet，只覆寫持倉相關的鍵，
     snapshot 與 opinions 一律保留；若 Sheet 已有 snapshot/opinions，預設中止，
     確認要用本機資料覆蓋持倉時再加 --force（仍不會抹掉 snapshot/opinions）。

設定改用環境變數，不再寫死路徑：
  GCP_SA_KEY                       service account JSON 全文（優先）
  GOOGLE_APPLICATION_CREDENTIALS   指向 JSON 金鑰檔路徑（次之）
  SHEET_ID                         目標試算表 ID（可省，用預設）

用法：
  python setup_sheets.py                     # 只產生 secrets.toml
  python setup_sheets.py --migrate           # 另外把 portfolio.json 安全合併進 Sheet
  python setup_sheets.py --migrate --force   # Sheet 已有 snapshot/opinions 時仍執行合併
"""
import argparse
import json
import os
import sys
from pathlib import Path

# Windows 主控台預設 cp950，印 ✓ ⛔ 等字元會崩潰；統一切 UTF-8。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 目標試算表 ID（可用 SHEET_ID 環境變數覆寫）
_DEFAULT_SHEET_ID = "15Bmw-uno3yDFEv6siIiXVYFe2BmtwtAEAeDB9mjT3zI"

HERE = Path(__file__).resolve().parent
SECRETS_PATH = HERE / ".streamlit" / "secrets.toml"
PORTFOLIO_JSON = HERE / "portfolio.json"

# 屬於本機 portfolio.json、可被搬遷覆蓋的鍵；snapshot / opinions 不在此列，永不覆寫。
_PORTFOLIO_KEYS = ("holdings", "watchlist", "favorites", "quick_view_extras", "sold")


def _sheet_id() -> str:
    return os.environ.get("SHEET_ID", _DEFAULT_SHEET_ID)


def _load_key_dict() -> dict:
    """從環境變數取 service account 金鑰（dict）。"""
    raw = os.environ.get("GCP_SA_KEY")
    if raw:
        return json.loads(raw)
    path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if path and Path(path).exists():
        return json.loads(Path(path).read_text(encoding="utf-8"))
    sys.exit("❌ 找不到金鑰：請設環境變數 GCP_SA_KEY（JSON 全文）或 "
             "GOOGLE_APPLICATION_CREDENTIALS（JSON 檔路徑）")


def esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def step1_write_secrets(key: dict) -> str:
    lines = [f'sheet_id = "{_sheet_id()}"', "", "[gcp_service_account]"]
    for k, v in key.items():
        if isinstance(v, str):
            lines.append(f'{k} = "{esc(v)}"')
        else:
            lines.append(f"{k} = {json.dumps(v)}")
    SECRETS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SECRETS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"✅ 已產生 {SECRETS_PATH}")
    client_email = key.get("client_email", "(找不到 client_email)")
    print("─" * 60)
    print("⚠️  請把『台股工具』試算表【共用】給這個帳號（權限選編輯者）：")
    print(f"    {client_email}")
    print("─" * 60)
    return client_email


def step2_migrate(key: dict, force: bool) -> None:
    """安全合併：讀現有 Sheet → 只覆寫持倉相關鍵 → snapshot/opinions 保留。"""
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError:
        print("⚠️  尚未安裝套件，先執行： pip install gspread google-auth  再跑一次")
        return
    if not PORTFOLIO_JSON.exists():
        print(f"⚠️  找不到 {PORTFOLIO_JSON}，跳過搬遷。")
        return

    local = json.loads(PORTFOLIO_JSON.read_text(encoding="utf-8"))
    creds = Credentials.from_service_account_info(
        key,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )
    gc = gspread.authorize(creds)
    try:
        book = gc.open_by_key(_sheet_id())
    except Exception as e:
        print(f"❌ 開不了試算表：{e}\n   多半是還沒共用給服務帳號 email，共用好再跑一次。")
        return
    try:
        ws = book.worksheet("portfolio")
    except Exception:
        ws = book.add_worksheet(title="portfolio", rows=1, cols=1)
        print("   （已自動建立 portfolio 分頁）")

    existing_raw = ws.cell(1, 1).value
    existing = json.loads(existing_raw) if existing_raw else {}

    # 防護：Sheet 已有 snapshot / opinions（排程與觀點管線的產物），預設中止，
    # 以免用本機 portfolio.json 的持倉覆蓋掉。--force 仍只覆寫持倉，不碰這兩塊。
    if (existing.get("snapshot") or existing.get("opinions")) and not force:
        have = [k for k in ("snapshot", "opinions") if existing.get(k)]
        print(f"⛔ Sheet 已有 {', '.join(have)}，中止搬遷以免覆蓋持倉。")
        print("   （snapshot/opinions 本來就不會被動；確定要用本機持倉覆蓋 Sheet 上的"
              "持倉，才加 --force 再跑一次。）")
        return

    # 合併：保留 existing 全部（含 snapshot/opinions），只用本機值覆蓋持倉相關鍵。
    merged = dict(existing)
    for k in _PORTFOLIO_KEYS:
        if k in local:
            merged[k] = local[k]

    ws.update_cell(1, 1, json.dumps(merged, ensure_ascii=False))
    kept = [k for k in ("snapshot", "opinions") if merged.get(k)]
    print(f"✅ 已合併寫入 portfolio!A1："
          f"holdings={len(merged.get('holdings', []))} "
          f"watchlist={len(merged.get('watchlist', []))}"
          + (f"；保留 {', '.join(kept)} 未動" if kept else ""))


def main() -> int:
    ap = argparse.ArgumentParser(description="台股溝 Google Sheets 設定")
    ap.add_argument("--migrate", action="store_true",
                    help="另外把 portfolio.json 安全合併進 Sheet（一次性搬遷/災難復原）")
    ap.add_argument("--force", action="store_true",
                    help="Sheet 已有 snapshot/opinions 時仍執行合併（仍不覆寫這兩塊）")
    args = ap.parse_args()

    print("=== 台股溝 Google Sheets 設定 ===\n")
    key = _load_key_dict()
    step1_write_secrets(key)
    if args.migrate:
        print()
        step2_migrate(key, args.force)
    else:
        print("\n（只做了 secrets.toml；要把本機持倉搬進 Sheet 再加 --migrate）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
