"""純顯示用的 HTML／SVG／CSS 產生器。只吃已算好的數字，不拉資料、不讀寫持倉。"""
import datetime
from html import escape

# ── 色票（與 app.py 的 C 相同；這裡是單一來源，app.py 從這裡匯入）──
C = {
    "up":       "#E5675C",  # 漲（紅）
    "down":     "#4FB386",  # 跌（綠）
    "bg":       "#070707",  # 背景
    "raised":   "#0E0E0D",  # 稍亮的區塊底
    "open":     "#111110",  # 展開中的列
    "text":     "#ECE9E3",  # 主要文字
    "text_sub": "#8F8B85",  # 次要文字
    "faint":    "#8A867F",  # 更淡的說明字（仍過 4.5:1）
    "line":     "#222120",  # 分隔線
    "edge":     "#3A3936",  # 按鈕／輸入框邊
}
_GREYS = ["#ECE9E3", "#B9B5AE", "#8F8B85", "#66625D", "#4E4B47", "#3B3936"]


def signed(v: float, digits: int = 0) -> str:
    """+1,234 / -1,234 / 0"""
    if v is None:
        return "—"
    s = f"{abs(v):,.{digits}f}"
    return ("+" if v > 0 else "-" if v < 0 else "") + s


def tone(v: float | None) -> str:
    if v is None or v == 0:
        return C["text_sub"]
    return C["up"] if v > 0 else C["down"]


# ── 底部導覽 icon（線條，CSS mask 用）──────────────────────────
_ICONS = [
    "<path d='M4 20V10M10 20V4M16 20v-7M22 20H2'/>",
    "<rect x='3' y='3' width='7' height='7'/><rect x='14' y='3' width='7' height='7'/>"
    "<rect x='3' y='14' width='7' height='7'/><rect x='14' y='14' width='7' height='7'/>",
    "<path d='M12 5v14M5 12h14'/>",
    "<path d='M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z'/><circle cx='12' cy='12' r='3'/>",
    "<circle cx='11' cy='11' r='7'/><path d='M20 20l-4-4'/>",
    "<path d='M4 4h7a3 3 0 0 1 3 3v13a2 2 0 0 0-2-2H4z'/><path d='M20 4h-4a2 2 0 0 0-2 2v14a2 2 0 0 1 2-2h4z'/>",
]


def _icon_url(inner: str) -> str:
    svg = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' "
           "stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'>"
           + inner + "</svg>")
    return 'url("data:image/svg+xml;utf8,' + svg.replace("#", "%23").replace('"', "'") + '")'


