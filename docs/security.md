# 資安與部署防護策略

## 1. API 金鑰代理模式（API Key Proxy）

為防止 Prompt Injection 導致金鑰外洩：

- 執行爬蟲／初步處理的節點與存放金鑰的 n8n 主實體**物理隔離**。
- 前端代理（Agents）僅向 n8n 發送**不含金鑰**的 Webhook 請求。
- n8n 於安全後端注入 OpenRouter 等認證憑證後再轉發外部 API。
- 敏感金鑰永不進入可能被 LLM 讀取的提示詞上下文。

## 2. n8n Credentials 集中管理

所有 API 金鑰（YouTube Data API、OpenRouter、Supabase、Telegram Token）一律
使用 n8n 原生 Credentials 系統存放，於資料庫層級加密，節點間傳遞不以明文暴露。

切勿將金鑰寫死於流程變數或自訂腳本。本機開發以 `.env`（已列入 `.gitignore`）
管理，範本見 [`.env.example`](../.env.example)。

## 3. Telegram 授權白名單

Telegram Bot 對外開放時，須在 Telegram Trigger 節點後立即加入授權邏輯：比對
發訊者 `user_id` / `chat_id` 是否存在於白名單（`TELEGRAM_ALLOWED_CHAT_IDS`），
未授權訊息第一時間捨棄，防止濫用昂貴的 LLM 配額與資料庫資源。

## 4. 反爬蟲與網路層韌性

- **住宅代理輪替**：整合 Webshare 等供應商，於 `youtube-transcript-api` 與
  `yt-dlp` 配置代理（見 `transcription-service/app/proxy.py`），分散請求來源。
- **禮貌性限速**：在批次迴圈中強制 Wait 節點（預設 60 秒），刻意降低存取頻率，
  避免 IP 封鎖（IP Ban）或 `410 Gone`。
- 初期建立語料庫雖耗時，但限速是長期存活與資料完整性的關鍵。

## 5. 部署備註

- WebSub 回呼需公開可達的 `N8N_WEBHOOK_URL`（生產環境須具備外部 HTTPS）。
- Supabase / PostgreSQL 資料卷需定期備份；`embeddings` 的 IVFFlat 索引 `lists`
  參數應隨語料規模調校。
