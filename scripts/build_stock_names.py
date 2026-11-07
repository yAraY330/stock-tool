"""產生 modules/stock_names.json（股票代號 → 中文簡稱，上市＋上櫃含 ETF）
與 modules/otc_codes.json（上櫃代號清單，format_ticker 用來決定加 .TWO）。

手動執行，不在 App 啟動時跑。新股上市時重跑一次即可：
    python scripts/build_stock_names.py
TWSE 憑證在部分 Python 版本驗證失敗（Missing SKI）時，先用 curl 下載再餵檔：
    curl -o twse.json https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL
    curl -o tpex.json https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes
    python scripts/build_stock_names.py --from-files twse.json tpex.json
"""
import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

TWSE_URL = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
TPEX_URL = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes"
OUT = Path(__file__).resolve().parent.parent / "modules" / "stock_names.json"
OTC_OUT = OUT.with_name("otc_codes.json")

# 只留股票與 ETF：4 碼普通股，或 00 開頭的 ETF（可帶 A/B/L/R/U 等字尾）；濾掉權證、債券、特別股
CODE_RE = re.compile(r"^(\d{4}|00\d{2,4}[A-Z]?)$")


def _fetch(url: str) -> list:
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        sys.exit(f"下載失敗：{url}\n{e}\n請改用 curl 下載後加 --from-files（見檔頭說明）")


def _read(path: str) -> list:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build(twse: list, tpex: list) -> tuple[dict, list, list]:
    listed = {x["Code"].strip(): x["Name"].strip() for x in twse}
    otc = {x["SecuritiesCompanyCode"].strip(): x["CompanyName"].strip() for x in tpex}
    names, conflicts = {}, []
    for src in (listed, otc):
        for code, name in src.items():
            name = name.replace("*", "")  # 交易所的「面額非 10 元」標記，不是股名（國巨* → 國巨）
            if not CODE_RE.match(code) or not name:
                continue
            if code in names and names[code] != name:
                conflicts.append((code, names[code], name))
                continue
            names[code] = name
    # 上市／上櫃同代號不同名 → 不自動選，兩邊都拿掉，讓 App 退回原本名稱
    for code, _, _ in conflicts:
        names.pop(code, None)
    otc_codes = sorted(c for c in otc if c in names)
    return dict(sorted(names.items())), otc_codes, conflicts


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-files", nargs=2, metavar=("TWSE_JSON", "TPEX_JSON"))
    args = ap.parse_args()
    if args.from_files:
        twse, tpex = _read(args.from_files[0]), _read(args.from_files[1])
    else:
        twse, tpex = _fetch(TWSE_URL), _fetch(TPEX_URL)

    names, otc_codes, conflicts = build(twse, tpex)
    OUT.write_text(json.dumps(names, ensure_ascii=False, indent=0), encoding="utf-8")
    OTC_OUT.write_text(json.dumps(otc_codes, indent=0), encoding="utf-8")
    print(f"寫入 {OUT}：{len(names)} 檔")
    print(f"寫入 {OTC_OUT}：上櫃 {len(otc_codes)} 檔")
    for code, a, b in conflicts:
        print(f"衝突（已排除）：{code} 上市「{a}」／上櫃「{b}」")


if __name__ == "__main__":
    main()
