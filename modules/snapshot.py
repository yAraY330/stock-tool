"""組裝每日快照 payload（供台股晨報日報讀取）。

純運算，不碰網路與 Streamlit，可離線單元測試。
欄位定義見 HANDOFF.md 第三節：型別一律 float/int，抓不到填 None（不填 0）。
"""
from __future__ import annotations


def _num(x):
    """只接受數字，其餘（含 None）回 None。"""
    return x if isinstance(x, (int, float)) and not isinstance(x, bool) else None


def build_snapshot(holdings: list, quotes: dict, market_date, now,
                   stale_codes=(), suspect_codes=()) -> dict:
    """
    holdings:      portfolio 的 holdings list（code 不含後綴）
    quotes:        {code: {price, prev_close, today_pct, ...}}（get_snapshot_data 的 quotes）
    market_date:   "YYYY-MM-DD" 或 None
    now:           datetime（含時區）→ updated_at
    stale_codes:   確定拿到舊資料的 code（該檔最後日期 < market_date）
    suspect_codes: 疑似平盤的 code（price==prev_close 且 today_pct==0）
                   兩者皆為全部 quotes（holdings ∪ watchlist）的偵測結果；additive 欄位，
                   供日報端精準辨識，不改動 status 的三值語意（ok/partial/stale）。

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

    # ── status：全部有價且無過期/疑似=ok，否則 partial ──
    # 維持 ok/partial/stale 三值不擴充；holdings 有缺價、或 holdings 落入
    # stale/suspect（含 ETF 非交易日回吐）都不得標 ok。stale/suspect 清單本身
    # 涵蓋全部 quotes，但只有 holdings 命中才影響 status。
    stale_set    = set(stale_codes)
    suspect_set  = set(suspect_codes)
    all_codes    = {h.get("code", "") for h in holdings}
    priced_codes = {c for c in all_codes if _num(quotes.get(c, {}).get("price")) is not None}
    holdings_flagged = all_codes & (stale_set | suspect_set)
    status = "ok" if (all_codes and priced_codes == all_codes
                      and not holdings_flagged) else "partial"
    if not all_codes:            # 無持股時沿用舊行為（視為 ok）
        status = "ok"

    return {
        "updated_at":      now.isoformat(),
        "last_attempt_at": now.isoformat(),   # 真正寫入 → 與 updated_at 同步
        "skip_reason":     None,              # 真正寫入 → 無跳過原因
        "market_date":     market_date,
        "status":          status,
        "stale_codes":     sorted(stale_set),
        "suspect_codes":   sorted(suspect_set),
        "quotes":          quotes,
        "positions":       positions,
        "totals":          totals,
    }


def decide_write(new_snap: dict, existing: dict | None, now) -> dict:
    """覆寫守門：比較新舊快照，回傳「應寫回 Sheet 的 snapshot」。

    - 真正更新：回 new_snap（已含 last_attempt_at=now、skip_reason=None）。
    - 決定不動：回既有快照的複本，資料原封不動，但把 last_attempt_at 前進到 now、
      記下 skip_reason。這樣「排程有跑但正確地決定不寫」與「排程掛了很多天」在
      Sheet 上就能分辨（前者 last_attempt_at 會持續前進，後者不會）。

    規則（market_date 為 ISO 日期字串，字典序即時間序）：
      - 無既有快照或既有無 market_date → 直接寫 new。
      - new.market_date 為 None            → 不寫，skip_reason=no_market_date。
      - new.market_date <  existing         → 不寫，skip_reason=older_market_date。
      - new.market_date == existing 且「new 髒、existing 乾淨」→ 不寫，
        skip_reason=same_date_dirty_payload（不拿髒的同日快照蓋掉乾淨的）。
      - 其餘（new 較新，或同日但 new 不劣）→ 寫 new。
    髒 = 有 stale_codes 或 suspect_codes。
    """
    if not existing or not existing.get("market_date"):
        return new_snap

    def _clean(s: dict) -> bool:
        return not s.get("stale_codes") and not s.get("suspect_codes")

    new_md = new_snap.get("market_date")
    old_md = existing.get("market_date")

    reason = None
    if not new_md:
        reason = "no_market_date"
    elif new_md < old_md:
        reason = "older_market_date"
    elif new_md == old_md and not _clean(new_snap) and _clean(existing):
        reason = "same_date_dirty_payload"

    if reason is None:
        return new_snap

    patched = dict(existing)
    patched["last_attempt_at"] = now.isoformat()
    patched["skip_reason"] = reason
    return patched
