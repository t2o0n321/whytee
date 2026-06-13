# 逐字稿微服務 REST 契約

供 n8n HTTP Request 節點介接。欄位名稱依慣例保留英文。

服務為無狀態（stateless），排程與限速由 n8n 負責。

## `GET /health`

存活檢查（liveness）。回傳：

```json
{
  "status": "ok",
  "version": "0.1.0",
  "default_languages": ["zh-TW", "zh-Hant", "zh", "en"],
  "whisper_model": "base",
  "stt_backend": "local",
  "proxy_enabled": false
}
```

`proxy_enabled` 為 `false` 時，從伺服器／資料中心 IP 呼叫常遭 YouTube 以
`403`／`410` 封鎖；服務啟動時會記錄一則警告。見下方錯誤碼與 `docs/security.md`。

每個回應都附帶 `X-Request-ID` 標頭；可由請求端帶入同名標頭以串接 n8n 的日誌追蹤。

## `GET /ready`

就緒檢查（readiness）。檢查第二層 STT 後端是否可用：`local` 一律就緒（模型於首次
音訊請求時延遲載入）；`cloud` 需設定 `TRANSCRIBER_CLOUD_STT_API_KEY`，否則回 `503`。

```json
{ "ready": true, "stt_backend": "local", "detail": "ok" }
```

## `POST /transcribe`

請求 body（`video_id` 與 `url` 至少擇一）：

```json
{
  "video_id": "dQw4w9WgXcQ",
  "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "languages": ["zh-TW", "en"],
  "force_audio": false
}
```

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| `video_id` | string? | 11 碼 YouTube 影片 ID。 |
| `url` | string? | 完整 watch URL（亦接受 `youtu.be`／`shorts`／`embed`）。 |
| `languages` | string[]? | 語言優先順序；省略時用伺服器預設。 |
| `force_audio` | bool | 跳過字幕，直接走音訊 + Whisper。 |

回應：

```json
{
  "video_id": "dQw4w9WgXcQ",
  "language": "zh-TW",
  "source": "captions",
  "segments": [{ "start": 0.0, "duration": 2.5, "text": "..." }],
  "text": "完整逐字稿……",
  "duration_s": 213.4
}
```

`source` 為 `captions`（第一層）或 `whisper_local`（第二層）。

錯誤碼：

- `400` — 缺少識別碼／格式錯誤。
- `422` — 請求 body 驗證失敗（`video_id` 與 `url` 皆缺）。
- `502` — 轉錄失敗。其 `detail` 會明確區分兩類常見原因：
  - **遭封鎖**：YouTube 以 `403`／`410` 拒絕（`TranscriptBlockedError`），訊息含
    住宅代理與加大限速延遲的指引。
  - **其他**：無字幕且音訊抓取／STT 失敗。

## `POST /transcribe/batch`

批次回補輔助端點，逐筆處理並彙整 per-item 錯誤而不整批失敗：

```json
{ "items": [ { "video_id": "..." }, { "url": "..." } ] }
```

回應 `{ "results": [...], "errors": [{ "request": {...}, "error": "..." }] }`。

## 設定（環境變數，前綴 `TRANSCRIBER_`）

| 變數 | 預設 | 說明 |
| --- | --- | --- |
| `TRANSCRIBER_DEFAULT_LANGUAGES` | `["zh-TW","zh-Hant","zh","en"]` | 預設語言優先順序。 |
| `TRANSCRIBER_STT_BACKEND` | `local` | 第二層後端：`local`（faster-whisper）或 `cloud`。 |
| `TRANSCRIBER_WHISPER_MODEL` | `base` | local 後端 faster-whisper 模型大小。 |
| `TRANSCRIBER_WHISPER_DEVICE` | `auto` | `auto`／`cpu`／`cuda`。 |
| `TRANSCRIBER_CLOUD_STT_BASE_URL` | `https://api.groq.com/openai/v1` | cloud 後端 OpenAI 相容端點。 |
| `TRANSCRIBER_CLOUD_STT_MODEL` | `whisper-large-v3` | cloud 後端模型。 |
| `TRANSCRIBER_CLOUD_STT_API_KEY` | （空） | cloud 後端金鑰；空值時 `/ready` 回 503。 |
| `TRANSCRIBER_AUDIO_CHUNK_SECONDS` | `900` | 音訊分塊秒數（15 分鐘）。 |
| `TRANSCRIBER_REQUEST_DELAY_SECONDS` | `60` | 建議的請求間延遲（由 n8n Wait 節點執行）。 |
| `TRANSCRIBER_WEBSHARE_PROXY_USERNAME` | （空） | Webshare 住宅代理帳號，空值停用代理。 |
| `TRANSCRIBER_WEBSHARE_PROXY_PASSWORD` | （空） | Webshare 住宅代理密碼。 |

## 同介面替代供應器

第二層 STT 在 `app/providers/` 下以相同 `transcribe_chunks` 介面實作，由
`TRANSCRIBER_STT_BACKEND` 切換：

- **本地 faster-whisper**（`local`，預設）：跨平台、免金鑰，於 CPU/GPU 執行。
  實作於 `app/providers/whisper_local.py`。
- **雲端 Whisper**（`cloud`）：OpenAI 相容端點（Groq／OpenRouter／OpenAI），
  規避本地算力需求。實作於 `app/providers/whisper_cloud.py`。

尚可依相同介面擴充（後續工作）：

- **Apple MLX Whisper**：Apple Silicon 上的高速本地轉錄。
- **ElevenLabs Scribe**：99+ 語言、高噪音環境準確度佳。
