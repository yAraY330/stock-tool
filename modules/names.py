"""股票中文簡稱查表。對照檔由 scripts/build_stock_names.py 產生，只讀不寫。"""
import json
from functools import lru_cache
from pathlib import Path

_FILE = Path(__file__).resolve().parent / "stock_names.json"


@lru_cache(maxsize=1)
def _table() -> dict:
    try:
        return json.loads(_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def zh_name(code: str, fallback: str = "") -> str:
    """代號（可帶 .TW／.TWO）→ 中文簡稱；查不到回 fallback"""
    c = (code or "").strip().upper()
    for suf in (".TWO", ".TW"):
        if c.endswith(suf):
            c = c[: -len(suf)]
            break
    return _table().get(c) or fallback or code
