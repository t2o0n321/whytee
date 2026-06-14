# 安裝與部署指南（Docker 為主）

本指南的目標：**clone 專案 → 照步驟操作 → 系統就架起來**。
推薦用 Docker Compose 一鍵啟動整套堆疊（資料庫 + 逐字稿微服務 + n8n）。
設計背景見 [`architecture.md`](./architecture.md)；REST 契約見 [`api.md`](./api.md)。

---

## 0. 先決條件

只需要兩樣東西：

| 工具 | 版本 | 取得 |
| --- | --- | --- |
| Docker Engine | 24+ | <https://docs.docker.com/engine/install/> |
| Docker Compose | v2（內建 `docker compose`） | 隨新版 Docker 一併安裝 |

> 不想用 Docker、只想跑逐字稿微服務做開發？見 §7。

另外建議先準備好這些帳號／金鑰（可邊做邊補）：

- **YouTube Data API v3 金鑰**（列出頻道影片）— Google Cloud Console。
- **OpenRouter API 金鑰**（LLM + Embedding）— <https://openrouter.ai>。
- **Telegram Bot Token**（推播 + 對話）— 跟 @BotFather 申請。
- **Webshare 住宅代理帳密**（強烈建議）— 從伺服器 IP 直連 YouTube 幾乎一定被
  `403`／`410` 封鎖，住宅代理是實務上的必備項，見 §6。

---

## 1. 取得程式並建立 `.env`

```bash
git clone https://github.com/t2o0n321/whytee.git
cd whytee
cp .env.example .env
```

用編輯器打開 `.env`，至少填入以下幾項（其餘可先留空，之後再補）：

```dotenv
# 資料庫（自行設定一組強密碼）
POSTGRES_PASSWORD=請改成強密碼

# YouTube / OpenRouter / Telegram
YOUTUBE_API_KEY=...
YOUTUBE_CHANNEL_ID=UCxxxxxxxxxxxxxxxxxx     # 要追蹤的頻道
OPENROUTER_API_KEY=...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_ALLOWED_CHAT_IDS=123456789         # 允許和 Bot 對話的 chat id（逗號分隔）

# 住宅代理（強烈建議，見 §6）
WEBSHARE_PROXY_USERNAME=...
WEBSHARE_PROXY_PASSWORD=...
```

> `.env` 已在 `.gitignore` 內，**切勿提交真實金鑰**。各變數完整說明見 `.env.example`。

---

## 2. 一鍵啟動（Docker Compose）

```bash
docker compose up -d --build
```

這會：

1. **建置** `transcriber` 映像（多階段、非 root、內含 `ffmpeg`）。
2. 啟動 **db**（`pgvector/pgvector:pg16`）並於**首次**自動套用 `supabase/schema.sql`。
3. 啟動 **transcriber**（逐字稿微服務）。
4. 啟動 **n8n**（編排引擎，等 db 與 transcriber 健康後才啟動）。

確認狀態（三個服務都應為 `healthy`）：

```bash
docker compose ps
```

冒煙測試逐字稿微服務：

```bash
curl localhost:8000/health     # {"status":"ok",...}
curl localhost:8000/ready      # {"ready":true,...}
```

常用維運指令：

```bash
docker compose logs -f             # 追蹤全部日誌
docker compose logs -f transcriber # 只看某服務
docker compose down                # 停止（保留資料）
docker compose down -v             # 停止並清除資料卷（會重置資料庫）
```

> **連線埠**：`db`（5432）與 `transcriber`（8000）只綁定 `127.0.0.1`，不對外。
> n8n UI（5678）對外開放方便操作——正式環境請放在 HTTPS 反向代理後並啟用驗證。

> **重新套用 schema**：`schema.sql` 只在資料卷為空時自動執行。改過 schema 後要
> `docker compose down -v` 重來，或手動 `docker compose exec -T db psql -U postgres -d whytee < supabase/schema.sql`。

---

## 3. 匯入 n8n 工作流並接線憑證