def global_css() -> str:
    icons = "\n".join(
        f".st-key-sidebar_nav [role=\"radiogroup\"] > label:nth-of-type({i + 1})::before"
        f"{{-webkit-mask-image:{_icon_url(s)};mask-image:{_icon_url(s)}}}"
        for i, s in enumerate(_ICONS)
    )
    css = """<style>
@import url("https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@300;400;500;700&display=swap");
html, body, .stApp, [data-testid="stAppViewContainer"] { background:#070707 !important; }
.stApp, .stApp p, .stApp label, .stApp input, .stApp textarea, .stApp button, .stApp li {
  font-family:'Noto Sans TC', sans-serif !important;
}
.stApp { color:#ECE9E3; }
.n { font-variant-numeric:tabular-nums; }

/* 版面：手機優先，桌機置中；底部留給導覽列 */
[data-testid="stMainBlockContainer"], .main .block-container {
  max-width:720px; padding:1.2rem 1.25rem 7rem !important;
}
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"],
[data-testid="stDecoration"], [data-testid="stToolbar"] { display:none !important; }
[data-testid="stHeader"] { background:transparent !important; height:0 !important; }

/* 標題 */
.stApp h1 { font-size:1.75rem !important; font-weight:300 !important; color:#ECE9E3 !important; letter-spacing:0; }
.stApp h2, .stApp h3 { font-size:0.85rem !important; font-weight:400 !important; color:#8F8B85 !important; }
hr { border-color:#222120 !important; margin:1.25rem 0 !important; }
[data-testid="stCaptionContainer"], .stApp small { color:#8F8B85 !important; }

/* 按鈕：膠囊 */
.stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] button {
  min-height:44px; border-radius:22px !important; border:1px solid #3A3936 !important;
  background:transparent !important; color:#ECE9E3 !important; font-weight:400 !important;
  box-shadow:none !important; transition:transform 120ms ease-out, background-color 160ms ease-out !important;
}
.stButton > button:hover, .stDownloadButton > button:hover { background:#1A1918 !important; }
.stButton > button:active { transform:scale(0.97); }
.stButton > button[kind="primary"], [data-testid="stFormSubmitButton"] button[kind="primaryFormSubmit"] {
  background:#ECE9E3 !important; color:#070707 !important; border-color:#ECE9E3 !important; font-weight:500 !important;
}
.stButton > button[kind="primary"] p { color:#070707 !important; }
button:focus-visible { outline:2px solid #ECE9E3 !important; outline-offset:2px; }

/* 輸入框：深底淺字 */
[data-baseweb="input"], [data-baseweb="base-input"], [data-baseweb="textarea"],
[data-baseweb="select"] > div:first-child {
  background:#0E0E0D !important; border-color:#3A3936 !important; border-radius:6px !important;
}
.stApp input, .stApp textarea { background:#0E0E0D !important; color:#ECE9E3 !important; caret-color:#ECE9E3 !important; font-size:16px !important; }
.stApp input::placeholder, .stApp textarea::placeholder { color:#6E6A64 !important; }
[data-baseweb="select"] [class*="singleValue"], [data-baseweb="select"] span { color:#ECE9E3 !important; }
[data-baseweb="popover"] ul, [data-baseweb="popover"] [role="option"] { background:#121211 !important; color:#ECE9E3 !important; }
[data-baseweb="popover"] [role="option"]:hover { background:#1E1D1C !important; }
[data-testid="stNumberInputContainer"] button { background:#0E0E0D !important; color:#8F8B85 !important; border:none !important; }
[data-testid="stFileUploaderDropzone"] { background:#0E0E0D !important; border:1px dashed #3A3936 !important; }
[data-testid="InputInstructions"] { display:none !important; }

/* 內頁的 radio（帳號、排序、區間）：膠囊。只針對選項，不碰 widget 自己的標籤 */
[data-testid="stRadio"] [role="radiogroup"] { gap:6px !important; flex-wrap:wrap; }
[data-testid="stRadio"] [role="radiogroup"] > label {
  margin:0 !important; padding:6px 14px !important; min-height:36px; border:1px solid #3A3936;
  border-radius:18px; align-items:center; cursor:pointer;
}
[data-testid="stRadio"] [role="radiogroup"] > label > div:first-child { display:none !important; }
[data-testid="stRadio"] [role="radiogroup"] > label:has(input:checked) { background:#ECE9E3; border-color:#ECE9E3; }
[data-testid="stRadio"] [role="radiogroup"] > label:has(input:checked) p { color:#070707 !important; }
[data-testid="stRadio"] [role="radiogroup"] > label p { font-size:13px !important; color:#ECE9E3; }
[data-testid="stRadio"] [data-testid="stWidgetLabel"] p { color:#8F8B85 !important; font-size:12px !important; }
/* 底部導覽列 */
.st-key-sidebar_nav {
  position:fixed !important; left:0; right:0; bottom:0; z-index:1000; width:100% !important;
  background:#070707; border-top:1px solid #222120; padding-bottom:env(safe-area-inset-bottom);
}
.st-key-sidebar_nav [data-testid="stRadio"], .st-key-sidebar_nav [data-testid="stRadio"] > div { width:100% !important; }
.st-key-sidebar_nav [data-testid="stWidgetLabel"] { display:none !important; }
.st-key-sidebar_nav [role="radiogroup"] {
  display:flex !important; flex-wrap:nowrap !important; gap:0 !important; width:100%; max-width:720px; margin:0 auto;
}
.st-key-sidebar_nav [role="radiogroup"] > label {
  flex:1 1 0; position:relative; display:flex !important; flex-direction:column; justify-content:center; align-items:center;
  gap:3px; min-height:58px; padding:6px 0 !important; border:none; border-radius:0; background:transparent !important;
  color:#8F8B85;
}
.st-key-sidebar_nav [role="radiogroup"] > label::before {
  content:""; width:22px; height:22px; background:currentColor;
  -webkit-mask-repeat:no-repeat; mask-repeat:no-repeat; -webkit-mask-size:contain; mask-size:contain;
}
.st-key-sidebar_nav [role="radiogroup"] > label p { font-size:11px !important; color:inherit !important; }
.st-key-sidebar_nav [role="radiogroup"] > label:has(input:checked) { color:#ECE9E3; background:transparent !important; }
.st-key-sidebar_nav [role="radiogroup"] > label:has(input:checked) p { font-weight:700 !important; color:#ECE9E3 !important; }
.st-key-sidebar_nav [role="radiogroup"] > label:has(input:checked)::after {
  content:""; position:absolute; top:-1px; left:28%; right:28%; height:2px; background:#ECE9E3;
  animation:navline 260ms ease-out both;
}
@keyframes navline { from { transform:scaleX(0); } }
""" + icons + """
/* 指標、expander、表格 */
[data-testid="stMetric"], [data-testid="metric-container"] { background:transparent; border:none; padding:0 !important; }
[data-testid="stMetricLabel"] p { color:#8F8B85 !important; font-size:12px !important; }
[data-testid="stMetricValue"] { font-weight:300 !important; font-size:1.5rem !important; }
details { border:none !important; border-top:1px solid #222120 !important; border-radius:0 !important; background:transparent !important; }
details > summary { padding:0.9rem 0 !important; }
details > summary p { font-size:15px !important; }
[data-testid="stAlert"], [data-testid="stAlertContainer"] { background:#0E0E0D !important; border:1px solid #3A3936 !important; border-radius:6px !important; color:#ECE9E3 !important; }
[data-testid="stAlert"] p, [data-testid="stAlertContainer"] p { color:#ECE9E3 !important; }
[data-testid="stAlertContentError"] p { color:#E5675C !important; }
.stProgress > div > div > div { background:#2A2927 !important; }
.stProgress > div > div > div > div { background:#ECE9E3 !important; }

/* 持股列：整列可點（透明按鈕蓋在卡片上） */
[class*="st-key-hrow_"] { position:relative; gap:0 !important; }
[class*="st-key-hrowbtn_"] { position:absolute !important; inset:0; z-index:2; margin:0 !important; }
[class*="st-key-hrowbtn_"] button { width:100%; height:100%; opacity:0; border:none !important; }

/* 動畫 ── 只在元素第一次出現時播放 */
.odo { display:flex; align-items:flex-start; height:1em; overflow:hidden; font-weight:300; line-height:1; letter-spacing:-0.03em; }
.odo .col { display:block; height:1em; overflow:hidden; }
.odo .strip { display:flex; flex-direction:column; transform:translateY(calc((10 + var(--d)) * -1em));
  animation:roll 1300ms calc(var(--i) * 90ms + 150ms) cubic-bezier(0.16,0.84,0.24,1) both; }
@keyframes roll { from { transform:translateY(0); } }
.iline { stroke-dasharray:1; animation:dash 1400ms 900ms cubic-bezier(0.3,0.6,0.2,1) both; }
.iarea { animation:fade 900ms 1700ms ease-out both; }
.spark { stroke-dasharray:1; animation:dash 700ms calc(var(--i) * 80ms + 600ms) ease-out both; }
@keyframes dash { from { stroke-dashoffset:1; } }
@keyframes fade { from { opacity:0; } }
.alloc { display:flex; gap:2px; height:10px; transform-origin:0 50%; animation:draw 1000ms 300ms cubic-bezier(0.22,0.8,0.3,1) both; }
@keyframes draw { from { transform:scaleX(0); } }
.flash { animation:flash 1800ms 1900ms ease-out both; }
@keyframes flash { 12% { background:#16291F; } }
.cal .cell { animation:fade 500ms calc(var(--i) * 18ms) ease-out both; }
@media (prefers-reduced-motion: reduce) {
  .stApp *, .stApp *::before, .stApp *::after { animation:none !important; transition:none !important; }
}
</style>"""
    # st.markdown 遇到空行就會結束 HTML 區塊，CSS 會被當成文字印出來，所以去掉空行
    return "\n".join(line for line in css.split("\n") if line.strip())


