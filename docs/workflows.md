# n8n 工作流規格

三個工作流的設計說明。可匯入骨架位於 [`n8n/workflows/`](../n8n/workflows/)。
匯入後需在 n8n 中設定對應的 Credentials（YouTube、OpenRouter、Supabase、
Telegram），骨架中以 `TODO` 與節點 notes 標示。

## 工作流一：頻道歷史語料庫回溯（Historical Corpus Initialization）

檔案：`01-historical-backfill.json` ｜ 一次性／定期批次任務。

| 步驟 | 節點 | 說明 |
| --- | --- | --- |
| 1 | Manual Trigger | 手動觸發回溯。 |
| 2 | YouTube Data API | 以 `playlistItems` 分頁（`nextPageToken`）拉取頻道所有影片 ID 與 metadata。 |
| 3 | Loop Over Items | 分批處理，避免觸發反爬蟲。 |
| 4 | 逐字稿微服務 | `POST /transcribe` 取得逐字稿。 |
| 5 | Wait 60s | 禮貌性延遲（對應 YTScribe 預設 60 秒冷卻）。 |
| 6 | Supabase Vector Store（Insert） | 文本分塊 → OpenRouter Embedding → 連同 metadata 寫入 pgvector。 |

## 工作流二：即時監控 + GEO 深度分析（Real-time Update & Synthesis）

檔案：`02-realtime-geo-analysis.json` ｜ 事件驅動。

| 步驟 | 節點 | 說明 |
| --- | --- | --- |
| 1 | WebSub Webhook | 透過 PubSubHubbub 訂閱頻道 RSS；新片發布時 YouTube 主動推送 XML。 |
| 2 | 逐字稿微服務 | 取得新影片逐字稿。 |
| 3 | OpenRouter（fast） | 以輕量模型萃取核心關鍵字與實體。 |
| 4 | Supabase（Retrieve） | 以關鍵字為查詢向量，餘弦相似度檢索歷史語料 top-K。 |
| 5 | OpenRouter（deep） | 強制 GEO 框架，回傳嚴格 JSON。 |
| 6 | Supabase（Insert） | 新影片向量滾動寫入，持續更新知識庫。 |
| 7 | Execute Workflow 03 | 交付推播子流程。 |

### GEO 結構化分析框架

LLM 必須以嚴格 JSON 回傳：

- `goal`（目標）：本片試圖探討的核心議題。
- `execution`（執行）：具體論證步驟、實作細節或佐證數據。
- `outcome`（結果與洞察）：結論及其產業意涵。
- `historical_evolution`（歷程演進）：與檢索出的歷史語料比對，指出傳承、演進或矛盾。

## 工作流三：格式化與推播（Data Formatting & Delivery）

檔案：`03-format-and-deliver.json` ｜ 由工作流二呼叫。

| 步驟 | 節點 | 說明 |
| --- | --- | --- |
| 1 | Execute Workflow Trigger | 接收工作流二傳入的 GEO JSON。 |
| 2 | Code（Render MarkdownV2） | 渲染富文本並**跳脫 MarkdownV2 特殊字元**，避免 `400 Bad Request: can't parse entities`。 |
| 3 | Telegram Send Message | 推播摘要 + Inline Keyboard（展開逐字稿／查詢歷史）。 |

## 雙向對話（Agentic RAG，待擴充）

以 Telegram Trigger 監聽使用者訊息，先經白名單授權，再以 PostgreSQL Chat
Memory 維持上下文、Supabase RAG 檢索歷史切片，最後由 OpenRouter 高階模型綜合
推理並回覆。骨架未含此流程，列為後續工作（見 README 的「未涵蓋範圍」）。
