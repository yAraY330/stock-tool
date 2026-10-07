# yAraY 的台股溝

個人持倉追蹤工具。Streamlit + yfinance，資料存在本機 JSON 或 Google Sheets。部署在 Streamlit Community Cloud，**從 `main` 自動部署：push 就等於上線**。

**這是給一位股市新手自用的工具，不是通用產品。** 持股以 ETF（市值型與高股息）加金融股為主，**配息是報酬的重要組成**。計算與呈現以「ETF ＋ 配息型持股」為預設情境。

## 目錄結構

```
stock-tool/
├── CLAUDE.md
├── SETUP.md            # Google Sheets 設定說明（新增頁沒有 secrets 時會引導使用者看）
├── requirements.txt
├── portfolio.json      # 本機模式資料檔（雲端模式改用 Google Sheets）
├── app.py              # Streamlit 主程式：底部導覽 + 六個頁面
├── setup_sheets.py     # 產生 secrets／把本機資料灌進 Sheet（--migrate）
├── 啟動台股工具.bat     # 使用者雙擊啟動用，不要動
├── scripts/
│   └── update_snapshot.py  # 排程寫每日快照回 Sheet
└── modules/
    ├── ui.py           # 純顯示用 HTML/SVG/CSS 產生器（全域樣式、走勢線、odometer、色帶、月曆），不碰資料讀寫
    ├── data.py         # 單檔股票詳細資料（yfinance）
    ├── market.py       # 批次行情、漲跌幅、K 線、快照行情
    ├── snapshot.py     # 組每日快照 payload（純函式）
    ├── evaluator.py    # 指標解讀（附新手說明）
    ├── portfolio.py    # 持倉/觀察/最愛/賣出/配息/快照的讀寫（JSON 或 Sheets 雙模式）
    ├── knowledge.py    # 補知識內容
    └── recommender.py  # 已停用（新手推薦功能於 8925dbb 移除），待使用者決定刪檔或標註
```

## 六個頁面（底部導覽）

1. **持倉** —— 今日損益（含今日走勢線、最大貢獻／拖累）、總覽（價差損益與含息報酬並存）、群組化持倉列（5 日迷你走勢，點開看 K 線、基本面、多筆明細、編輯／配息／賣出／刪除）、已賣出、日報快照、帳號管理
2. **速覽** —— 今日焦點、近 6 週每日損益月曆（推算值）、個股走勢卡片（當日／週／月）
3. **新增** —— 手動新增（即時預覽加入後的持倉分配與 40% 集中度）、CSV 匯入匯出
4. **觀察** —— 觀察清單、目標買入價
5. **評估** —— 單檔查詢、52 週位置、一年走勢、指標解讀
6. **知識** —— 靜態教學章節

頁面頂部有自動提醒：買入點（觀察標的跌到目標價）、停利／停損、集中度（單檔超過總市值 40%）。

## 視覺設計規範（2026-10 黑底改版）

- **去 AI 化**：不用 emoji 當 icon、不用漸層／光暈／卡片陰影、不用無限閃爍的動畫。設計稿在私人 Design 畫布（F 分散版）。檢查工具：`npx impeccable detect <html>`。
- 色彩一律走 `app.py` 頂端的 `C` 字典：底 `#070707`、字 `#ECE9E3`、次要字 `#8F8B85`、分隔線 `#222120`。**台股慣例：紅 `#E5675C`＝漲、綠 `#4FB386`＝跌**。
- 字體 Noto Sans TC；大數字用細字重（300）。
- 動畫只用 CSS、只在元素第一次出現時播放，並尊重 `prefers-reduced-motion`。
- 導覽是 `st.radio(key="sidebar_nav")` 用 CSS 固定在底部；跳頁請設 `st.session_state.sidebar_nav`。不要改成網址連結（整頁重載會清掉登入狀態）。

## 資料儲存

`modules/portfolio.py` 偵測 `st.secrets` 是否有 `sheet_id`：有 → Google Sheets；無 → 本機 `portfolio.json`。**兩種模式都要測。** 資料是一份 JSON，存在 Sheet `portfolio` 工作表 cell(1,1)。

頂層鍵：`holdings`、`watchlist`、`favorites`、`sold`、`quick_view_extras`、`snapshot`（另有 stock-opinions 寫的 `opinions`）。讀取端一律用 `.get()` 加預設值。

⚠️ Sheets 寫入是整份 JSON 覆寫，`_load_sheets()` 有 30 秒快取。寫入前必須先 `_load_sheets.clear()` 再讀，讀寫之間不要做耗時運算。

## 外部相依：每日晨報（重要）

這份 Sheet 每天被雲端「台股晨報」讀取（只讀）。日報環境連不到 Yahoo，所以行情由本工具寫進 `snapshot`。

- **不要更改 `holdings`／`watchlist`／`snapshot` 的既有欄位名稱或結構**，改了日報會靜默壞掉。
- 正式 Sheet 是日報真的在讀的資料，測試請用副本或本機 JSON。

## 命名約定

- 呼叫 yfinance 時加 `.TW`（`0050.TW`），存進 JSON 時不加（`"0050"`）
- 函數名英文 snake_case，顯示文字全用繁體中文
- 每個 module 只做一件事，資料拉取與畫面顯示不要混在一起

## 啟動與驗證

```bash
streamlit run app.py
```

改完程式後：`python -c "import ast;ast.parse(open('app.py',encoding='utf-8').read())"`，再實際跑起來點過六個頁面。驗證時用沒有 secrets 的副本（本機 JSON），不要動正式 Sheet。

## 約束

- 會儲存使用者自己的股數、成本、配息、賣出紀錄，但**不碰真實券商帳戶、不下單**。
- **不提供買賣建議**；推薦性質內容附「這不是投資建議」聲明。
- **配息必須貫穿到彙總數字**：價差損益與含息報酬兩個都要顯示，不要互相取代（除息日股價被扣，只看價差會顯示假虧損）。
- **配息一律手動登錄**，不自動抓（yfinance 台股配息不完整）。
- **抓不到的資料填 `null` 或顯示「—」，不要填 0。**
- **ETF 成分股與內扣費用 yfinance 沒有**，需人工維護並標資料日期與來源。
- Streamlit Cloud 上 yfinance 容易被限速：新功能盡量沿用既有、有快取的批次下載。
- 新增或移除模組後，同步更新本檔案的目錄結構。
