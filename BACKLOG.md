# BACKLOG.md

## Now

- [x] 初始化 Next.js frontend
- [x] 初始化 FastAPI backend
- [x] 加入 Docker Compose: PostgreSQL, Redis
- [ ] 建立基礎 database migration
- [ ] 實作 async job model
- [x] 實作 Amazon report create API
- [x] 實作 Amazon scraper adapter interface

## Next

- [ ] 建立 report dashboard layout
- [ ] 實作 price distribution chart
- [ ] 實作 rating / review distribution chart
- [ ] 實作 Top 200 product table
- [ ] 加入 Redis cache layer
- [ ] 加入 credit pre-charge / refund flow
- [ ] 加入 LLM VOC worker
- [ ] 填入 APIFY_API_TOKEN 並測試真實 Amazon fetch

## Later

- [ ] Amazon OAuth
- [ ] Amazon Product Type Definitions adapter
- [ ] Amazon Listings Items validation preview
- [ ] Draft editor
- [ ] Validation issue repair suggestions

## Technical Debt

- [ ] 加入 request id / trace id
- [ ] 加入 structured logging
- [ ] 加入 background job retry policy
- [ ] 加入 rate limit
- [ ] 加入 RLS policy
- [ ] 加入 secret scanning

## Decisions

- MVP 只做 Amazon。
- 搜尋分析先用 scraper / Apify，不強行用 SP-API。
- Amazon 上架先做 internal draft + validation preview，不做一鍵 live publish。
- 所有長任務都走 queue。
- 所有昂貴任務都走 credits + cache。
