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
