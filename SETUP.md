# 台股溝 — 個人部署指南

> 跟著這份指南，你可以擁有一份完全屬於自己的台股溝 App，資料獨立、永久保存。
> 預計時間：約 20 分鐘。

---

## 你需要準備

- 一個 **GitHub 帳號**（免費，沒有的話先到 github.com 註冊）
- 一個 **Google 帳號**（用來存資料）
- 電腦瀏覽器

---

## 步驟一：Fork 這個專案

1. 前往 `github.com/yAraY330/stock-tool`
2. 右上角點 **Fork**
3. 選擇你的帳號，按 **Create fork**
4. 等待複製完成（幾秒鐘）

完成後你會有一份自己的專案，網址類似 `github.com/你的帳號/stock-tool`

---

## 步驟二：部署到 Streamlit Cloud

1. 前往 `share.streamlit.io`
2. 用你的 **GitHub 帳號** 登入
3. 點 **Create app**
4. 在「Repository」選你 fork 的 `stock-tool`
5. Branch 選 `main`
6. Main file path 填：`app.py`
7. 按 **Deploy**，等待約 2-3 分鐘

部署完成後，App 已可以開啟使用。

> ⚠️ **重要：** 這個階段的資料存在 Streamlit Cloud 的暫時空間，**App 重新啟動後資料會消失**。
> 請繼續步驟三讓資料永久保存。

---

## 步驟三：建立 Google Sheet（資料永久保存）

### 3-1 新增一個空白試算表

1. 前往 `sheets.google.com`，登入你的 Google 帳號
2. 按左上角 **+（空白）** 新增試算表
3. 隨意命名，例如「我的台股溝資料」
4. 記下瀏覽器網址列中間那一段長字串（Sheet ID）

   ```
   https://docs.google.com/spreadsheets/d/【這裡就是 Sheet ID】/edit
   ```

---

### 3-2 建立 Google 服務帳號

這個步驟讓 App 有權限讀寫你的試算表。

1. 前往 `console.cloud.google.com`，用你的 Google 帳號登入
2. 頁面頂部點 **選取專案** → **新增專案**
3. 專案名稱隨意填（例如「股票溝資料庫」），按 **建立**
4. 建立完成後，確認頂部顯示你的新專案名稱

**開啟 API：**

5. 左側選單點 **API 和服務** → **程式庫**
6. 搜尋 `Google Sheets API`，點進去，按 **啟用**
7. 返回，再搜尋 `Google Drive API`，同樣按 **啟用**

**建立服務帳號：**

8. 左側選單點 **API 和服務** → **憑證**
9. 上方點 **+ 建立憑證** → **服務帳號**
10. 「服務帳號名稱」隨意填（例如 `stock-app`），按 **完成**
11. 在憑證頁面點剛建立的服務帳號 Email（長得像 `stock-app@xxx.iam.gserviceaccount.com`）
12. 切換到 **金鑰** 標籤 → **新增金鑰** → **建立新金鑰** → 選 **JSON** → **建立**
13. 一個 JSON 檔案會自動下載到你的電腦

---

### 3-3 把試算表分享給服務帳號

1. 回到剛才建立的 Google Sheet
2. 右上角點 **共用**
3. 把步驟 3-2 第 11 步的服務帳號 Email 貼上去
4. 權限選 **編輯者**
5. 按 **傳送**（或「不要通知」）

---

## 步驟四：設定 Streamlit Secrets

1. 前往 `share.streamlit.io`，點你的 App
2. 右上角點 **⋮** → **Settings** → **Secrets**
3. 把以下內容貼進去，並填入你自己的值：

```toml
app_password = "你想設定的密碼"
sheet_id = "步驟3-1的Sheet ID"

[gcp_service_account]
type = "service_account"
project_id = "（從 JSON 檔複製）"
private_key_id = "（從 JSON 檔複製）"
private_key = "（從 JSON 檔複製，包含 -----BEGIN...END----- 那整段）"
client_email = "（從 JSON 檔複製）"
client_id = "（從 JSON 檔複製）"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "（從 JSON 檔複製）"
```

**怎麼找 JSON 檔的內容：**
用記事本（Windows）或文字編輯器（Mac）打開步驟 3-2 下載的 JSON 檔，
裡面的每個欄位對應 Secrets 裡 `[gcp_service_account]` 下的欄位。

4. 貼完後按 **Save**
5. App 會自動重新啟動，之後資料就會永久保存在你的 Google Sheet 了

---

## 完成！

開啟你的 App，試著新增一筆持倉，重新整理頁面確認資料還在。

如果遇到問題，可以把錯誤訊息傳給台股溝的作者（yAraY）。

---

## 常見問題

**Q：我可以不設 Google Sheets 嗎？**
可以，但每次 App 重新啟動資料就會消失，只適合測試用。

**Q：app_password 可以不設嗎？**
可以，不設的話 App 不需要密碼就能進入。

**Q：我的資料會跟 yAraY 的混在一起嗎？**
不會。你 fork 的是程式碼，資料完全獨立存在你自己的 Google Sheet。
