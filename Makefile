# whytee — 常用開發指令
# 逐字稿微服務以 transcription-service/ 為工作目錄；其餘指令操作整體 Docker 堆疊。

SERVICE_DIR := transcription-service

.DEFAULT_GOAL := help
.PHONY: help install test cov lint fmt run up down logs ps clean smoke

help: ## 顯示可用指令
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install: ## 安裝逐字稿微服務（含 dev 相依）
	cd $(SERVICE_DIR) && pip install -e ".[dev]"

test: ## 執行單元測試（免網路／金鑰）
	cd $(SERVICE_DIR) && pytest

cov: ## 執行測試並輸出覆蓋率報告
	cd $(SERVICE_DIR) && pytest --cov=app --cov-report=term-missing

lint: ## ruff 靜態檢查
	cd $(SERVICE_DIR) && ruff check .

fmt: ## ruff 自動格式化與修正
	cd $(SERVICE_DIR) && ruff format . && ruff check --fix .

run: ## 本機啟動逐字稿微服務（熱重載）
	cd $(SERVICE_DIR) && uvicorn app.main:app --reload

smoke: ## 對執行中的服務做一次健康檢查
	curl -fsS localhost:8000/health && echo

up: ## 啟動完整本機堆疊（db + transcriber + n8n）
	docker compose up -d db transcriber n8n

down: ## 停止本機堆疊
	docker compose down

logs: ## 追蹤本機堆疊日誌
	docker compose logs -f

ps: ## 顯示堆疊服務狀態
	docker compose ps

clean: ## 清除 Python 暫存與測試快取
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf $(SERVICE_DIR)/.pytest_cache $(SERVICE_DIR)/.ruff_cache \
		$(SERVICE_DIR)/*.egg-info $(SERVICE_DIR)/.coverage