# ── 首屏：odometer 今日損益 ─────────────────────────────────────
def odometer(value: float, size_px: int = 76) -> str:
    color = tone(value)
    txt = f"{abs(value):,.0f}"
    sign = "+" if value > 0 else "-" if value < 0 else ""
    strip = "".join(f"<span>{d % 10}</span>" for d in range(20))
    parts, i = [], 0
    for ch in txt:
        if ch.isdigit():
            parts.append(f'<span class="col" style="--d:{ch};--i:{i}"><span class="strip">{strip}</span></span>')
            i += 1
        else:
            parts.append(f"<span>{ch}</span>")
    return (f'<div class="odo n" style="font-size:{size_px}px;color:{color}" '
            f'aria-label="{sign}{txt} 元"><span>{sign}</span>{"".join(parts)}</div>')


def _path(values: list, w: float, h: float, pad: float, lo=None, hi=None) -> str:
    lo = min(values) if lo is None else lo
    hi = max(values) if hi is None else hi
    rng = (hi - lo) or 1
    step = w / max(len(values) - 1, 1)
    return " ".join(
        f"{'M' if i == 0 else 'L'}{i * step:.1f} {(hi - v) / rng * (h - 2 * pad) + pad:.1f}"
        for i, v in enumerate(values)
    )


def intraday_chart(deltas: list, start_label: str, end_label: str) -> str:
    """今日持倉總值相對昨收的走勢；deltas 是每個時間點的損益。"""
    if len(deltas) < 2:
        return ""
    w, h, pad = 350, 84, 4
    lo, hi = min(min(deltas), 0), max(max(deltas), 0)
    span = (hi - lo) or 1
    lo, hi = lo - span * 0.08, hi + span * 0.08
    d = _path(deltas, w, h, pad, lo, hi)
    zero_y = (hi - 0) / (hi - lo) * (h - 2 * pad) + pad
    last_y = (hi - deltas[-1]) / (hi - lo) * (h - 2 * pad) + pad
    clr = tone(deltas[-1])
    fill = "rgba(229,103,92,0.12)" if deltas[-1] >= 0 else "rgba(79,179,134,0.12)"
    return f"""<figure style="margin:20px 0 0" aria-label="今日持倉總值走勢">
<svg width="100%" height="{h}" viewBox="0 0 {w} {h}" preserveAspectRatio="none" style="display:block;overflow:visible">
<line x1="0" x2="{w}" y1="{zero_y:.1f}" y2="{zero_y:.1f}" stroke="#3A3936" stroke-width="1" stroke-dasharray="2 4" vector-effect="non-scaling-stroke"></line>
<path class="iarea" d="{d} L{w} {zero_y:.1f} L0 {zero_y:.1f} Z" fill="{fill}"></path>
<path class="iline" d="{d}" pathLength="1" fill="none" stroke="{clr}" stroke-width="1.6" stroke-linejoin="round" vector-effect="non-scaling-stroke"></path>
<circle cx="{w}" cy="{last_y:.1f}" r="3" fill="{clr}"></circle>
</svg>
<figcaption style="display:flex;justify-content:space-between;margin-top:6px;font-size:11px;color:#8A867F"><span>{escape(start_label)}</span><span>虛線＝昨收</span><span>{escape(end_label)}</span></figcaption>
</figure>"""


