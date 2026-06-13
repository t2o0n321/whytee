# 系統架構設計：智慧化 YouTube 頻道自動追蹤與歷史語料分析

> 本文件為設計依據（design of record），整理自研究報告
> `YouTube逐字稿開源專案與n8n.pdf`，描述端到端架構與各元件職責。

## 1. 目標與核心價值

將被動、耗時且易受主觀記憶偏差影響的影音觀看行為，轉變為具備互動性、客觀性與
歷史脈絡記憶的企業級情報探勘系統。系統不只摘要單一影片，而是具備跨時間軸的
「歷程記錄分析」能力，挖掘創作者的主題演進、論述脈絡與潛在自我矛盾。

本架構解決三大瓶頸：

1. **YouTube 反爬蟲與存取限制** — 以住宅代理輪替與禮貌性延遲規避 IP 封鎖。
2. **語音轉文字（STT）成本與檔案大小限制** — 以階層式降級轉錄與音訊分塊處理。
3. **LLM 上下文視窗極限** — 以 Supabase 向量化 + RAG 跨越長度限制。

## 2. 元件總覽

```
YouTube ──(WebSub / Data API)──> n8n（總指揮 / 編排引擎）
                                   │
        ┌──────────────┬──────────┼─────────────┬───────────────┐
        ▼              ▼          ▼             ▼               ▼
  逐字稿微服務     OpenRouter   Supabase      Telegram      Wait/Loop
 （本專案主程式）（LLM 路由）（pgvector）   Bot API        （限速）
```

| 元件 | 角色 | 本專案實作位置 |
| --- | --- | --- |
| 逐字稿微服務 | 階層式降級轉錄（字幕 → 本地 Whisper），對外暴露 REST | `transcription-service/`（**主程式**） |
| n8n | 流程編排、排程、狀態管理、限速控制 | `n8n/workflows/*.json`（可匯入骨架） |
| OpenRouter | LLM 統一存取閘道，動態模型路由 + Embedding | n8n 節點憑證 + `.env.example` |
| Supabase | PostgreSQL 關聯表 + pgvector 向量庫（RAG） | `supabase/schema.sql` |
| Telegram | 結果推播 + 雙向 Agentic RAG 對話介面 | `n8n/workflows/03-*.json` |

## 3. 逐字稿微服務（主程式）

採用 lifesized/youtube-transcriber 的「階層式降級轉錄」策略：

1. **`captions`（第一層）** — `youtube-transcript-api` 取得官方／自動字幕，
   支援語言優先順序陣列與自動翻譯後備。輕量、免下載音訊。
2. **`whisper_local`（第二層）** — 無字幕或 `force_audio=true` 時，以 `yt-dlp`
   下載最佳音訊、`ffmpeg` 切割為 ≤15 分鐘區塊（規避 25MB／API 限制），再以
   `faster-whisper` 本地轉錄並依時間偏移拼接。

> **為何預設 faster-whisper**：PDF 提及的 MLX 僅限 Apple Silicon、雲端 Whisper
> 需付費金鑰；`faster-whisper` 可跨平台於 CPU/GPU 執行，無需密鑰即可驗證骨架。
> 第二層後端以相同 `transcribe_chunks` 介面實作，可透過 `TRANSCRIBER_STT_BACKEND`
> 在 `local`（faster-whisper）與 `cloud`（OpenAI 相容端點，如 Groq/OpenRouter）間
> 切換；MLX 等仍列為後續工作。詳見 `docs/api.md`。

詳細 REST 契約見 [`docs/api.md`](./api.md)。

## 4. OpenRouter 介接與動態路由

- 全面以 OpenRouter 作為 LLM 統一閘道，相容 OpenAI API 規格。
- **任務分級**：逐字稿清理／關鍵字萃取等粗粒度任務路由至低成本／免費模型
  （`OPENROUTER_MODEL_FAST`）；跨年份歷史統整與 GEO 報告生成則切換至高階模型
  （`OPENROUTER_MODEL_DEEP`）。
- **多語系最佳化**：依資料屬性動態切換最擅長該語系的模型。
- n8n 1.78+ 可用原生 OpenRouter 節點；舊版則以「OpenAI Chat Model」節點將
  Base URL 覆寫為 `https://openrouter.ai/api/v1`。

## 5. Supabase 向量化與 RAG

- 底層 PostgreSQL + `pgvector`，關聯資料與向量統一管理。
- 結構見 [`supabase/schema.sql`](../supabase/schema.sql)：`channels`、`videos`、
  `transcripts`、`embeddings(vector(1536))`、`chat_history`，並提供
  `match_documents` 餘弦相似度檢索函式供 n8n Supabase Vector Store 節點使用。
- 三種運作模式：Insert Documents（知識寫入）、Retrieve Documents（語意檢索）、
  Retrieve as Tool（AI 代理自主查閱）。

## 6. 三個 n8n 工作流

詳見 [`docs/workflows.md`](./workflows.md)。摘要：

1. **歷史語料回溯與向量化** — 批次回補頻道歷史影片並建立向量知識庫。
2. **即時監控 + GEO 深度分析** — WebSub 事件驅動，結合 RAG 進行跨時間脈絡分析。
3. **格式化與推播** — 將 GEO JSON 渲染為 Telegram MarkdownV2 並推播。

## 7. 安全與部署

見 [`docs/security.md`](./security.md)：API 金鑰代理模式、n8n Credentials 集中
管理、Telegram 白名單授權、Webshare 住宅代理與禮貌性限速。
