from __future__ import annotations

import asyncio
import math
import re
from collections import Counter
from typing import Any
from urllib.parse import quote_plus

from apify_client import ApifyClient

from app.core.config import get_settings


def _parse_price(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict):
        for key in ("value", "amount", "price", "raw", "text"):
            parsed = _parse_price(value.get(key))
            if parsed is not None:
                return parsed
        return None
    if isinstance(value, str):
        match = re.search(r"(\d+(?:\.\d+)?)", value.replace(",", ""))
        if match:
            return float(match.group(1))
    return None


def _parse_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        match = re.search(r"(\d+)", value.replace(",", ""))
        if match:
            return int(match.group(1))
    return None


def _proxy_country_for_locale(locale: str) -> str:
    normalized = (locale or "US").upper()
    allowed = {
        "US",
        "CA",
        "GB",
        "DE",
        "FR",
        "ES",
        "IT",
        "NL",
        "SE",
        "PL",
        "JP",
        "AU",
        "IN",
        "MX",
        "BR",
        "AE",
        "SA",
        "SG",
    }
    return normalized if normalized in allowed else "US"


def _parse_bsr(item: dict[str, Any], fallback: int) -> int:
    direct_value = item.get("bsr") or item.get("bestSellerRank") or item.get("rank")
    parsed_direct = _parse_int(direct_value)
    if parsed_direct is not None:
        return parsed_direct

    ranks = item.get("bestsellerRanks")
    candidates = ranks if isinstance(ranks, list) else [ranks]
    for candidate in candidates:
        if isinstance(candidate, dict):
            candidate = candidate.get("rank") or candidate.get("value") or candidate.get("name")
        parsed_rank = _parse_int(candidate)
        if parsed_rank is not None:
            return parsed_rank

    return fallback


def _normalize_item(item: dict[str, Any], rank: int, marketplace: str) -> dict[str, Any]:
    asin = (
        item.get("asin")
        or item.get("productAsin")
        or item.get("id")
        or item.get("sku")
        or item.get("productId")
        or ""
    )
    title = item.get("title") or item.get("name") or item.get("productTitle") or f"Product {rank}"
    product_url = (
        item.get("url")
        or item.get("productUrl")
        or item.get("product_url")
        or (f"https://www.amazon.com/dp/{asin}" if asin else "")
    )
    price = _parse_price(
        item.get("price")
        or item.get("currentPrice")
        or item.get("buyBoxPrice")
        or item.get("listingPrice")
    )
    brand = item.get("brand") or item.get("manufacturer") or ""
    rating = _parse_price(item.get("stars") or item.get("rating") or item.get("averageRating"))
    review_count = _parse_int(
        item.get("reviewsCount")
        or item.get("reviewCount")
        or item.get("ratingCount")
        or item.get("reviews_count")
    ) or 0
    bsr = _parse_bsr(item, rank)
    image_url = (
        item.get("imageUrl")
        or item.get("image_url")
        or item.get("mainImage")
        or item.get("thumbnailImage")
        or ""
    )

    return {
        "asin": str(asin),
        "title": str(title),
        "product_url": str(product_url),
        "brand": str(brand),
        "rating": rating,
        "price": price,
        "bsr": bsr,
        "review_count": review_count,
        "image_url": str(image_url),
        "is_amazon_choice": bool(item.get("isAmazonChoice") or item.get("amazonChoiceText")),
        "amazon_choice_text": item.get("amazonChoiceText"),
        "monthly_purchase_volume": item.get("monthlyPurchaseVolume"),
        "marketplace": marketplace,
        "raw": item,
    }


def _build_price_distribution(prices: list[float]) -> list[dict[str, Any]]:
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

    distribution: list[dict[str, Any]] = []
    for label, lower, upper in buckets:
        if upper is None:
            count = sum(1 for price in prices if price >= lower)
        else:
            count = sum(1 for price in prices if lower <= price < upper)
        distribution.append({"bucket": label, "count": count})
    return distribution


