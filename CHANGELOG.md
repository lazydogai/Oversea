# CHANGELOG.md

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added

- Created project direction file `AGENT.md`.
- Created compatibility pointer `AGENTS.md`.
- Created MVP roadmap in `ROADMAP.md`.
- Created product and engineering backlog in `BACKLOG.md`.
- Created environment templates `.env` and `.env.example`.
- Added initial backend and frontend skeleton.
- Added Docker Compose for PostgreSQL and Redis.
- Added FastAPI health/report endpoints and Amazon service stubs.
- Added Next.js dashboard shell for reports and drafts.
- Added static preview page for the Amazon MVP skeleton.
- Added mock pipeline job endpoints and polling-ready frontend.
- Added Apify scraper service scaffold with debug-mode switching and normalized Amazon fetch output.
- Fixed backend root `.env` loading and added compatibility for the existing Apify environment variable names.
- Added bounded Apify request timeout and retry behavior so live jobs cannot wait indefinitely.
- Updated Apify Amazon actor input to use `categoryOrProductUrls` search URLs.
- Set the default Apify timeout to 240 seconds for the expected long-running crawl window.
- Mapped the live Amazon crawler fields `bestsellerRanks` and `thumbnailImage` into the normalized product model.
- Verified a live Apify run completed successfully and returned 287 raw dataset records before adapter limiting.
- Verified the FastAPI mock polling flow completed with 200 normalized products.
- Added a backend-connected HTML preview that creates and polls Amazon analysis jobs.
- Added `USE_LIVE_APIFY` so local previews stay on mock data unless live Apify is explicitly enabled.
- Restored the preview default to V1 backend-connected API mode and removed the fake demo delay path.
- Added a Market Report V1 preview using the real Apify crawl dataset with KPI cards, price/rating/brand distributions, opportunity segments, and filters for rating, price, review count, brand, and Amazon Choice.
- Fixed Market Report V1 chart rendering so distribution bars show filled values and the overview price chart includes bucket labels and counts.
- Switched the V1 live search scope from Top 200/Top 20 gating to a hard Top 50 Apify crawl, with the report retaining all returned rows while the UI keeps Top 20 competitor cards.
- Added an explicit `desk lamp` cached Apify snapshot fallback for the demo environment when Apify monthly quota is exhausted; the report labels the source instead of presenting it as live.
- Fixed live Apify price normalization for object-shaped price fields such as `{ value, currency }`, so report price metrics and filters receive numeric prices.
- Localized the preview and Next.js shell to Simplified Chinese and replaced user-facing scraper vendor labels with neutral data-source wording for Vercel demos.

### Decisions

- MVP scope is Amazon only.
- First workflow is Amazon keyword search analysis + Amazon Listing Draft validation.
- TikTok Shop, eBay, and multi-platform publishing are postponed.
- Amazon competitor search will use scraper / Apify first.
- Amazon listing validation will use SP-API Product Type Definitions and Listings Items validation preview.
