"""股票中文簡稱與上市／上櫃查表。對照檔由 scripts/build_stock_names.py 產生，只讀不寫。"""
import json
from functools import lru_cache
from pathlib import Path

_FILE = Path(__file__).resolve().parent / "stock_names.json"
_OTC_FILE = _FILE.with_name("otc_codes.json")


@lru_cache(maxsize=1)
def _table() -> dict:
    try:
        return json.loads(_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


@lru_cache(maxsize=1)
def _otc() -> frozenset:
    try:
        return frozenset(json.loads(_OTC_FILE.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        return frozenset()


def _bare(code: str) -> str:
    c = (code or "").strip().upper()
    for suf in (".TWO", ".TW"):
        if c.endswith(suf):
            return c[: -len(suf)]
    return c


def zh_name(code: str, fallback: str = "") -> str:
    """代號（可帶 .TW／.TWO）→ 中文簡稱；查不到回 fallback"""
    return _table().get(_bare(code)) or fallback or code


def is_otc(code: str) -> bool:
    """是否為上櫃（yfinance 要用 .TWO）；清單外的一律當上市"""
    return _bare(code) in _otc()
