# 安裝與部署指南

本文件提供從零到可運作的逐步說明：本機開發、完整 Docker 堆疊、n8n 憑證接線，
以及常見問題排解。設計背景請見 [`architecture.md`](./architecture.md)。

## 0. 先決條件

| 工具 | 用途 | 備註 |
| --- | --- | --- |
| Python 3.10+ | 逐字稿微服務 | `make install` 會建立可編輯安裝。 |
| `ffmpeg` | 音訊下載與分塊（第二層） | 需在 `PATH`；僅做字幕轉錄可省略。 |
| Docker + Compose | 完整本機堆疊 | db + transcriber + n8n。 |
| Make | 常用指令捷徑 | 非必要，指令亦可手動執行。 |

## 1. 設定環境變數

```bash
cp .env.example .env
```

依註解填入金鑰。各區塊對應：

- **PostgreSQL / Supabase**：`POSTGRES_*` 與 `SUPABASE_DB_URL`。
- **YouTube Data API v3**：`YOUTUBE_API_KEY`（頻道影片列舉）。
- **OpenRouter**：`OPENROUTER_API_KEY` 與 fast／deep／embedding 模型名稱。
- **Telegram**：`TELEGRAM_BOT_TOKEN` 與授權白名單 `TELEGRAM_ALLOWED_CHAT_IDS`。
- **逐字稿微服務**：`TRANSCRIBER_*`（見下方 §4）。
- **Webshare 代理（選用）**：`WEBSHARE_PROXY_*`，規避 IP 限速。

> `.env` 已列入 `.gitignore`，切勿提交真實金鑰。

## 2. 本機開發（僅逐字稿微服務）

```bash
make install        # cd transcription-service && pip install -e ".[dev]"
make test           # 單元測試（免網路／金鑰）
make run            # uvicorn，http://localhost:8000
make smoke          # curl /health
```

開啟 <http://localhost:8000/docs> 可瀏覽 OpenAPI 互動文件。
REST 契約細節見 [`api.md`](./api.md)。

## 3. 完整本機堆疊（Docker Compose）

```bash
make up             # docker compose up -d db transcriber n8n
make ps             # 確認三個服務 healthy
make logs           # 追蹤日誌
make down           # 停止
```

啟動內容：

- **db**：`pgvector/pgvector:pg16`，首次啟動自動套用 `supabase/schema.sql`
  （掛載至 `docker-entrypoint-initdb.d`）。
- **transcriber**：本倉建置，透過 `env_file: .env` 讀取所有 `TRANSCRIBER_*` 設定。
- **n8n**：`n8nio/n8n:latest`，以同一個 PostgreSQL 作為後端儲存。

> **重新套用 schema**：`schema.sql` 只在資料卷為空時自動執行。要重置請
> `docker compose down -v` 清除 `db_data` 後再 `make up`，或手動
> `psql "$SUPABASE_DB_URL" -f supabase/schema.sql`。

## 4. 逐字稿微服務設定（`TRANSCRIBER_` 前綴）

| 變數 | 預設 | 說明 |
| --- | --- | --- |
| `TRANSCRIBER_DEFAULT_LANGUAGES` | `["zh-TW","zh-Hant","zh","en"]` | 語言優先順序。 |
| `TRANSCRIBER_STT_BACKEND` | `local` | 第二層後端：`local`／`cloud`／`elevenlabs`／`mlx`。 |
| `TRANSCRIBER_WHISPER_MODEL` | `base` | local 後端模型大小。 |
| `TRANSCRIBER_WHISPER_DEVICE` | `auto` | `auto`／`cpu`／`cuda`。 |
| `TRANSCRIBER_CLOUD_STT_BASE_URL` | Groq | cloud 後端 OpenAI 相容端點。 |
| `TRANSCRIBER_CLOUD_STT_MODEL` | `whisper-large-v3` | cloud 後端模型。 |
| `TRANSCRIBER_CLOUD_STT_API_KEY` | （空） | cloud 後端金鑰；空值時 `/ready` 回 503。 |
| `TRANSCRIBER_ELEVENLABS_API_KEY` | （空） | elevenlabs 後端金鑰。 |
| `TRANSCRIBER_ELEVENLABS_MODEL` | `scribe_v1` | ElevenLabs Scribe 模型。 |
| `TRANSCRIBER_MLX_MODEL` | `whisper-large-v3-mlx` | mlx 後端模型（需 `mlx-whisper`，Apple Silicon）。 |
| `TRANSCRIBER_AUDIO_CHUNK_SECONDS` | `900` | 音訊分塊秒數。 |
| `TRANSCRIBER_WEBSHARE_PROXY_USERNAME` | （空） | 住宅代理帳號。 |
| `TRANSCRIBER_WEBSHARE_PROXY_PASSWORD` | （空） | 住宅代理密碼。 |

