from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.services.apify_service import ApifyAmazonScraperService

MAX_TOP_N = 50


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _read_payload(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("content-length") or "0")
    if length <= 0:
        return {}
    raw = handler.rfile.read(length)
    return json.loads(raw.decode("utf-8"))


def _price_distribution(prices: list[float]) -> list[dict[str, Any]]:
    buckets = [
        ("$0-$15", 0, 15),
        ("$15-$20", 15, 20),
        ("$20-$25", 20, 25),
        ("$25-$30", 25, 30),
        ("$30-$40", 30, 40),
        ("$40-$50", 40, 50),
        ("$50-$70", 50, 70),
        ("$70+", 70, None),
    ]
    result = []
    for label, lower, upper in buckets:
        if upper is None:
            count = sum(1 for price in prices if price >= lower)
        else:
            count = sum(1 for price in prices if lower <= price < upper)
        result.append({"bucket": label, "count": count})
    return result


def _completed_job(keyword: str, platform: str, locale: str, top_n: int) -> dict[str, Any]:
    scraper = ApifyAmazonScraperService(debug_mode=False)
    if not scraper.is_configured:
        raise RuntimeError("实时数据源未配置，缺少：" + "、".join(scraper.missing_config))

    products = asyncio.run(scraper.search_top_products(keyword, locale, top_n))
    if not products:
        raise RuntimeError("实时数据源没有返回商品结果。")
    report = scraper.build_report(keyword, locale, top_n, products)
    now = _now_iso()
    return {
        "job_id": str(uuid4()),
        "status": "completed",
        "progress": 100,
        "keyword": keyword,
        "platform": platform,
        "locale": locale,
        "top_n": top_n,
        "created_at": now,
        "updated_at": now,
        "error_message": None,
        "report": report,
    }

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self) -> None:
        _json_response(self, 200, {"ok": True})

    def do_POST(self) -> None:
        try:
            payload = _read_payload(self)
            keyword = str(payload.get("keyword") or "").strip()
            if not keyword:
                _json_response(self, 400, {"error": "keyword is required"})
                return

            platform = str(payload.get("platform") or "amazon")
            locale = str(payload.get("locale") or "US")
            top_n = min(max(int(payload.get("top_n") or 50), 1), MAX_TOP_N)
            _json_response(self, 200, _completed_job(keyword, platform, locale, top_n))
        except RuntimeError as exc:
            message = str(exc)
            status = 503 if "未配置" in message else 502
            _json_response(self, status, {"status": "failed", "error_message": message, "error": message})
        except Exception as exc:  # noqa: BLE001
            _json_response(self, 502, {"status": "failed", "error_message": "实时数据采集失败，请稍后重试。", "error": str(exc)})
