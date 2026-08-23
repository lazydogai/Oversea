from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from app.core.config import get_settings
from app.services.apify_service import ApifyAmazonScraperService
from app.services.llm_adapter import MockLLMAdapter
from app.services.scraper_adapter import MockScraper

SCRAPER = MockScraper()
LLM = MockLLMAdapter()
APIFY = ApifyAmazonScraperService()
SETTINGS = get_settings()

MOCK_JOBS: dict[UUID, dict[str, Any]] = {}
MAX_SEARCH_TOP_N = 50
SNAPSHOT_PATH = Path(__file__).resolve().parents[3] / "preview" / "crawl-sample.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _base_report(keyword: str, platform: str, locale: str, top_n: int) -> dict[str, Any]:
    return {
        "summary": {
            "keyword": keyword,
            "platform": platform,
            "locale": locale,
            "top_n": top_n,
        },
        "metrics": {
            "product_count": 0,
            "price_min": None,
            "price_median": None,
            "price_max": None,
            "avg_rating": None,
            "review_total": 0,
            "top_brand_share": None,
        },
        "price_distribution": [],
        "top_competitors": [],
        "voc": {
            "pain_points": [],
            "selling_points": [],
            "visual_style": [],
        },
        "recommendation": {
            "suggested_price": None,
            "positioning": "pending",
            "listing_focus": [],
        },
    }


def _create_job(keyword: str, platform: str = "amazon", locale: str = "US", top_n: int = 50) -> dict[str, Any]:
    job_id = uuid4()
    job = {
        "job_id": str(job_id),
        "status": "queued",
        "progress": 0,
        "keyword": keyword,
        "platform": platform,
        "locale": locale,
        "top_n": top_n,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "report": None,
        "error_message": None,
    }
    MOCK_JOBS[job_id] = job
    asyncio.create_task(_run_job(job_id))
    return job


def create_mock_job(keyword: str, platform: str = "amazon", locale: str = "US", top_n: int = 50) -> dict[str, Any]:
    return _create_job(keyword=keyword, platform=platform, locale=locale, top_n=top_n)


def create_apify_job(keyword: str, platform: str = "amazon", locale: str = "US", top_n: int = 50) -> dict[str, Any]:
    return _create_job(keyword=keyword, platform=platform, locale=locale, top_n=top_n)


def create_search_job(keyword: str, platform: str = "amazon", locale: str = "US", top_n: int = 50) -> dict[str, Any]:
    top_n = min(top_n, MAX_SEARCH_TOP_N)
    if SETTINGS.use_live_apify and not SETTINGS.debug_mode and APIFY.is_configured and top_n <= MAX_SEARCH_TOP_N:
        return create_apify_job(keyword=keyword, platform=platform, locale=locale, top_n=top_n)
    return create_mock_job(keyword=keyword, platform=platform, locale=locale, top_n=top_n)


async def _run_job(job_id: UUID) -> None:
    job = MOCK_JOBS.get(job_id)
    if job is None:
        return

    try:
        job["status"] = "running"
        job["progress"] = 0
        job["updated_at"] = _now_iso()

        await asyncio.sleep(1)
        job["progress"] = 50
        job["updated_at"] = _now_iso()

        if SETTINGS.use_live_apify:
            if SETTINGS.debug_mode:
                raise RuntimeError("Live data source is disabled while DEBUG_MODE is enabled")
            if not APIFY.is_configured:
                raise RuntimeError("Live data source is enabled but credentials are not configured")
            try:
                products = await APIFY.search_top_products(job["keyword"], job["locale"], job["top_n"])
                report = APIFY.build_report(job["keyword"], job["locale"], job["top_n"], products)
            except Exception as exc:  # noqa: BLE001
                if not _can_use_snapshot_fallback(job, exc):
                    raise
                products = _load_snapshot_products(job["top_n"])
                report = APIFY.build_report(job["keyword"], job["locale"], job["top_n"], products)
                report["source"] = "cached_snapshot"
                report["fallback_reason"] = "实时数据源额度限制，已切换到数据快照"
                report["recommendation"]["positioning"] = "演示环境数据快照"
        else:
            raw_products = SCRAPER.search_top_products(job["keyword"], job["platform"], job["top_n"])
            voc = LLM.analyze_voc(raw_products[:20])
            report = _build_mock_report(job, raw_products, voc)

        job["report"] = report
        job["status"] = "completed"
        job["progress"] = 100
        job["updated_at"] = _now_iso()
    except Exception as exc:  # noqa: BLE001
        job["status"] = "failed"
        job["progress"] = 100
        job["error_message"] = str(exc)
        job["updated_at"] = _now_iso()