def spark(values: list, idx: int = 0, w: int = 64, h: int = 24) -> str:
    vals = [float(v) for v in values if v == v]  # 去掉 NaN
    if len(vals) < 2:
        return f'<svg width="{w}" height="{h}" aria-hidden="true"></svg>'
    clr = tone(vals[-1] - vals[0])
    return (f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" aria-hidden="true" style="overflow:visible;flex:none">'
            f'<path class="spark" d="{_path(vals, w, h, 2)}" pathLength="1" fill="none" stroke="{clr}" '
            f'stroke-width="1.4" stroke-linejoin="round" stroke-linecap="round" style="--i:{idx}"></path></svg>')


def stat_grid(items: list) -> str:
    """items: [(標籤, 主數字, 主數字顏色, 小字 or None, 小字顏色)]，兩欄。"""
    cells = []
    for i, (label, val, clr, sub, sub_clr) in enumerate(items):
        border = "border-left:1px solid #222120;padding-left:14px;" if i % 2 else ""
        sub_html = f'<div class="n" style="font-size:12px;color:{sub_clr}">{sub}</div>' if sub else ""
        cells.append(f'<div style="padding:12px 10px 4px 0;{border}"><div style="font-size:12px;color:#8F8B85">{label}</div>'
                     f'<div class="n" style="font-size:18px;color:{clr}">{val}</div>{sub_html}</div>')
    return ('<div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));margin-top:22px;'
            'border-top:1px solid #222120">' + "".join(cells) + "</div>")


def alerts(items: list) -> str:
    """items: [(kind, 標題, 說明)]；kind ∈ loss / profit / buy / concentration。"""
    if not items:
        return ""
    icon = {
        "loss":   ("#4FB386", "<path d='M12 3v14M6 11l6 6 6-6'/><path d='M4 21h16'/>"),
        "profit": ("#E5675C", "<path d='M12 21V7M6 13l6-6 6 6'/><path d='M4 3h16'/>"),
        "buy":    ("#ECE9E3", "<circle cx='12' cy='12' r='9'/><path d='M8 12h8M12 8v8'/>"),
        "concentration": ("#ECE9E3", "<circle cx='12' cy='12' r='9'/><path d='M12 3v9l6 4'/>"),
    }
    rows = []
    for n, (kind, title, body) in enumerate(items):
        clr, paths = icon.get(kind, icon["concentration"])
        cls = ' class="flash"' if kind == "loss" else ""
        sep = "border-top:1px solid #1A1918;" if n else ""
        rows.append(
            f'<div{cls} style="display:flex;gap:12px;align-items:flex-start;padding:14px 8px;margin:0 -8px;{sep}">'
            f'<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="{clr}" stroke-width="1.6" '
            f'style="flex:none;margin-top:3px" aria-hidden="true">{paths}</svg>'
            f'<div style="font-size:14px;line-height:1.5"><span style="font-weight:500">{escape(title)}</span><br>'
            f'<span style="color:#8F8B85">{escape(body)}</span></div></div>')
    return ('<section aria-label="提醒" style="margin:8px 0 4px;border-top:1px solid #222120;'
            'border-bottom:1px solid #222120">' + "".join(rows) + "</section>")


def holding_row(name: str, sub: str, spark_svg: str, value: str, pnl: str, pnl_clr: str, star: bool) -> str:
    st_ = '<span style="color:#8F8B85;margin-right:4px">★</span>' if star else ""
    return f"""<div style="display:grid;grid-template-columns:minmax(0,1fr) 64px 104px;column-gap:12px;align-items:center;padding:14px 0;min-height:44px">
<div style="min-width:0"><div style="font-size:17px;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{st_}{escape(name)}</div>
<div class="n" style="font-size:12px;color:#8F8B85;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{escape(sub)}</div></div>
{spark_svg}
<div style="text-align:right"><div class="n" style="font-size:16px">{value}</div><div class="n" style="font-size:12px;color:{pnl_clr}">{pnl}</div></div>
</div>"""


def alloc_strip(items: list, legend: bool = True, mark: str | None = None) -> str:
    """items: [(code, 名稱, 市值)]。超過 40% 的那段標紅；mark＝要框起來的代碼。"""
    total = sum(v for _, _, v in items) or 1
    segs, rows, g = [], [], 0
    for code, name, v in items:
        pct = v / total * 100
        over = pct > 40
        clr = C["up"] if over else _GREYS[g % len(_GREYS)]
        if not over:
            g += 1
        ring = "outline:1px solid #ECE9E3;outline-offset:1px;" if mark and code == mark else ""
        segs.append(f'<span style="flex:{pct:.3f} 1 0;background:{clr};border-radius:1px;{ring}"></span>')
        txt = C["up"] if over else C["text"]
        rows.append(f'<div style="display:flex;align-items:center;gap:8px"><span style="width:8px;height:8px;'
                    f'border-radius:1px;background:{clr};flex:none"></span><span style="flex:1;color:#B9B5AE;'
                    f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{escape(name)}</span>'
                    f'<span class="n" style="color:{txt}">{pct:.1f}%</span></div>')
    aria = "，".join(f"{n} {v / total * 100:.1f}%" for _, n, v in items)
    html = f'<div class="alloc" role="img" aria-label="{escape(aria)}">{"".join(segs)}</div>'
    if legend:
        html += ('<div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));column-gap:16px;'
                 'row-gap:6px;margin-top:12px;font-size:13px">' + "".join(rows) + "</div>")
    return html


