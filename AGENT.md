# AGENT.md

## Project Direction

本專案先聚焦做一條清晰可交付的 MVP 閉環：

1. Amazon keyword 搜尋分析
2. Top 200 競品資料抓取與指標分佈
3. Top 20 深度 VOC / 賣點 / 痛點分析
4. 生成 Amazon Listing Draft
5. 透過 Amazon SP-API 做 draft validation preview

暫時不做 TikTok Shop、eBay、多平台同步發布、影片分析與完整 ERP 功能。

## Mandatory Working Rule

每次有任何 action 之前，先閱讀：

1. `AGENT.md`
2. `ROADMAP.md`

所有開發、文件、架構、資料庫、API、UI 決策都必須向同一個方向前進：先打通 Amazon 搜尋分析 + Amazon 發布草稿。

## Product Principles

- MVP 先證明付費價值，不追求一次做完整平台。
- 優先交付可用 workflow，而不是完美架構。
- 競品分析結果必須能轉化成 Listing Draft，不做純展示型報表。
- 所有昂貴 API 操作都要有 credit、cache、rate limit。
- 用戶資料必須 multi-tenant 隔離，所有查詢都帶 `user_id`。
- OAuth token 必須加密儲存，不得明文寫入 database 或 log。

## Technical Direction

### Frontend

- Next.js
- React
- Tailwind CSS
- shadcn/ui
- ECharts / Recharts for dashboard charts

### Backend

- FastAPI
- PostgreSQL
- Redis
- Celery / RQ
- SQLAlchemy / Alembic

### AI / Data

- LLM gateway abstraction，避免綁死單一模型供應商
- competitor raw data 存 JSONB
- VOC / SWOT / Listing suggestions 存 JSONB
- 後續需要語義搜尋時再加入 pgvector

### Amazon

- Amazon 搜尋分析：MVP 優先用 Apify / scraper service
- Amazon draft validation：使用 Amazon SP-API
- 類目欄位：使用 Product Type Definitions API
- 上架檢查：使用 Listings Items API validation preview

## Engineering Rules

- 不直接硬編碼 secret。
- 不在 log 輸出 access token、refresh token、buyer data。
- 長任務必須走 queue，不讓 HTTP request 等 1-3 分鐘。
- 所有 background job 要有狀態：`queued`, `running`, `completed`, `failed`。
- 失敗任務要保留 `error_message` 與 retry 次數。
- 每個新增功能要更新 `CHANGELOG.md` 或 `BACKLOG.md`。

## Current MVP Definition

成功標準：

1. 用戶輸入 Amazon keyword。
2. 系統建立 async report job。
3. Worker 抓 Top 200 competitor products。
4. Dashboard 顯示價格、rating、review、品牌與頭部效應。
5. 系統對 Top 20 做 LLM VOC 分析。
6. 用戶上傳或輸入自己的產品資料。
7. AI 生成 Amazon Listing Draft。
8. 系統可用 Amazon SP-API validation preview 檢查 draft 缺失欄位。

