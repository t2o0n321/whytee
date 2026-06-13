# whytee — 智慧化 YouTube 頻道追蹤與歷史語料分析

基於 **n8n + OpenRouter + Supabase + 開源逐字稿技術** 的端到端架構：自動追蹤
YouTube 頻道、轉錄每支影片、將歷史語料向量化為 RAG 知識庫，並透過 Telegram
進行跨時間軸的「觀點演進」分析與雙向問答。

> 完整設計依據整理自研究報告 `YouTube逐字稿開源專案與n8n.pdf`。

## 架構總覽

```
YouTube ──(WebSub / Data API)──> n8n（編排引擎）
                                   │
        ┌──────────────┬──────────┼─────────────┬───────────────┐
        ▼              ▼          ▼             ▼               ▼
  逐字稿微服務     OpenRouter   Supabase      Telegram      Wait/Loop
 （本專案主程式）（LLM 路由）（pgvector）   Bot API        （限速）
```

詳見 [`docs/architecture.md`](docs/architecture.md)。

## 專案結構

```
whytee/
├── docs/                    # 設計文件（繁體中文）
│   ├── README.md            # 文件索引
│   ├── setup.md             # 安裝、部署與 n8n 接線逐步指南 + 疑難排解
│   ├── architecture.md      # 系統架構
│   ├── workflows.md         # 三個 n8n 工作流規格
│   ├── api.md               # 逐字稿微服務 REST 契約
│   └── security.md          # 資安與部署防護
├── transcription-service/   # 主程式：階層式降級轉錄微服務（Python/FastAPI）
├── supabase/schema.sql      # PostgreSQL + pgvector 結構與 RAG 檢索函式
├── n8n/workflows/*.json     # 四個可匯入的 n8n 工作流骨架
├── docker-compose.yml       # db + transcriber + n8n 本機堆疊
├── Makefile                 # install / test / lint / run / up / down 等捷徑
└── .env.example             # 所有金鑰與設定範本
```

## 快速開始

完整逐步說明（含 n8n 憑證接線與疑難排解）見 [`docs/setup.md`](docs/setup.md)。

```bash
cp .env.example .env          # 填入各項金鑰

# 1) 逐字稿微服務（主程式）— 單元測試免網路／金鑰
make install                  # cd transcription-service && pip install -e ".[dev]"（音訊層需 ffmpeg）
make test                     # 單元測試
make run                      # uvicorn，http://localhost:8000
make smoke                    # curl /health

# 2) 完整本機堆疊
make up                       # docker compose up -d db transcriber n8n
# 於 n8n UI 匯入 n8n/workflows/*.json 並設定 Credentials（見 docs/setup.md §5）
# 資料庫結構由 docker-compose 於初始化時自動套用 supabase/schema.sql
```

> 不使用 Make 亦可：`cd transcription-service && pip install -e ".[dev]" && pytest`。

## 實作狀態

**已實作**

- 逐字稿微服務：兩層降級轉錄（`captions` → 第二層 STT）、REST API
  （`/health`、`/ready`、`/transcribe`、`/transcribe/batch`）、音訊分塊、代理
  hook、結構化日誌與 request id，附端點與 provider-mock 單元測試。
- 第二層 STT 四後端（同介面、`source` 反映後端）：本地 `faster-whisper`、雲端
  OpenAI 相容 Whisper（Groq／OpenRouter）、ElevenLabs Scribe、Apple MLX，由
  `TRANSCRIBER_STT_BACKEND` 切換；`/ready` 依後端檢查金鑰／套件就緒。
- 韌性：YouTube 封鎖（403／410）對應為帶代理指引的明確錯誤。
- Supabase 結構：關聯表 + pgvector + `match_documents` 檢索函式。
- 可匯入的 n8n 工作流骨架（四流程，含 Agentic RAG 雙向對話）與 docker-compose 堆疊。
- 開發工具：`Makefile`、`ruff` 檢查／格式化、`pytest` 覆蓋率、GitHub Actions CI
  （含 Docker build 煙霧測試）、Claude Code on the web 的 SessionStart hook。

**部署前置（需自備帳號／基礎設施，非程式缺口）**

- 真實 OpenRouter / Telegram / YouTube / Supabase 憑證與線上呼叫。
- 生產級住宅代理帳號（從伺服器 IP 存取 YouTube 實質必要）。
- 外部 HTTPS 端點以接收 WebSub 回呼（工作流二）。
- `elevenlabs`／`mlx` 後端各自的金鑰或 Apple Silicon 環境（選用）。

授權：[MIT](LICENSE)。貢獻方式見 [`CONTRIBUTING.md`](CONTRIBUTING.md)，
變更紀錄見 [`CHANGELOG.md`](CHANGELOG.md)。
