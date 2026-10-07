# Vercel 課堂部署操作

目前已完成 Vercel 部署配置與本機驗證，尚未上傳至你的 Vercel 帳號，也沒有已發布網址。

## 最短路徑：直接用 CLI，無需先建 GitHub

1. 安裝 [Node.js LTS](https://nodejs.org/)，若已有 Node 與 npm 可跳過。
2. 在 [Vercel](https://vercel.com/) 註冊或登入個人帳號。
3. 開啟 macOS 終端機，輸入：

```sh
cd "/Users/huifan/Library/Mobile Documents/com~apple~CloudDocs/Study/北科大/大三上/人工智慧跨域金融之應用/Lecture/2026.10.5/credit-review-poc"
npx vercel@latest login
npx vercel@latest
```

若 npx 詢問是否安裝 vercel，輸入 y。登入時依終端機顯示的瀏覽器／驗證指示完成登入，不需把 token 貼給任何人。

首次部署問答的文字可能隨 CLI 版本變動，依含義選擇：

| 問題 | 選擇 |
|---|---|
| 是否部署目前資料夾 | Y |
| 部署到哪個 scope | 自己的個人帳號／課程指定帳號 |
| 連結現有專案 | N（第一次部署） |
| 專案名稱 | credit-review-poc，或另一個小寫英文名稱 |
| 程式在哪個目錄 | ./ |
| 修改偵測到的設定 | N（使用已提供配置） |

本專案沒有 Next.js 或 React 編譯。Framework 使用 Other；Build Command 不需設定；Output Directory 使用 public。Vercel JSON 已提供設定。不要把 public 設成 Root Directory，因為專案根目錄也必須包含 api、engine.py、server.py、requirements.txt 與 samples/financials.csv。

部署成功時終端機會顯示預覽網址。若預覽網址要求登入，先用同一 Vercel 帳號開啟即可。要提供同學使用的正式網址，再執行：

```sh
npx vercel@latest --prod
```

這會發布目前資料夾內容到正式部署。完成後使用命令顯示的 Production／Alias 網址；名稱可能帶有後綴，不要猜測網址。

## 驗收

- 網址首頁可開啟。
- 點「載入示範案例」：營收年減 35%、負債比率 76.25%、風險 6 項。
- 使用小於 3 MB 的範本 CSV、XLSX、文字 PDF 上傳分析。
- 人工負債比率輸入 0.7，更新比對後顯示「有差異」。
- 下載覆審 HTML 報告並確認數值與來源。
- 開啟實際網址後加 `/api/health`，應回傳 ok=true、deployment=vercel。

## 已準備的部署結構

```
credit-review-poc/
  vercel.json
  .python-version
  requirements.txt
  engine.py
  server.py
  api/
    analyze.py
    report.py
    health.py
  public/
    index.html
    app.js
    style.css
    sample.csv
  samples/
    financials.csv
```

public 是網頁靜態資源；api 是 Vercel Python Functions。server.py 保留本機啟動方式，在雲端只匯入其處理函式，不啟動常駐伺服器。資料不寫入伺服器檔案系統。

雲端展示版上傳限制為 3 MiB，Base64 後約 4 MiB，以留在 Vercel Function 的 4.5 MB payload 上限內。雲端停用本機 Ollama，分析與報告採用規則摘要，無需設定模型 API 金鑰。金額資料只應使用合成或去識別化範例。

修改 static 後，在本機先執行 `python3 sync_public.py` 更新雲端前端，再執行部署。純 API／engine.py 修改無需同步 public。CLI 首次會建立 .vercel 專案連結，後續在相同資料夾執行 `npx vercel@latest --prod` 即可更新。

## 如果老師要求 GitHub → Vercel 網頁操作

1. 在 GitHub 建立 repository，把 credit-review-poc 資料夾內的檔案推到 repository 根目錄；保留 .gitignore，勿上傳 .env、.venv 或 .vercel。
2. 在 Vercel Dashboard 點 Add New → Project，連結 GitHub 並 Import 該 repository。
3. Framework Preset 選 Other、Root Directory 為 repository 根目錄，使用 vercel.json 的 public 輸出配置，按 Deploy。
4. 等待部署完成，開啟產生的網址並執行上述驗收。

## 常見問題

| 情況 | 處理 |
|---|---|
| npm／npx command not found | 安裝 Node.js LTS，重新開啟終端機 |
| 404 首頁 | 確認 Root Directory 是完整專案根目錄，public/index.html 存在 |
| 財報分析 404 | 確認 api/ 下三個 .py 檔也已部署，沒有只部署 public |
| 500／模組不存在 | 查看 Vercel Function Logs；確認 requirements.txt、engine.py 與 server.py 已包含 |
| 413 Payload too large | 檔案改用 3 MB 以下；本版本未實作大檔直傳儲存服務 |
| 本機 Ollama 無法連線 | 雲端不使用本機模型；保持規則模式 |
| 沒有看到同學可用網址 | 確認已執行 --prod；如果專案另設保護，檢查該專案的存取設定 |

## 驗證範圍

新增 5 項 Vercel handler 測試：HTTPS 同源、跨來源拒絕、3 MB 限制、報告與健康檢查，以及雲端 LLM 回退。與既有 12 項合計 17 項。這些是本機入口驗證，尚未做 Vercel 雲端 build／實際部署驗證。

官方參考：[Python runtime](https://vercel.com/docs/functions/runtimes/python)、[CLI 部署](https://vercel.com/docs/cli/deploying-from-cli)、[vercel.json](https://vercel.com/docs/project-configuration/vercel-json)、[Function 限制](https://vercel.com/docs/functions/limitations)。
