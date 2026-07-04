# stock-tool

台股新手工具：新手推薦（風險×目標×類別三維篩選）+ 近期熱門 + 股票評估 + 補知識。使用 Streamlit + yfinance。

## 目錄結構

```
stock-tool/
├── CLAUDE.md
├── SETUP.md            # 朋友部署自己版本的逐步指南
├── requirements.txt
├── app.py              # Streamlit 主程式，入口
├── modules/
│   ├── data.py         # 資料拉取（yfinance）
│   ├── recommender.py  # 新手推薦邏輯
│   ├── evaluator.py    # 股票評估邏輯
│   ├── market.py       # 批次拉報價／K線，含 .TWO fallback
│   ├── portfolio.py    # 持倉讀寫（本機 JSON 或 Google Sheets）
│   └── knowledge.py    # 補知識內容（靜態教學資料）
└── .env.example        # 環境變數範本（若日後加 API key）
```

## 命名約定

- 台股代碼統一加 `.TW` 後綴（yfinance 格式），例：`0050.TW`
- 函數名英文 snake_case，顯示文字全用繁體中文
- 每個 module 只做一件事，不要把資料拉取和顯示混在一起

## 啟動指令

```bash
streamlit run app.py
```

## 驗證指令

改完程式後跑：
```bash
python -c "import app" 2>&1 | head -20
streamlit run app.py --server.headless true &
```

## 約束

- 不存使用者的交易數據、不碰真實帳戶
- 所有推薦都附上「這不是投資建議」聲明
- 新增模組前先在此更新目錄結構
- 股票數據來源：yfinance（免費、免 API key）