1. 開啟 <http://localhost:5678>，建立管理者帳號。
2. **匯入工作流**：左側 *Workflows* → *Import from File*，逐一匯入：
   - `n8n/workflows/01-historical-backfill.json`（歷史回溯）
   - `n8n/workflows/02-realtime-geo-analysis.json`（即時 GEO 分析）
   - `n8n/workflows/03-format-and-deliver.json`（格式化推播）
   - `n8n/workflows/04-agentic-rag-chat.json`（雙向對話）
3. **建立 Credentials**（*Credentials* → *Add Credential*）：
   - **OpenAI（指向 OpenRouter）**：給 LLM／Embedding／Agent 節點用。Base URL 覆寫
     為 `https://openrouter.ai/api/v1`，API Key 填 `OPENROUTER_API_KEY`。
   - **Supabase / Postgres**：Vector Store 與 Chat Memory 節點用。連 `db` 服務
     （host `db`、port `5432`、db `whytee`、帳密同 `.env`）。
   - **Telegram**：以 `TELEGRAM_BOT_TOKEN` 建立。
   - **YouTube**：HTTP Request 節點以 `={{ $env.YOUTUBE_API_KEY }}` 帶入即可，免額外憑證。
4. 逐一打開工作流，把各節點（節點上有 `notes` 提示）指派到上述憑證；Vector Store
   節點記得連上 **Embeddings** 子節點（模型維度需與 `schema.sql` 的 `vector(1536)` 相符）。
5. 工作流內的逐字稿節點已指向堆疊內位址 `http://transcriber:8000/transcribe`，免修改。
   若有設 `TRANSCRIBER_API_KEY`，請在該 HTTP 節點加上 `Authorization: Bearer <金鑰>` 標頭。

各工作流節點與資料流詳見 [`workflows.md`](./workflows.md)。

---

## 4. 端到端驗證

1. **逐字稿微服務**：`curl localhost:8000/health` 回 `status: ok`。
2. **歷史回溯**：在 n8n 手動執行工作流一，跑一小批；到資料庫確認 `transcripts`
   與 `embeddings` 有資料：
   ```bash
   docker compose exec db psql -U postgres -d whytee -c "select count(*) from embeddings;"
   ```
3. **即時分析**：對追蹤頻道發布測試影片（或重送 WebSub），確認工作流二觸發、
   Telegram 收到 GEO 摘要。
4. **雙向對話**：用白名單內的帳號私訊 Bot，工作流四應回覆並引用歷史 `video_id`；
   非白名單帳號的訊息會被靜默丟棄。

---

## 5. 逐字稿微服務設定（`TRANSCRIBER_` 前綴）

| 變數 | 預設 | 說明 |
| --- | --- | --- |
| `TRANSCRIBER_DEFAULT_LANGUAGES` | `["zh-TW","zh-Hant","zh","en"]` | 語言優先順序（可填逗號或 JSON 陣列）。 |
| `TRANSCRIBER_STT_BACKEND` | `local` | 第二層後端：`local`／`cloud`／`elevenlabs`／`mlx`。 |
| `TRANSCRIBER_WHISPER_MODEL` | `base` | local 後端模型大小。 |
| `TRANSCRIBER_WHISPER_DEVICE` | `auto` | `auto`／`cpu`／`cuda`。 |
| `TRANSCRIBER_CLOUD_STT_BASE_URL` | Groq | cloud 後端 OpenAI 相容端點。 |
| `TRANSCRIBER_CLOUD_STT_MODEL` | `whisper-large-v3` | cloud 後端模型。 |
| `TRANSCRIBER_CLOUD_STT_API_KEY` | （空） | cloud 後端金鑰；空值時 `/ready` 回 503。 |
| `TRANSCRIBER_ELEVENLABS_API_KEY` | （空） | elevenlabs 後端金鑰。 |
| `TRANSCRIBER_MLX_MODEL` | `whisper-large-v3-mlx` | mlx 後端模型（需 `mlx-whisper`，Apple Silicon）。 |
| `TRANSCRIBER_AUDIO_CHUNK_SECONDS` | `900` | 音訊分塊秒數。 |
| `TRANSCRIBER_API_KEY` | （空） | 設定後 `/transcribe*` 需帶 `Authorization: Bearer`。 |
| `TRANSCRIBER_WEBSHARE_PROXY_USERNAME` | （空） | 住宅代理帳號。 |
| `TRANSCRIBER_WEBSHARE_PROXY_PASSWORD` | （空） | 住宅代理密碼。 |

