# ROADMAP.md

## North Star

先做一個可上線、可收費、可驗證市場需求的 Amazon MVP：

Amazon keyword 搜尋分析 -> 競品 VOC 洞察 -> 自家產品 Gap Analysis -> Amazon Listing Draft -> SP-API validation preview。

## Phase 0 - Project Foundation

Target: 建立專案方向、基礎文件與開發約束。

- [x] 建立 `AGENT.md`
- [x] 建立 `ROADMAP.md`
- [x] 建立 `BACKLOG.md`
- [x] 建立 `CHANGELOG.md`
- [x] 建立 `.env` / `.env.example`
- [x] 初始化 backend / frontend 專案結構
- [x] 建立 Docker Compose: PostgreSQL + Redis

## Phase 1 - Amazon Search Analysis

Target: 用戶輸入 keyword 後，可以產生 Amazon Top 200 競品分析報告。

- [ ] User auth 基礎結構
- [ ] Subscription / credits schema
- [ ] Market report schema
- [ ] Competitor products schema
- [ ] `POST /amazon/reports`
- [ ] `GET /jobs/{job_id}`
- [ ] Redis job state
- [ ] Celery worker
- [x] Amazon scraper adapter
- [x] Top 200 product normalization
- [ ] Dashboard: price distribution
- [ ] Dashboard: rating / review distribution
- [ ] Dashboard: brand concentration
- [ ] Dashboard: head effect analysis
- [ ] Report cache by keyword + marketplace + locale

## Phase 2 - VOC and Listing Draft

Target: 把競品分析轉化成可操作的 Amazon Listing Draft。

- [ ] Top 20 product deep dive
- [ ] Bullet points extraction
- [ ] Low-star review extraction
- [ ] Buyer Q&A extraction
- [ ] LLM VOC analysis
- [ ] Pain points summary
- [ ] Selling points summary
- [ ] User product input / upload
- [ ] Gap analysis
- [ ] AI title generation
- [ ] AI bullet generation
- [ ] AI description generation
- [ ] Backend search term suggestions
- [ ] Amazon listing draft schema
- [ ] Draft editor UI

## Phase 3 - Amazon SP-API Validation

Target: 串接 Amazon seller account，讓 draft 可以做 validation preview。

- [ ] Amazon OAuth flow
- [ ] Encrypted token storage
- [ ] Seller account / marketplace storage
- [ ] Product Type Definitions API adapter
- [ ] Product type selection
- [ ] Required attributes mapping
- [ ] Local schema validation
- [ ] Listings Items API validation preview
- [ ] Validation issues UI
- [ ] Draft revision loop
- [ ] Audit log for SP-API requests

## Later Phases

暫時不排入 MVP：

- TikTok Shop publishing
- eBay publishing
- Multi-platform category mapping
- TikTok creator video / subtitle analysis
- Advanced inventory sync
- Order management
- ERP / warehouse integration