def pnl_calendar(daily: dict, today: datetime.date, weeks: int = 6) -> str:
    """daily: {date: 當日損益}。近 N 週、週一到週五；沒有資料的日子（休市／未到）留空。"""
    monday = today - datetime.timedelta(days=today.weekday())
    start = monday - datetime.timedelta(weeks=weeks - 1)
    vals = [abs(v) for v in daily.values()]
    top = max(vals) if vals else 1
    cells = []
    for w in range(weeks):
        for d in range(5):
            day = start + datetime.timedelta(weeks=w, days=d)
            v = daily.get(day)
            i = w * 5 + d
            if v is None:
                cells.append(f'<div class="cell" style="--i:{i};background:#121211;color:#4E4B47">'
                             f'<span>{day.day}</span></div>')
                continue
            lvl = abs(v) / top if top else 0
            a = 0.95 if lvl > 0.75 else 0.65 if lvl > 0.45 else 0.4 if lvl > 0.2 else 0.22
            bg = f"rgba(229,103,92,{a})" if v >= 0 else f"rgba(79,179,134,{a})"
            short = f"{v / 1000:+.1f}k" if abs(v) >= 1000 else f"{v:+.0f}"
            ring = "outline:1px solid #ECE9E3;" if day == today else ""
            cells.append(f'<div class="cell" style="--i:{i};background:{bg};{ring}" title="{day:%m/%d} {signed(v)} 元">'
                         f'<span>{day.day}</span><span class="n" style="color:#ECE9E3">{short}</span></div>')
    head = "".join(f"<span>{x}</span>" for x in "一二三四五")
    return (
        '<style>.cal .cell{aspect-ratio:1/1;min-height:44px;border-radius:3px;padding:4px 5px;box-sizing:border-box;'
        'display:flex;flex-direction:column;justify-content:space-between;font-size:11px;color:rgba(236,233,227,0.85)}</style>'
        '<div style="display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:4px;font-size:11px;'
        f'color:#8A867F;text-align:center">{head}</div>'
        '<div class="cal" style="display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:4px;margin-top:6px">'
        + "".join(cells) + "</div>")


def stock_card(name: str, code: str, price: str, today: str, today_clr: str, spark_svg: str, foot: str = "") -> str:
    return f"""<div style="background:#0B0B0A;padding:14px 12px 12px;min-width:0">
<div style="display:flex;justify-content:space-between;align-items:baseline;gap:6px"><span style="font-size:15px;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{escape(name)}</span><span class="n" style="font-size:11px;color:#8A867F">{escape(code)}</span></div>
<div style="display:flex;justify-content:space-between;align-items:baseline;margin-top:2px"><span class="n" style="font-size:18px;font-weight:300">{price}</span><span class="n" style="font-size:13px;color:{today_clr}">{today}</span></div>
<div style="margin-top:8px">{spark_svg}</div>{foot}</div>"""


# ── 登入頁：號子跑馬燈 ────────────────────────────────────────
AMBER = "#F2B33D"


def _ticker_row(items: list, dur: int, reverse: bool, idx: int) -> str:
    """一排跑馬燈；items: [(名稱, 價格字串, 漲跌%)]。內容放兩份做無縫循環。"""
    cells = []
    for name, price, pct in items:
        if pct is None:
            chg = '<span style="color:#8F8B85">—</span>'
        else:
            clr = "#FF5A4E" if pct >= 0 else "#3FD07F"
            chg = f'<span style="color:{clr}">{"▲" if pct >= 0 else "▼"}{abs(pct):.2f}%</span>'
        cells.append(f'<span class="tk-cell"><span style="color:{AMBER}">{escape(name)}</span>'
                     f'<span>{escape(price)}</span>{chg}</span>')
    body = "".join(cells)
    side = " r" if reverse else ""
    direction = "reverse" if reverse else "normal"
    return (f'<div class="tk-row{side}" style="--i:{idx}"><div class="tk-tape" style="animation-duration:{dur}s;'
            f'animation-direction:{direction}">{body}{body}</div></div>')


def ticker_block(quotes: list, which: str) -> str:
    """which＝top／bottom：各兩排，方向交錯。quotes 為空就回傳空字串（不畫跑馬燈）。"""
    if not quotes:
        return ""
    n = len(quotes)

    def rot(k: int) -> list:
        return (quotes[k % n:] + quotes[:k % n])[:5]

    if which == "top":
        rows = _ticker_row(rot(0), 22, False, 0) + _ticker_row(rot(4), 26, True, 1)
    else:
        rows = _ticker_row(rot(2), 30, False, 3) + _ticker_row(rot(6), 24, True, 4)
    return f'<div class="tk tk-{which}" aria-hidden="true">{rows}</div>'


def login_brand(date_label: str) -> str:
    return (f'<div class="tk-brand"><div class="tk-logo">台股溝</div>'
            f'<div class="tk-date n">{escape(date_label)}</div></div><div class="tk-groove"><i></i></div>')


