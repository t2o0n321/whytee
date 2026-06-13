# 變更紀錄（Changelog）

本專案版本紀錄格式參考 [Keep a Changelog](https://keepachangelog.com/zh-TW/1.1.0/)，
並遵循 [語意化版本](https://semver.org/lang/zh-TW/)。

## [Unreleased]

### 新增
- `Makefile`：`install`／`test`／`cov`／`lint`／`fmt`／`run`／`up`／`down` 等常用指令。
- `LICENSE`（MIT）、`CONTRIBUTING.md`、`CHANGELOG.md`。
- `.dockerignore` 以縮小映像建置上下文。
- `ruff` 靜態檢查與 `pytest-cov` 覆蓋率設定（`pyproject.toml`）。
- GitHub Actions CI：安裝 → ruff → pytest。
- Claude Code on the web 的 SessionStart hook（`.claude/`）。
- `docs/setup.md`（部署與 n8n 憑證接線逐步說明、疑難排解）與 `docs/README.md` 文件索引。
- 逐字稿微服務：FastAPI 端點測試、結構化日誌與 request id、`/ready` 就緒探測。
- 第二層 STT 新增雲端 Whisper 供應器（OpenRouter／Groq，OpenAI 相容），以環境變數啟用。

### 變更
- `docker-compose.yml`：transcriber 改用 `env_file: .env`，並為 n8n 加入 healthcheck。
- `transcription-service/Dockerfile`：複製 `README.md` 以符合 `pyproject.toml` 的 `readme` 宣告。

## [0.1.0] — 初始骨架

### 新增
- 逐字稿微服務：兩層降級轉錄（`captions` → `whisper_local`）、REST API、音訊分塊、代理 hook，附 provider-mock 單元測試。
- Supabase 結構：關聯表 + pgvector + `match_documents` 檢索函式。
- 三個可匯入的 n8n 工作流骨架與 docker-compose 堆疊。
- 設計文件（繁體中文）：architecture／workflows／api／security。