class ApifyAmazonScraperService:
    def __init__(
        self,
        api_token: str | None = None,
        actor_id: str | None = None,
        debug_mode: bool | None = None,
        timeout_seconds: int | None = None,
    ) -> None:
        settings = get_settings()
        self.api_token = api_token if api_token is not None else settings.apify_api_token
        self.actor_id = actor_id if actor_id is not None else settings.apify_amazon_scraper_actor_id
        self.debug_mode = settings.debug_mode if debug_mode is None else debug_mode
        self.timeout_seconds = timeout_seconds if timeout_seconds is not None else settings.apify_timeout_seconds

    @property
    def is_configured(self) -> bool:
        return bool(self.api_token and self.actor_id)

    def _build_run_input(self, keyword: str, locale: str, limit: int) -> dict[str, Any]:
        run_limit = 10 if self.debug_mode else min(limit, 50)
        max_search_pages = max(1, min(5, math.ceil(run_limit / 48)))
        search_url = f"https://www.amazon.com/s?k={quote_plus(keyword)}"
        return {
            "categoryOrProductUrls": [{"url": search_url}],
            "maxItemsPerStartUrl": run_limit,
            "maxSearchPagesPerStartUrl": max_search_pages,
            "scrapeProductDetails": True,
            "proxyCountry": _proxy_country_for_locale(locale),
        }

    async def search_top_products(self, keyword: str, locale: str = "US", limit: int = 200) -> list[dict[str, Any]]:
        if not self.is_configured:
            raise RuntimeError("Live data source is not configured")

        limit = min(limit, 50)
        run_input = self._build_run_input(keyword=keyword, locale=locale, limit=limit)

        def _run() -> list[dict[str, Any]]:
            client = ApifyClient(
                self.api_token,
                max_retries=2,
                timeout_secs=self.timeout_seconds,
            )
            run = client.actor(self.actor_id).call(run_input=run_input)
            dataset_id = run.get("defaultDatasetId") if isinstance(run, dict) else getattr(run, "default_dataset_id", None)
            if not dataset_id:
                return []
            dataset = client.dataset(dataset_id)
            return list(dataset.iterate_items())

        raw_items = await asyncio.wait_for(
            asyncio.to_thread(_run),
            timeout=self.timeout_seconds + 15,
        )
        normalized = [_normalize_item(item, index + 1, "amazon") for index, item in enumerate(raw_items)]
        return normalized[: (10 if self.debug_mode else limit)]

    @staticmethod
    def build_report(keyword: str, locale: str, top_n: int, products: list[dict[str, Any]]) -> dict[str, Any]:
        prices = [item["price"] for item in products if isinstance(item.get("price"), (int, float))]
        review_total = sum(int(item.get("review_count") or 0) for item in products)
        ratings = [item["rating"] for item in products if isinstance(item.get("rating"), (int, float))]
        brand_counts = Counter(item.get("brand") for item in products if item.get("brand"))
        top_brand = brand_counts.most_common(1)
        top_competitors = [
            {
                "rank": index + 1,
                "asin": item["asin"],
                "title": item["title"],
                "product_url": item.get("product_url"),
                "brand": item.get("brand"),
                "rating": item.get("rating"),
                "price": item["price"],
                "bsr": item["bsr"],
                "review_count": item["review_count"],
                "image_url": item["image_url"],
                "is_amazon_choice": item.get("is_amazon_choice", False),
                "amazon_choice_text": item.get("amazon_choice_text"),
                "monthly_purchase_volume": item.get("monthly_purchase_volume"),
            }
            for index, item in enumerate(products)
        ]

        title_tokens = Counter(
            token.lower()
            for item in products[:20]
            for token in re.findall(r"[A-Za-z0-9]+", item["title"])
            if len(token) > 2
        )

        return {
            "summary": {
                "keyword": keyword,
                "platform": "amazon",
                "locale": locale,
                "top_n": top_n,
            },
            "metrics": {
                "product_count": len(products),
                "price_min": round(min(prices), 2) if prices else None,
                "price_median": round(sorted(prices)[len(prices) // 2], 2) if prices else None,
                "price_max": round(max(prices), 2) if prices else None,
                "avg_rating": round(sum(ratings) / len(ratings), 2) if ratings else None,
                "review_total": review_total,
                "top_brand_share": round(top_brand[0][1] / len(products), 2) if top_brand else None,
            },
            "price_distribution": _build_price_distribution(prices),
            "top_competitors": top_competitors,
            "voc": {
                "pain_points": [
                    "搜索报告基于公开搜索结果信号；评论和问答 VOC 需要单独做深度抓取。",
                ],
                "selling_points": [
                    "价格、评分、评论数、品牌、图片、ASIN 和商品链接会从实时采集中统一整理。",
                ],
                "visual_style": [
                    "Top 20 竞品卡片",
                    "Top 50 市场筛选",
                ],
            },
            "recommendation": {
                "suggested_price": round(sorted(prices)[len(prices) // 2], 2) if prices else None,
                "positioning": "基于 Amazon 搜索结果的市场定位",
                "listing_focus": [token for token, _ in title_tokens.most_common(5)],
            },
            "source": "live_data",
        }