_TICKER_CSS = """
@import url("https://fonts.googleapis.com/css2?family=DotGothic16&display=swap");
.tk { position:fixed; left:0; right:0; z-index:5; background:#0B0A09; font-family:'DotGothic16', monospace; font-size:17px; color:#ECE9E3; }
.tk-top { top:28px; border-bottom:1px solid #1C1B19; }
.tk-bottom { bottom:28px; border-bottom:1px solid #1C1B19; }
.tk-row { overflow:hidden; white-space:nowrap; border-top:1px solid #1C1B19; padding:10px 0; }
.tk-tape { display:inline-flex; animation-name:tape; animation-timing-function:linear; animation-iteration-count:infinite; }
.tk-cell { display:inline-flex; gap:10px; padding-right:28px; }
@keyframes tape { to { transform:translateX(-50%); } }
.tk-brand { text-align:center; font-family:'DotGothic16', monospace; }
.tk-logo { font-size:72px; line-height:1; color:#F2B33D; letter-spacing:0.14em; padding-left:0.14em; }
.tk-date { margin-top:12px; font-size:13px; color:#8F8B85; letter-spacing:0.2em; }
.tk-groove { position:relative; height:1px; background:#2A2927; margin:34px 0 0; }
.tk-groove i { position:absolute; inset:0; background:#F2B33D; transform:scaleX(0); transform-origin:0 50%; }
"""


def _compact(css: str) -> str:
    # st.markdown 遇到空行就會結束 HTML 區塊，所以去掉空行
    return "\n".join(line for line in css.split("\n") if line.strip())


def login_css(err_count: int) -> str:
    """登入頁版面；err_count 每加一，表單就重晃一次（動畫名稱交替才會重播）。"""
    shake = ""
    if err_count:
        name = "shake-a" if err_count % 2 else "shake-b"
        shake = f'.st-key-login_box [data-testid="stForm"]{{animation:{name} 320ms ease-out}}'
    css = "<style>" + _TICKER_CSS + """
[data-testid="stMainBlockContainer"], .main .block-container { padding-bottom:180px !important; }
.st-key-login_box { max-width:340px; margin:0 auto; }
.st-key-login_box [data-testid="stForm"] { border:none; padding:0; }
.st-key-login_box [data-baseweb="input"], .st-key-login_box [data-baseweb="base-input"] {
  background:transparent !important; border:none !important; border-bottom:1px solid #3A3936 !important; border-radius:0 !important;
}
.st-key-login_box [data-baseweb="input"]:focus-within { border-bottom-color:#ECE9E3 !important; }
.st-key-login_box input { background:transparent !important; font-size:22px !important; letter-spacing:0.2em; padding-left:0 !important; }
.st-key-login_box input::placeholder { letter-spacing:0.04em; font-size:17px !important; color:#46433F !important; }
.st-key-login_box [data-baseweb="input"] button { background:transparent !important; }
.st-key-login_box [data-testid="InputInstructions"] { display:none !important; }
.st-key-login_box [data-testid="stFormSubmitButton"] button {
  min-height:50px !important; background:#F2B33D !important; border-color:#F2B33D !important; color:#070707 !important; border-radius:25px !important;
}
.st-key-login_box [data-testid="stFormSubmitButton"] button p { color:#070707 !important; font-weight:500; }
.st-key-login_box [data-testid="stFormSubmitButton"] button:hover { background:#FFC55A !important; }
@keyframes shake-a { 20%{transform:translateX(-6px)} 40%{transform:translateX(5px)} 60%{transform:translateX(-3px)} 80%{transform:translateX(2px)} }
@keyframes shake-b { 20%{transform:translateX(-6px)} 40%{transform:translateX(5px)} 60%{transform:translateX(-3px)} 80%{transform:translateX(2px)} }
""" + shake + """
@media (prefers-reduced-motion: reduce) { .tk-tape, .st-key-login_box * { animation:none !important; } }
</style>"""
    return _compact(css)


def entry_overlay(quotes: list, date_label: str) -> str:
    """登入成功後播一次的「離站」：溝線畫亮 → 每排跑馬燈沿原方向衝出 → 招牌往左走 → 整層消失。"""
    css = "<style>" + _TICKER_CSS + """
.entry { position:fixed; inset:0; z-index:2000; background:#070707; pointer-events:none;
  animation:entry-gone 300ms 1250ms ease-out both; }
.entry .tk { z-index:auto; }
.entry .tk-mid { position:absolute; left:0; right:0; top:calc(max(150px, 22vh) + 1.2rem); }
.entry .tk-groove { max-width:340px; margin:34px auto 0; }
.entry .tk-groove i { animation:entry-draw 480ms 60ms cubic-bezier(0.65,0,0.35,1) both; }
.entry .tk-row { animation:rush-l 560ms calc(380ms + var(--i) * 70ms) cubic-bezier(0.55,0,0.9,0.35) both; }
.entry .tk-row.r { animation-name:rush-r; }
.entry .tk-brand { animation:rush-l 520ms 640ms cubic-bezier(0.55,0,0.9,0.35) both; }
@keyframes entry-draw { to { transform:scaleX(1); } }
@keyframes rush-l { to { transform:translateX(-115%); } }
@keyframes rush-r { to { transform:translateX(115%); } }
@keyframes entry-gone { to { opacity:0; visibility:hidden; } }
@media (prefers-reduced-motion: reduce) { .entry { display:none; } }
</style>"""
    return (_compact(css) + '<div class="entry" aria-hidden="true">' + ticker_block(quotes, "top")
            + f'<div class="tk-mid">{login_brand(date_label)}</div>' + ticker_block(quotes, "bottom") + "</div>")