def _can_use_snapshot_fallback(job: dict[str, Any], error: Exception) -> bool:
    expected_keyword = SETTINGS.apify_snapshot_keyword.strip().casefold()
    actual_keyword = str(job.get("keyword") or "").strip().casefold()
    return (
        SETTINGS.apify_snapshot_fallback
        and actual_keyword == expected_keyword
        and "monthly usage hard limit exceeded" in str(error).casefold()
        and SNAPSHOT_PATH.exists()
    )


def _load_snapshot_products(limit: int) -> list[dict[str, Any]]:
    rows = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    products: list[dict[str, Any]] = []
    for index, row in enumerate(rows[:limit], start=1):
        ranks = row.get("bestsellerRanks") or []
        first_rank = ranks[0].get("rank") if ranks and isinstance(ranks[0], dict) else index
        products.append(
            {
                "asin": str(row.get("asin") or ""),
                "title": str(row.get("title") or f"Product {index}"),
                "product_url": str(row.get("url") or ""),
                "brand": str(row.get("brand") or ""),
                "rating": row.get("stars"),
                "price": row.get("price"),
                "bsr": first_rank,
                "review_count": row.get("reviewsCount") or 0,
                "image_url": str(row.get("thumbnailImage") or ""),
                "is_amazon_choice": bool(row.get("isAmazonChoice") or row.get("amazonChoiceText")),
                "amazon_choice_text": row.get("amazonChoiceText"),
                "monthly_purchase_volume": row.get("monthlyPurchaseVolume"),
            }
        )
    return products


def _build_mock_report(job: dict[str, Any], raw_products: list[dict[str, Any]], voc: dict[str, Any]) -> dict[str, Any]:
    prices = [item["price"] for item in raw_products if isinstance(item.get("price"), (int, float))]
    top_competitors = [
        {
            "rank": index + 1,
            "asin": item["asin"],
            "title": item["title"],
            "price": item["price"],
            "bsr": item["bsr"],
            "review_count": item["review_count"],
            "image_url": item["image_url"],
        }
        for index, item in enumerate(raw_products)
    ]
    return {
        **_base_report(job["keyword"], job["platform"], job["locale"], job["top_n"]),
        "metrics": {
            "product_count": len(raw_products),
            "price_min": round(min(prices), 2) if prices else None,
            "price_median": round(sorted(prices)[len(prices) // 2], 2) if prices else None,
            "price_max": round(max(prices), 2) if prices else None,
            "avg_rating": 4.4,
            "review_total": sum(int(item.get("review_count") or 0) for item in raw_products),
            "top_brand_share": 0.31,
        },
        "price_distribution": [
            {"bucket": "$0-$15", "count": 18},
            {"bucket": "$15-$20", "count": 29},
            {"bucket": "$20-$25", "count": 36},
            {"bucket": "$25-$30", "count": 41},
            {"bucket": "$30-$40", "count": 35},
            {"bucket": "$40-$50", "count": 22},
            {"bucket": "$50-$70", "count": 12},
            {"bucket": "$70+", "count": 7},
        ],
        "top_competitors": top_competitors,
        "voc": voc,
        "recommendation": {
            "suggested_price": round(sorted(prices)[len(prices) // 2], 2) if prices else None,
            "positioning": "中高端办公照明",
            "listing_focus": [
                "稳定性",
                "手感按键",
                "阅读场景亮度控制",
            ],
        },
        "source": "mock",
    }


def get_mock_job(job_id: UUID) -> dict[str, Any] | None:
    return MOCK_JOBS.get(job_id)
