from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from app.services.apify_service import ApifyAmazonScraperService

APIFY = ApifyAmazonScraperService(debug_mode=False)
JOBS: dict[UUID, dict[str, Any]] = {}
MAX_SEARCH_TOP_N = 50


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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
    JOBS[job_id] = job
    asyncio.create_task(_run_job(job_id))
    return job


def create_apify_job(keyword: str, platform: str = "amazon", locale: str = "US", top_n: int = 50) -> dict[str, Any]:
    return _create_job(keyword=keyword, platform=platform, locale=locale, top_n=top_n)


def create_search_job(keyword: str, platform: str = "amazon", locale: str = "US", top_n: int = 50) -> dict[str, Any]:
    return create_apify_job(
        keyword=keyword,
        platform=platform,
        locale=locale,
        top_n=min(top_n, MAX_SEARCH_TOP_N),
    )


async def _run_job(job_id: UUID) -> None:
    job = JOBS.get(job_id)
    if job is None:
        return

    try:
        job["status"] = "running"
        job["progress"] = 10
        job["updated_at"] = _now_iso()

        if not APIFY.is_configured:
            raise RuntimeError("实时数据源未配置，请检查服务器环境变量。")

        products = await APIFY.search_top_products(job["keyword"], job["locale"], job["top_n"])
        if not products:
            raise RuntimeError("实时数据源没有返回商品结果。")
        job["progress"] = 90
        job["updated_at"] = _now_iso()
        job["report"] = APIFY.build_report(job["keyword"], job["locale"], job["top_n"], products)
        job["status"] = "completed"
        job["progress"] = 100
        job["updated_at"] = _now_iso()
    except Exception as exc:  # noqa: BLE001
        job["status"] = "failed"
        job["progress"] = 100
        job["error_message"] = str(exc)
        job["updated_at"] = _now_iso()


def get_mock_job(job_id: UUID) -> dict[str, Any] | None:
    return JOBS.get(job_id)