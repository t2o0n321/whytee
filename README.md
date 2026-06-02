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
│   ├── architecture.md      # 系統架構
│   ├── workflows.md         # 三個 n8n 工作流規格
│   ├── api.md               # 逐字稿微服務 REST 契約
│   └── security.md          # 資安與部署防護
├── transcription-service/   # 主程式：階層式降級轉錄微服務（Python/FastAPI）
├── supabase/schema.sql      # PostgreSQL + pgvector 結構與 RAG 檢索函式
├── n8n/workflows/*.json     # 三個可匯入的 n8n 工作流骨架
├── docker-compose.yml       # db + transcriber + n8n 本機堆疊
└── .env.example             # 所有金鑰與設定範本
```

## 快速開始

```bash
cp .env.example .env          # 填入各項金鑰

# 1) 逐字稿微服務（主程式）— 單元測試免網路／金鑰
cd transcription-service
pip install -e ".[dev]"       # 音訊層需系統有 ffmpeg
pytest
uvicorn app.main:app --reload
curl localhost:8000/health

# 2) 完整本機堆疊
docker compose up -d db transcriber n8n
# 於 n8n UI 匯入 n8n/workflows/*.json 並設定 Credentials
# 資料庫結構由 docker-compose 於初始化時自動套用 supabase/schema.sql
```

## 實作狀態

**已實作**

- 逐字稿微服務：兩層降級轉錄（`captions` → `whisper_local`）、REST API、
  音訊分塊、代理 hook，附 provider-mock 單元測試。
- Supabase 結構：關聯表 + pgvector + `match_documents` 檢索函式。
- 可匯入的 n8n 工作流骨架（三流程）與 docker-compose 堆疊。

**未涵蓋範圍（已於文件標示為後續工作）**

- 真實 OpenRouter / Telegram 憑證與線上呼叫。
- MLX / 雲端 Whisper、ElevenLabs Scribe 等替代轉錄供應器。
- 完整 Agentic RAG 雙向對話與長期記憶。
- 生產級住宅代理帳號與外部 HTTPS WebSub 回呼。
