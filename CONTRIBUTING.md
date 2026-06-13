# 貢獻指南

歡迎協助改善 whytee。本文件說明開發環境、程式碼風格與提交流程。

## 開發環境

逐字稿微服務（主程式）以 Python 3.10+ 開發，音訊層需系統安裝 `ffmpeg`。

```bash
make install     # 等同 cd transcription-service && pip install -e ".[dev]"
make test        # 執行單元測試（免網路／金鑰）
make lint        # ruff 靜態檢查
make fmt         # ruff 自動格式化與修正
make run         # 本機啟動服務（http://localhost:8000）
```

完整本機堆疊（PostgreSQL + transcriber + n8n）：

```bash
cp .env.example .env   # 填入金鑰
make up                # docker compose up -d
make down              # 停止
```

## 程式碼風格

- 以 `ruff`（檢查 + 格式化）為唯一風格工具，設定於 `transcription-service/pyproject.toml`。
- 型別註記採 `from __future__ import annotations`，公開函式與模組附 docstring。
- 程式介面欄位與識別碼維持英文；說明文件維持繁體中文。

## 測試

- 所有新行為都應附測試。供應器（providers）的網路呼叫一律以 `monkeypatch` 模擬，
  測試不得依賴真實 YouTube／金鑰／模型下載。
- 提交前請確認 `make test` 與 `make lint` 皆通過；CI 會在 PR 上重跑相同步驟。

## 提交與 PR

1. 由 `main` 開分支，分支名稱簡述用途。
2. Commit 訊息使用祈使句、聚焦單一變更，必要時於內文補充背景。
3. 變更若影響使用者可見行為，請同步更新 `CHANGELOG.md` 的 `Unreleased` 區段與相關文件。
4. 開 PR 時描述動機、做法與驗證方式。

## 安全

請勿提交任何真實金鑰或 `.env`。回報安全問題請參考 [`docs/security.md`](docs/security.md)
的金鑰代理與授權白名單設計，避免在 issue 中貼出敏感資訊。