切換雲端 STT（免本地算力，需付費金鑰）：

```bash
TRANSCRIBER_STT_BACKEND=cloud
TRANSCRIBER_CLOUD_STT_BASE_URL=https://api.groq.com/openai/v1
TRANSCRIBER_CLOUD_STT_MODEL=whisper-large-v3
TRANSCRIBER_CLOUD_STT_API_KEY=gsk_...
```

以 `curl localhost:8000/ready` 確認後端就緒。

## 5. 匯入 n8n 工作流並接線憑證

1. 開啟 n8n（<http://localhost:5678>），建立管理者帳號。
2. **匯入**：左側選單 → *Workflows* → *Import from File*，逐一匯入
   `n8n/workflows/01-historical-backfill.json`、`02-realtime-geo-analysis.json`、
   `03-format-and-deliver.json`、`04-agentic-rag-chat.json`。
3. **建立 Credentials**（*Credentials* → *Add Credential*）：
   - **YouTube Data API**：HTTP Query Auth 或在節點以 `={{ $env.YOUTUBE_API_KEY }}` 帶入。
   - **OpenRouter**：n8n 1.78+ 用原生 OpenRouter 節點；舊版用「OpenAI」憑證，
     Base URL 覆寫為 `https://openrouter.ai/api/v1`。
   - **Supabase**：Host／Service Role Key，或 Postgres 連線（對應 `SUPABASE_DB_URL`）。
   - **Telegram**：以 `TELEGRAM_BOT_TOKEN` 建立 Telegram API 憑證。
4. 開啟每個工作流，將標示 `TODO`／節點 notes 的位置指派上述憑證。
5. **逐字稿微服務節點**：HTTP Request 指向 `http://transcriber:8000/transcribe`
   （堆疊內服務名）或本機 `http://localhost:8000/transcribe`。
6. **WebSub（工作流二）**：需公開可達的 `N8N_WEBHOOK_URL`（生產環境須外部 HTTPS）。
   本機測試可用通道工具（如反向代理）暫時對外。

各工作流的節點與資料流請見 [`workflows.md`](./workflows.md)。

## 6. 驗證端到端

1. `make smoke` → 服務 `/health` 回 `status: ok`。
2. n8n 手動執行工作流一，挑選一個頻道做小批次回溯，確認 `transcripts` 與
   `embeddings` 表有資料寫入。
3. 對監聽中的頻道發布測試影片（或重送 WebSub），確認工作流二觸發並推播 Telegram。
4. 從白名單內的 Telegram 帳號向 Bot 發問，確認工作流四回覆並引用歷史 `video_id`；
   以非白名單帳號發問應被靜默丟棄。

## 7. 疑難排解

| 症狀 | 可能原因 / 解法 |
| --- | --- |
| `pip install` 後 `ffmpeg not found` | 音訊層需系統 `ffmpeg`；`apt-get install ffmpeg` 或 `brew install ffmpeg`。 |
| `/transcribe` 回 `502` 且訊息含 `410 Gone` | YouTube IP 限速；設定 Webshare 代理並在 n8n 加大 Wait 延遲。 |
| `/ready` 回 `503` | `stt_backend=cloud` 但 `CLOUD_STT_API_KEY` 為空，補上金鑰。 |
| n8n 無法連線資料庫 | 確認 `db` 服務 healthy；`DB_POSTGRESDB_*` 與 `POSTGRES_*` 一致。 |
| `schema.sql` 未生效 | 資料卷非空不會重跑；`docker compose down -v` 後重啟。 |
| Telegram `400 can't parse entities` | MarkdownV2 特殊字元未跳脫；見工作流三的 Code 節點。 |
| 向量檢索結果不佳 | 調整 `embeddings` 的 IVFFlat `lists` 參數以符合語料規模。 |
| 雲端 STT 檔案過大 | 多數端點限 25MB；縮小 `AUDIO_CHUNK_SECONDS`。 |

## 8. 在 Claude Code on the web 開發

倉庫內含 SessionStart hook（`.claude/hooks/session-start.sh`），於遠端 web
session 啟動時自動安裝逐字稿微服務（含 dev 相依與 `ffmpeg`），讓 `pytest`／`ruff`
可直接運作。合併進預設分支後，後續所有 web session 皆會套用。