# ── 觀察頁 ───────────────────────────────────────────────────
def target_hit_card(name: str, code: str, price: str, target: str, note: str) -> str:
    why = f"你寫的理由：「{escape(note)}」" if note else "你沒有寫觀察理由。"
    return (f'<section aria-label="已到目標價" style="margin:4px 0 12px;border:1px solid #6E6A64;background:#0E0E0D;padding:16px 16px 14px">'
            f'<div style="display:flex;justify-content:space-between;align-items:baseline;font-size:13px;color:#8F8B85">'
            f'<span>已到目標價</span><span class="n" style="font-size:12px;color:#8A867F">現價 ≤ 目標</span></div>'
            f'<div style="display:flex;justify-content:space-between;align-items:baseline;margin-top:8px">'
            f'<span style="font-size:20px;font-weight:500">{escape(name)} <span class="n" style="font-size:13px;font-weight:400;color:#8A867F">{escape(code)}</span></span>'
            f'<span class="n" style="font-size:30px;font-weight:300">{price}</span></div>'
            f'<div class="n" style="font-size:13px;color:#8F8B85">目標 {target}・{why}</div>'
            f'<p style="margin:12px 0 0;font-size:14px;color:#B9B5AE">到價不等於該買。先確認當初的理由現在還成立，再決定。</p></section>')


def watch_row(name: str, code: str, note: str, price: str, w1: float | None, m1: float | None,
              target: float, dist: float | None) -> str:
    def pct(v):
        return ("—", C["text_sub"]) if v is None else (f"{v:+.1f}%", tone(v))

    w1s, w1c = pct(w1)
    m1s, m1c = pct(m1)
    if target > 0 and dist is not None:
        near = dist <= 5
        pos = max(0.0, min(dist, 25)) / 25 * 100
        dot = "#ECE9E3" if near else "#8F8B85"
        txt = "已到價" if dist <= 0 else f"還差 {dist:.1f}%"
        bar = (f'<span class="n" style="font-size:11px;color:#8A867F;min-width:70px">目標 {target:,.2f}</span>'
               f'<span style="position:relative;height:12px"><span style="position:absolute;left:0;right:0;top:5px;height:2px;background:#2A2927"></span>'
               f'<span style="position:absolute;left:0;top:0;width:1px;height:12px;background:#ECE9E3"></span>'
               f'<span style="position:absolute;top:2px;width:8px;height:8px;border-radius:4px;margin-left:-4px;left:{pos:.1f}%;background:{dot}"></span></span>'
               f'<span class="n" style="font-size:12px;min-width:64px;text-align:right;color:{dot if near else "#8A867F"}">{txt}</span>')
    elif target > 0:
        bar = f'<span class="n" style="font-size:11px;color:#8A867F">目標 {target:,.2f}（暫無報價）</span><span></span><span></span>'
    else:
        bar = '<span style="font-size:11px;color:#8A867F">未設目標價</span><span></span><span></span>'
    note_html = escape(note) if note else "&nbsp;"
    return (f'<div style="display:grid;grid-template-columns:minmax(0,1fr) auto;column-gap:12px;padding:14px 0 12px">'
            f'<div style="min-width:0"><div style="font-size:16px;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">'
            f'{escape(name)} <span class="n" style="font-size:12px;font-weight:400;color:#8A867F">{escape(code)}</span></div>'
            f'<div style="font-size:12px;color:#8A867F;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{note_html}</div></div>'
            f'<div style="text-align:right"><div class="n" style="font-size:17px;font-weight:300">{price}</div>'
            f'<div class="n" style="font-size:12px"><span style="color:{w1c}">{w1s}</span>　<span style="color:{m1c}">{m1s}</span></div></div>'
            f'<div style="grid-column:1 / -1;display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:10px;align-items:center;margin-top:10px">{bar}</div>'
            f'</div>')


def target_chart(closes: list, target: float) -> str:
    vals = [float(v) for v in closes if v == v]
    if len(vals) < 2:
        return ""
    ext = [target] if target > 0 else []
    lo, hi = min(vals + ext), max(vals + ext)
    w, h, pad = 350, 64, 4
    d = _path(vals, w, h, pad, lo, hi)
    tline = ""
    if target > 0:
        ty = (hi - target) / ((hi - lo) or 1) * (h - 2 * pad) + pad
        tline = (f'<line x1="0" x2="{w}" y1="{ty:.1f}" y2="{ty:.1f}" stroke="#6E6A64" stroke-width="1" '
                 f'stroke-dasharray="3 4" vector-effect="non-scaling-stroke"></line>')
    clr = tone(vals[-1] - vals[0])
    note = f"虛線＝目標價 {target:,.2f}" if target > 0 else "設定目標價後，這裡會畫出目標線"
    return (f'<figure style="margin:4px 0 8px" aria-label="近 1 個月走勢">'
            f'<div style="display:flex;justify-content:space-between;font-size:12px;color:#8A867F"><span>近 1 個月</span>'
            f'<span class="n">{min(vals):,.2f} – {max(vals):,.2f}</span></div>'
            f'<svg width="100%" height="{h}" viewBox="0 0 {w} {h}" preserveAspectRatio="none" style="display:block;margin-top:6px">{tline}'
            f'<path d="{d}" fill="none" stroke="{clr}" stroke-width="1.5" stroke-linejoin="round" '
            f'vector-effect="non-scaling-stroke"></path></svg>'
            f'<figcaption style="font-size:11px;color:#8A867F;margin-top:2px">{note}</figcaption></figure>')


