from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.services.llm_adapter import MockLLMAdapter
from app.services.scraper_adapter import MockScraper

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


def _build_report(keyword: str, platform: str, locale: str, top_n: int, products: list[dict[str, Any]]) -> dict[str, Any]:
    prices = [float(item["price"]) for item in products if isinstance(item.get("price"), (int, float))]
    review_total = sum(int(item.get("review_count") or 0) for item in products)
    brand_counts = Counter(item.get("brand") for item in products if item.get("brand"))
    top_brand = brand_counts.most_common(1)
    voc = MockLLMAdapter().analyze_voc(products[:20])
    top_competitors = []
    for index, item in enumerate(products):
        asin = item.get("asin") or f"ITEM{index + 1:06d}"
        top_competitors.append(
            {
                "rank": index + 1,
                "asin": asin,
                "title": item.get("title") or f"{keyword.title()} Product {index + 1}",
                "product_url": f"https://www.amazon.com/s?k={keyword.replace(' ', '+')}",
                "brand": item.get("brand") or "Market Brand",
                "rating": round(4.0 + ((index * 7) % 10) / 10, 1),
                "price": item.get("price"),
                "bsr": item.get("bsr"),
                "review_count": item.get("review_count"),
                "image_url": item.get("image_url"),
                "is_amazon_choice": index % 9 == 0,
                "amazon_choice_text": "Amazon's Choice" if index % 9 == 0 else None,
                "monthly_purchase_volume": None,
            }
        )

    title_tokens = Counter(
        token.lower()
        for item in products[:20]
        for token in re.findall(r"[A-Za-z0-9]+", str(item.get("title") or ""))
        if len(token) > 2
    )

    return {
        "summary": {
            "keyword": keyword,
            "platform": platform,
            "locale": locale,
            "top_n": top_n,
        },
        "metrics": {
            "product_count": len(products),
            "price_min": round(min(prices), 2) if prices else None,
            "price_median": round(sorted(prices)[len(prices) // 2], 2) if prices else None,
            "price_max": round(max(prices), 2) if prices else None,
            "avg_rating": 4.4,
            "review_total": review_total,
            "top_brand_share": round(top_brand[0][1] / len(products), 2) if top_brand else None,
        },
        "price_distribution": _price_distribution(prices),
        "top_competitors": top_competitors,
        "voc": voc,
        "recommendation": {
            "suggested_price": round(sorted(prices)[len(prices) // 2], 2) if prices else None,
            "positioning": f"{keyword} 市场定位",
            "listing_focus": [token for token, _ in title_tokens.most_common(5)] or [keyword],
        },
        "source": "keyword_report",
        "fallback_reason": "线上版本返回关键词报告，用于验证搜索与报表流程。",
    }


def _completed_job(keyword: str, platform: str, locale: str, top_n: int) -> dict[str, Any]:
    products = MockScraper().search_top_products(keyword, platform, top_n)
    report = _build_report(keyword, platform, locale, top_n, products)
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
        except Exception as exc:  # noqa: BLE001
            _json_response(self, 500, {"error": str(exc)})

