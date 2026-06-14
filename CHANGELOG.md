# 變更紀錄（Changelog）

本專案版本紀錄格式參考 [Keep a Changelog](https://keepachangelog.com/zh-TW/1.1.0/)，
並遵循 [語意化版本](https://semver.org/lang/zh-TW/)。

## [Unreleased]

### 修正（產品化 QA）
- **開機崩潰**：`TRANSCRIBER_DEFAULT_LANGUAGES` 以逗號字串設定時不再 crash；新增
  validator 同時接受逗號與 JSON 陣列。
- **磁碟外洩 + 資料污染**：第二層音訊轉錄改在 `try/finally` 清理下載與分塊檔；
  `split_audio` 先清除舊 chunk、ffmpeg 加 `-y`，避免把上一支影片的殘留音訊拼進來。
- **聊天記憶無法運作**：`schema.sql` 的對話表改為 `n8n_chat_histories`，欄位
  （`id`/`session_id`/`message jsonb`）對齊 n8n Postgres Chat Memory 節點；工作流四
  同步更新。
- **工作流接線缺漏**：工作流一補上頻道→上傳清單解析、分頁、`splitInBatches` 迴圈
  回接與 Embeddings 子節點；工作流二補上 Atom XML 解析（取得 `videoId`）、保留逐字
  稿文字、彙整檢索歷史與 Embeddings 子節點。
- `whisper_local` 片段時長加上非負保護，與其他後端一致。

### 新增
- 逐字稿微服務可選 Bearer Token 認證（`TRANSCRIBER_API_KEY`）與 `/transcribe/batch`
  筆數上限（`batch_max_items`）。
- 本機執行時 `app/config.py` 會同時尋找 `./.env` 與 `../.env`，單一根目錄 `.env` 即可。

### Docker（以 Docker 為主要部署方式）
- `Dockerfile` 改為多階段建置、非 root 執行、內建 `HEALTHCHECK`。
- `docker-compose.yml`：`db`／`transcriber` 僅綁定 `127.0.0.1`，全服務加 `restart`
  與具名容器，n8n 依賴 transcriber 健康後啟動，`docker compose up -d --build` 一鍵啟動。
- `docs/setup.md` 改寫為「clone → docker compose up → 匯入工作流」的逐步指南。

### 新增（既有）
- `Makefile`：`install`／`test`／`cov`／`lint`／`fmt`／`run`／`up`／`down` 等常用指令。
- `LICENSE`（MIT）、`CONTRIBUTING.md`、`CHANGELOG.md`。
- `.dockerignore` 以縮小映像建置上下文。
- `ruff` 靜態檢查與 `pytest-cov` 覆蓋率設定（`pyproject.toml`）。
- GitHub Actions CI：安裝 → ruff → pytest。
- Claude Code on the web 的 SessionStart hook（`.claude/`）。
- `docs/setup.md`（部署與 n8n 憑證接線逐步說明、疑難排解）與 `docs/README.md` 文件索引。
- 逐字稿微服務：FastAPI 端點測試、結構化日誌與 request id、`/ready` 就緒探測。
- 第二層 STT 新增雲端 Whisper 供應器（OpenRouter／Groq，OpenAI 相容），以環境變數啟用。
- 第二層 STT 再新增 ElevenLabs Scribe 與 Apple MLX 供應器（同 `transcribe_chunks` 介面）；
  `TRANSCRIBER_STT_BACKEND` 可選 `local`／`cloud`／`elevenlabs`／`mlx`，回應 `source` 反映後端，
  `/ready` 依後端檢查金鑰／套件就緒。
- 第四個 n8n 工作流 `04-agentic-rag-chat.json`：Telegram 觸發 → 白名單授權 →
  AI Agent（OpenRouter deep + Postgres Chat Memory + Supabase Retrieve-as-Tool）→ 回覆。

- 韌性：字幕供應器將 YouTube 封鎖（403／410／IP block）對應為
  `TranscriptBlockedError`，附住宅代理與限速指引；服務啟動時若未設定代理會記錄警告。
- `/health` 新增 `proxy_enabled` 欄位。
- 選用整合測試（`RUN_INTEGRATION=1`）實際呼叫 YouTube；CI 預設略過。
- CI 新增 `docker build` + 啟動 `/health`、`/ready` 煙霧測試。

### 變更
- `docker-compose.yml`：transcriber 改用 `env_file: .env`（選用，缺檔不報錯），並為 n8n 加入 healthcheck。
- `transcription-service/Dockerfile`：複製 `README.md` 以符合 `pyproject.toml` 的 `readme` 宣告。
- 將 `youtube-transcript-api` 釘選為 `>=1.0,<2`（程式使用 1.x 實例 API，與 0.6.x 不相容）。

## [0.1.0] — 初始骨架

### 新增
- 逐字稿微服務：兩層降級轉錄（`captions` → `whisper_local`）、REST API、音訊分塊、代理 hook，附 provider-mock 單元測試。
- Supabase 結構：關聯表 + pgvector + `match_documents` 檢索函式。
- 三個可匯入的 n8n 工作流骨架與 docker-compose 堆疊。
- 設計文件（繁體中文）：architecture／workflows／api／security。
