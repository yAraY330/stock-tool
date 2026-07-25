"""組裝每日快照 payload（供台股晨報日報讀取）。

純運算，不碰網路與 Streamlit，可離線單元測試。
欄位定義見 HANDOFF.md 第三節：型別一律 float/int，抓不到填 None（不填 0）。
"""
from __future__ import annotations


def _num(x):
    """只接受數字，其餘（含 None）回 None。"""
    return x if isinstance(x, (int, float)) and not isinstance(x, bool) else None


def build_snapshot(holdings: list, quotes: dict, market_date, now) -> dict:
    """
    holdings:    portfolio 的 holdings list（code 不含後綴）
    quotes:      {code: {price, prev_close, today_pct, ...}}（get_snapshot_data 的 quotes）
    market_date: "YYYY-MM-DD" 或 None
    now:         datetime（含時區）→ updated_at

    positions 以「code|account」為單位，同 code+account 多筆合併（加權均價、股數/配息加總）。
    totals 只加總「有現價」的部位，讓含息報酬率的分子分母一致；無現價的部位仍列於
    positions（欄位填 None），但不進 totals。
    """
    # ── 先依 code+account 合併 ──
    merged: dict[str, dict] = {}
    for h in holdings:
        code = h.get("code", "")
        account = h.get("account", "預設帳號")
        key = f"{code}|{account}"
        m = merged.setdefault(key, {"code": code, "account": account,
                                    "shares": 0.0, "cost": 0.0, "div": 0.0})
        shares = h.get("shares", 0) or 0
        m["shares"] += shares
        m["cost"]   += shares * (h.get("avg_cost", 0) or 0)
        m["div"]    += h.get("dividends", 0) or 0

    positions: dict[str, dict] = {}
    tot_mv = tot_cost = tot_price_pnl = tot_div = 0.0
    any_priced = False

    for key, m in merged.items():
        shares = m["shares"]
        cost   = m["cost"]
        div    = round(m["div"], 2)
        avg_cost = round(cost / shares, 4) if shares else None
        price = _num(quotes.get(m["code"], {}).get("price"))

        if price is not None:
            mv               = round(price * shares, 2)
            price_pnl        = round(mv - cost, 2)
            price_pnl_pct    = round(price_pnl / cost * 100, 2) if cost else None
            total_return     = round(price_pnl + div, 2)
            total_return_pct = round(total_return / cost * 100, 2) if cost else None
            any_priced = True
            tot_mv        += mv
            tot_cost      += cost
            tot_price_pnl += price_pnl
            tot_div       += div
        else:
            mv = price_pnl = price_pnl_pct = total_return = total_return_pct = None

        positions[key] = {
            "code": m["code"], "account": m["account"],
            "shares": shares, "avg_cost": avg_cost,
            "market_value": mv,
            "price_pnl": price_pnl, "price_pnl_pct": price_pnl_pct,
            "dividends_received": div,
            "total_return": total_return, "total_return_pct": total_return_pct,
        }

    tot_return = round(tot_price_pnl + tot_div, 2) if any_priced else None
    totals = {
        "market_value":       round(tot_mv, 2) if any_priced else None,
        "cost":               round(tot_cost, 2) if any_priced else None,
        "price_pnl":          round(tot_price_pnl, 2) if any_priced else None,
        "dividends_received": round(tot_div, 2) if any_priced else None,
        "total_return":       tot_return,
        "total_return_pct":   (round(tot_return / tot_cost * 100, 2)
                               if (tot_return is not None and tot_cost) else None),
    }

    # ── status：全部有價=ok，部分缺=partial ──
    all_codes    = {h.get("code", "") for h in holdings}
    priced_codes = {c for c in all_codes if _num(quotes.get(c, {}).get("price")) is not None}
    status = "ok" if (not all_codes or priced_codes == all_codes) else "partial"

    return {
        "updated_at":  now.isoformat(),
        "market_date": market_date,
        "status":      status,
        "quotes":      quotes,
        "positions":   positions,
        "totals":      totals,
    }