預設 `local` 後端免金鑰、跑在容器 CPU 上。要改用雲端 STT（免本地算力、需付費金鑰）：

```dotenv
TRANSCRIBER_STT_BACKEND=cloud
TRANSCRIBER_CLOUD_STT_API_KEY=gsk_...
```

改完 `.env` 後 `docker compose up -d transcriber` 重建即可；`curl localhost:8000/ready`
確認後端就緒。

---

## 6. 反爬蟲 / 代理（重要）

從**資料中心 / 雲端伺服器 IP** 直連 YouTube，字幕與 `yt-dlp` 下載都很容易被回
`403`／`410 Gone`。本服務會把這類封鎖轉成明確錯誤並在啟動時警告。實務上請：

1. 在 `.env` 填入 `WEBSHARE_PROXY_USERNAME` / `WEBSHARE_PROXY_PASSWORD`（或其他
   住宅代理供應商，於 `app/proxy.py` 調整端點）。
2. 在 n8n 批次迴圈維持 `Wait`（預設 60 秒）禮貌性延遲。

未設代理時 `curl localhost:8000/health` 會顯示 `"proxy_enabled": false`，且
log 會出現一則警告。細節見 [`security.md`](./security.md)。

---

## 7.（選用）本機開發逐字稿微服務

不經 Docker，直接在本機跑微服務做開發：

```bash
make install   # cd transcription-service && pip install -e ".[dev]"（音訊層需 ffmpeg）
make test      # 單元測試（免網路／金鑰）
make lint      # ruff 檢查
make run       # uvicorn，http://localhost:8000
make smoke     # curl /health
```

服務會自動讀取專案根目錄的 `.env`（`app/config.py` 會找 `./.env` 與 `../.env`）。
開 <http://localhost:8000/docs> 可瀏覽互動式 OpenAPI 文件。

---

## 8. 疑難排解

| 症狀 | 可能原因 / 解法 |
| --- | --- |
| `docker compose ps` 顯示 transcriber 一直 unhealthy | 看 `docker compose logs transcriber`；多半是 `.env` 設定問題或埠衝突。 |
| `/transcribe` 回 `502`，訊息含 `blocked` / `403` / `410` | YouTube 封鎖伺服器 IP；設定住宅代理（§6）並加大 n8n Wait 延遲。 |
| `/ready` 回 `503` | 所選後端缺金鑰／套件（如 `cloud` 沒填 `CLOUD_STT_API_KEY`）。 |
| `/transcribe` 回 `401` | 有設 `TRANSCRIBER_API_KEY`，呼叫端要帶 `Authorization: Bearer <金鑰>`。 |
| n8n 連不上資料庫 | 確認 `db` healthy；憑證 host 用 `db`、port `5432`、帳密與 `.env` 一致。 |
| 改了 `schema.sql` 沒生效 | init 腳本只在空資料卷跑；`docker compose down -v` 後重來。 |
| 對話沒記憶 / Chat Memory 報錯 | 確認用 `n8n_chat_histories` 表（schema 已內建，欄位對齊 n8n 節點）。 |
| 向量檢索結果差 | 調整 `embeddings` 的 IVFFlat `lists` 參數以符合語料規模。 |
| Telegram `400 can't parse entities` | MarkdownV2 特殊字元未跳脫；見工作流三 Code 節點。 |
| 映像建置時拉不到 base image | 你的網路擋了 Docker Hub；換可連網環境或設定 registry mirror。 |

---

## 9. 在 Claude Code on the web 開發

倉庫內含 SessionStart hook（`.claude/hooks/session-start.sh`），於遠端 web session
啟動時自動安裝逐字稿微服務（含 dev 相依與 `ffmpeg`），讓 `pytest`／`ruff` 直接可用。
合併進預設分支後，後續所有 web session 皆會套用。
