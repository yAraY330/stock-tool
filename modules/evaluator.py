METRIC_EXPLANATIONS = {
    "pe_ratio": {
        "label": "本益比（P/E）",
        "explain": lambda v: (
            f"本益比 {v:.1f} 倍。"
            + ("偏低，股價相對盈利便宜，但要確認公司基本面是否健康。" if v < 15 else
               "合理區間。" if v < 25 else
               "偏高，市場對未來成長有高預期，波動風險較大。")
            if v is not None else "無資料（可能是虧損股或 ETF）"
        ),
        "beginner_tip": "本益比 = 股價 ÷ 每股盈利。數字越小代表越「便宜」，但太低也可能是公司有問題。台股合理區間大約 15-25 倍。",
    },
    "dividend_yield": {
        "label": "股息殖利率",
        "explain": lambda v: (
            f"殖利率 {v*100:.2f}%。"
            + ("目前無配息或配息極低。" if v == 0 else
               "偏低，公司傾向把盈利再投資而非配息。" if v < 0.02 else
               "正常水準。" if v < 0.05 else
               "殖利率高，適合領息族，但要確認配息是否穩定。")
            if v is not None else "無配息紀錄"
        ),
        "beginner_tip": "殖利率 = 每股股息 ÷ 股價。台股平均殖利率約 3-4%，高於定存利率（約 1.5%）。",
    },
    "beta": {
        "label": "Beta 值（波動係數）",
        "explain": lambda v: (
            f"Beta {v:.2f}。"
            + ("比大盤穩定，適合保守投資人。" if v < 0.8 else
               "和大盤波動相近。" if v < 1.2 else
               "比大盤更波動，漲時漲更多，跌時跌更深。")
            if v is not None else "無資料"
        ),
        "beginner_tip": "Beta = 1 代表和大盤一起漲跌。大於 1 代表波動更劇烈，小於 1 代表相對穩定。",
    },
    "profit_margins": {
        "label": "淨利率",
        "explain": lambda v: (
            f"淨利率 {v*100:.1f}%。"
            + ("目前損益平衡或微利。" if v == 0 else
               "偏低，獲利能力有限。" if v < 0.05 else
               "正常。" if v < 0.15 else
               "偏高，公司有較強的獲利能力或競爭護城河。")
            if v is not None else "無資料（ETF 無此指標）"
        ),
        "beginner_tip": "每賺100元營收，能留下多少利潤。越高代表公司賺錢能力越強。ETF 沒有這個指標。",
    },
    "revenue_growth": {
        "label": "營收成長率（YoY）",
        "explain": lambda v: (
            f"年增 {v*100:.1f}%。"
            + ("營收在衰退，需進一步了解原因。" if v < 0 else
               "營收穩定成長。" if v < 0.15 else
               "高速成長，但注意能否維持。")
            if v is not None else "無資料（ETF 無此指標）"
        ),
        "beginner_tip": "和去年同期相比，公司的收入是增加還是減少。持續成長通常是好信號。ETF 沒有這個指標。",
    },
}


# 評估頁刻度條用：兩個門檻（與上面 explain 的分界一致）、刻度範圍、三段判讀、顯示格式
METRIC_SCALES = {
    "pe_ratio":       {"cut": (15, 25), "scale": (0, 40), "words": ("偏低", "合理", "偏高"),
                       "fmt": lambda v: f"{v:.1f} 倍", "ends": ("0", "15 ｜ 25", "40")},
    "dividend_yield": {"cut": (0.02, 0.05), "scale": (0, 0.08), "words": ("偏低", "正常", "高"),
                       "fmt": lambda v: f"{v*100:.2f}%", "ends": ("0%", "2% ｜ 5%", "8%")},
    "beta":           {"cut": (0.8, 1.2), "scale": (0, 2), "words": ("比大盤穩", "和大盤相近", "比大盤波動大"),
                       "fmt": lambda v: f"{v:.2f}", "ends": ("0", "0.8 ｜ 1.2", "2")},
    "profit_margins": {"cut": (0.05, 0.15), "scale": (0, 0.5), "words": ("偏低", "正常", "偏高"),
                       "fmt": lambda v: f"{v*100:.1f}%", "ends": ("0%", "5% ｜ 15%", "50%")},
    "revenue_growth": {"cut": (0, 0.15), "scale": (-0.2, 0.5), "words": ("衰退", "穩定成長", "高速成長"),
                       "fmt": lambda v: f"{v*100:+.1f}%", "ends": ("-20%", "0 ｜ 15%", "50%")},
}


def evaluate(info: dict) -> list:
    results = []
    for key, meta in METRIC_EXPLANATIONS.items():
        value = info.get(key)
        item = {
            "label": meta["label"],
            "value": value,
            "explanation": meta["explain"](value),
            "beginner_tip": meta["beginner_tip"],
            "display": None, "verdict": None, "pos": None, "zones": None, "ends": None,
        }
        sc = METRIC_SCALES.get(key)
        if sc and value is not None:
            lo, hi = sc["scale"]
            pct = lambda x: max(0.0, min(100.0, (x - lo) / (hi - lo) * 100))
            c1, c2 = sc["cut"]
            item.update({
                "display": sc["fmt"](value),
                "verdict": sc["words"][0] if value < c1 else sc["words"][1] if value < c2 else sc["words"][2],
                "pos": pct(value), "zones": (pct(c1), pct(c2)), "ends": sc["ends"],
            })
        results.append(item)
    return results


def price_position(info: dict) -> dict:
    price = info.get("price")
    high = info.get("52w_high")
    low = info.get("52w_low")
    if not all([price, high, low]):
        return {}
    position = (price - low) / (high - low) * 100
    return {
        "price": price,
        "high": high,
        "low": low,
        "position_pct": position,
        "label": (
            "接近52週低點，可能是低買機會，但要確認原因" if position < 30 else
            "在52週中間區間" if position < 70 else
            "接近52週高點，注意追高風險"
        ),
    }