# ── 評估頁 ───────────────────────────────────────────────────
def _scale_bar(pos_pct: float, zones: tuple, ends: tuple, h: int = 16) -> str:
    z1, z2 = zones
    ends_html = "".join(f"<span>{escape(e)}</span>" for e in ends)
    return (f'<div style="position:relative;height:{h}px">'
            f'<div style="position:absolute;left:0;right:0;top:{h // 2 - 2}px;display:flex;gap:2px;height:4px">'
            f'<span style="flex:{z1:.2f} 1 0;background:#2A2927"></span><span style="flex:{z2 - z1:.2f} 1 0;background:#3A3936"></span>'
            f'<span style="flex:{100 - z2:.2f} 1 0;background:#2A2927"></span></div>'
            f'<span style="position:absolute;top:0;left:{pos_pct:.1f}%;width:2px;height:{h}px;margin-left:-1px;background:#ECE9E3"></span></div>'
            f'<div class="n" style="display:flex;justify-content:space-between;font-size:11px;color:#8A867F;margin-top:4px">{ends_html}</div>')


def range_bar(low: float, high: float, price: float, label: str) -> str:
    pos = max(0.0, min(100.0, (price - low) / ((high - low) or 1) * 100))
    bar = _scale_bar(pos, (30, 70), (f"低 {low:,.2f}", "低檔｜中間｜高檔", f"高 {high:,.2f}"), 24)
    return (f'<section aria-label="52 週區間" style="margin:18px 0 8px">'
            f'<div style="display:flex;justify-content:space-between;font-size:13px;color:#8F8B85"><span>52 週區間</span>'
            f'<span class="n" style="color:#ECE9E3">位在 {pos:.0f}%</span></div>'
            f'<div style="margin-top:10px">{bar}</div>'
            f'<p style="margin:10px 0 0;font-size:14px;color:#B9B5AE">{escape(label)}</p></section>')


def line_chart(values: list, start_label: str, end_label: str, aria: str) -> str:
    vals = [float(v) for v in values if v == v]
    if len(vals) < 2:
        return ""
    w, h = 350, 140
    grid = "".join(f'<line x1="0" x2="{w}" y1="{y}" y2="{y}" stroke="#1A1918" vector-effect="non-scaling-stroke"></line>'
                   for y in (35, 70, 105))
    return (f'<figure style="margin:8px 0 0" aria-label="{escape(aria)}">'
            f'<svg width="100%" height="{h}" viewBox="0 0 {w} {h}" preserveAspectRatio="none" style="display:block">{grid}'
            f'<path d="{_path(vals, w, h, 6)}" fill="none" stroke="#ECE9E3" stroke-width="1.5" '
            f'stroke-linejoin="round" vector-effect="non-scaling-stroke"></path></svg>'
            f'<figcaption class="n" style="display:flex;justify-content:space-between;font-size:11px;color:#8A867F;margin-top:4px">'
            f'<span>{escape(start_label)}</span><span>{escape(end_label)}</span></figcaption></figure>')


def metric_rows(items: list) -> str:
    """items: evaluator.evaluate() 的結果。用原生 <details> 展開，不觸發 Streamlit 重跑。"""
    rows = []
    for m in items:
        has = m.get("value") is not None and m.get("pos") is not None
        val = escape(m["display"]) if has else "無資料"
        bar = f'<div style="margin-top:10px">{_scale_bar(m["pos"], m["zones"], m["ends"])}</div>' if has else ""
        vclr = "#ECE9E3" if has else "#6E6A64"
        rows.append(
            f'<details class="mrow" style="border-top:1px solid #222120">'
            f'<summary style="list-style:none;cursor:pointer;padding:14px 0;display:block">'
            f'<div style="display:flex;justify-content:space-between;align-items:baseline;gap:12px"><span style="font-size:15px">{escape(m["label"])}</span>'
            f'<span><span class="n" style="font-size:22px;font-weight:300;color:{vclr}">{val}</span>'
            f'<span style="font-size:13px;color:#B9B5AE;margin-left:8px">{escape(m.get("verdict") or "")}</span></span></div>{bar}</summary>'
            f'<div style="padding:0 0 16px"><p style="margin:0;font-size:14px;color:#ECE9E3">{escape(m["explanation"])}</p>'
            f'<p style="margin:8px 0 0;font-size:13px;color:#8F8B85">{escape(m["beginner_tip"])}</p></div></details>')
    return ('<style>.mrow summary::-webkit-details-marker{display:none}</style>'
            '<section aria-label="基本面指標" style="border-bottom:1px solid #222120">' + "".join(rows) + "</section>")


# ── 知識頁 ───────────────────────────────────────────────────
def read_progress(n: int, total: int) -> str:
    pct = n / total * 100 if total else 0
    return (f'<div style="height:2px;background:#1A1918;margin:-6px 0 18px"><div style="height:2px;width:{pct:.1f}%;'
            f'background:#ECE9E3"></div></div>')
