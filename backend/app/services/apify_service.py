from __future__ import annotations

import asyncio
import inspect
import math
import re
from collections import Counter
from typing import Any
from urllib.parse import quote_plus

from apify_client import ApifyClient

from app.core.config import get_settings

SUPPORTED_PLATFORMS = {"amazon", "taobao"}
TAOBAO_DEFAULT_ACTOR_ID = "zen-studio/taobao-search-scraper"

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


def _normalize_platform(platform: str) -> str:
    normalized = (platform or "amazon").strip().lower()
    if normalized in {"taobao", "tmall", "tao"}:
        return "taobao"
    return "amazon"


def _currency_for_platform(platform: str) -> tuple[str, str]:
    return ("CNY", "¥") if _normalize_platform(platform) == "taobao" else ("USD", "$")


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
    normalized_marketplace = _normalize_platform(marketplace)
    search = item.get("search") if isinstance(item.get("search"), dict) else {}
    shop = item.get("shop") if isinstance(item.get("shop"), dict) else {}
    asin = (
        item.get("asin")
        or item.get("productAsin")
        or item.get("sku")
        or (item.get("productId") if normalized_marketplace == "amazon" else "")
        or ""
    )
    item_id = item.get("itemId") or search.get("itemId") or item.get("productId") or item.get("id") or item.get("sku") or ""
    title = (
        item.get("title")
        or item.get("titleOriginal")
        or item.get("name")
        or item.get("productTitle")
        or search.get("itemName")
        or f"Product {rank}"
    )
    if normalized_marketplace == "taobao":
        product_url = (
            item.get("url")
            or item.get("productUrl")
            or item.get("product_url")
            or item.get("itemUrl")
            or item.get("detailUrl")
            or (f"https://item.taobao.com/item.htm?id={item_id}" if item_id else "")
        )
    else:
        product_url = (
            item.get("url")
            or item.get("productUrl")
            or item.get("product_url")
            or (f"https://www.amazon.com/dp/{asin}" if asin else "")
        )
    shop_name = str(
        item.get("shopName")
        or item.get("sellerName")
        or item.get("storeName")
        or item.get("shop_name")
        or item.get("seller")
        or shop.get("shopName")
        or shop.get("shopNameFromSearch")
        or shop.get("sellerNick")
        or ""
    )
    shop_url = str(item.get("shopUrl") or item.get("sellerUrl") or item.get("shop_url") or shop.get("shopUrl") or "")
    price = _parse_price(
        item.get("price")
        or item.get("currentPrice")
        or item.get("buyBoxPrice")
        or item.get("listingPrice")
        or item.get("discountedPriceFromSearch")
        or item.get("priceFromSearch")
        or item.get("originalPrice")
        or search.get("discntPriceYuan")
        or search.get("priceYuan")
    )
    brand = item.get("brand") or item.get("brandName") or item.get("manufacturer") or shop_name or ""
    rating = _parse_price(
        item.get("stars")
        or item.get("rating")
        or item.get("averageRating")
        or item.get("shopRating")
        or item.get("itemGradeAvg")
        or search.get("itemGradeAvg")
    )
    review_count = _parse_int(
        item.get("reviewsCount")
        or item.get("reviewCount")
        or item.get("ratingCount")
        or item.get("reviews_count")
        or item.get("commentCount")
        or item.get("commentsCount")
        or search.get("commentCount")
    ) or 0
    bsr = _parse_bsr(item, rank)
    pictures = item.get("pictures") if isinstance(item.get("pictures"), list) else []
    image_url = (
        item.get("imageUrl")
        or item.get("image_url")
        or item.get("mainImage")
        or item.get("thumbnailImage")
        or item.get("mainPictureUrl")
        or item.get("picUrlFull")
        or search.get("picUrlFull")
        or (pictures[0] if pictures else "")
        or ""
    )
    monthly_purchase_volume = (
        item.get("monthlyPurchaseVolume")
        or item.get("salesSignal")
        or item.get("sales")
        or item.get("totalSold")
        or item.get("monthlySales")
        or search.get("orderPayUV")
    )

    return {
        "asin": str(asin),
        "item_id": str(item_id),
        "title": str(title),
        "product_url": str(product_url),
        "brand": str(brand),
        "shop_name": shop_name,
        "shop_url": shop_url,
        "rating": rating,
        "price": price,
        "bsr": bsr,
        "review_count": review_count,
        "image_url": str(image_url),
        "is_amazon_choice": bool(item.get("isAmazonChoice") or item.get("amazonChoiceText")),
        "amazon_choice_text": item.get("amazonChoiceText"),
        "monthly_purchase_volume": monthly_purchase_volume,
        "marketplace": normalized_marketplace,
        "raw": item,
    }

def _build_price_distribution(prices: list[float], currency_symbol: str = "$") -> list[dict[str, Any]]:
    buckets = [
        (f"{currency_symbol}0-{currency_symbol}15", 0, 15),
        (f"{currency_symbol}15-{currency_symbol}20", 15, 20),
        (f"{currency_symbol}20-{currency_symbol}25", 20, 25),
        (f"{currency_symbol}25-{currency_symbol}30", 25, 30),
        (f"{currency_symbol}30-{currency_symbol}40", 30, 40),
        (f"{currency_symbol}40-{currency_symbol}50", 40, 50),
        (f"{currency_symbol}50-{currency_symbol}70", 50, 70),
        (f"{currency_symbol}70+", 70, None),
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
        self.taobao_actor_id = settings.apify_taobao_search_actor_id or TAOBAO_DEFAULT_ACTOR_ID
        self.debug_mode = settings.debug_mode if debug_mode is None else debug_mode
        self.timeout_seconds = timeout_seconds if timeout_seconds is not None else settings.apify_timeout_seconds

    def actor_id_for_platform(self, platform: str) -> str | None:
        normalized = _normalize_platform(platform)
        if normalized == "taobao":
            return self.taobao_actor_id
        return self.actor_id

    def missing_config_for(self, platform: str) -> list[str]:
        missing: list[str] = []
        if not self.api_token:
            missing.append("APIFY_API_TOKEN 或 APIFY_TOKEN")
        normalized = _normalize_platform(platform)
        actor_id = self.actor_id_for_platform(normalized)
        if not actor_id:
            if normalized == "taobao":
                missing.append("APIFY_TAOBAO_SEARCH_ACTOR")
            else:
                missing.append("APIFY_AMAZON_SCRAPER_ACTOR_ID 或 APIFY_AMAZON_SEARCH_ACTOR")
        return missing

    @property
    def missing_config(self) -> list[str]:
        return self.missing_config_for("amazon")

    def is_configured_for(self, platform: str) -> bool:
        return not self.missing_config_for(platform)

    @property
    def is_configured(self) -> bool:
        return self.is_configured_for("amazon")

    def _build_run_input(self, keyword: str, locale: str, limit: int, platform: str) -> dict[str, Any]:
        normalized_platform = _normalize_platform(platform)
        run_limit = 10 if self.debug_mode else min(limit, 50)
        if normalized_platform == "taobao":
            run_limit = max(10, run_limit)
            return {
                "keyword": keyword,
                "maxItems": run_limit,
                "enrichWithDetails": False,
                "fetchReviews": False,
            }
        max_search_pages = max(1, min(5, math.ceil(run_limit / 48)))
        search_url = f"https://www.amazon.com/s?k={quote_plus(keyword)}"
        return {
            "categoryOrProductUrls": [{"url": search_url}],
            "maxItemsPerStartUrl": run_limit,
            "maxSearchPagesPerStartUrl": max_search_pages,
            "scrapeProductDetails": True,
            "proxyCountry": _proxy_country_for_locale(locale),
        }

    async def search_top_products(self, keyword: str, locale: str = "US", limit: int = 200, platform: str = "amazon") -> list[dict[str, Any]]:
        normalized_platform = _normalize_platform(platform)
        if not self.is_configured_for(normalized_platform):
            raise RuntimeError("Live data source is not configured")

        limit = min(limit, 50)
        run_input = self._build_run_input(keyword=keyword, locale=locale, limit=limit, platform=normalized_platform)
        actor_id = self.actor_id_for_platform(normalized_platform)
        if not actor_id:
            raise RuntimeError("Live data source actor is not configured")

        def _run() -> list[dict[str, Any]]:
            # Keep optional constructor arguments compatible with the deployed SDK version.
            supported_kwargs = inspect.signature(ApifyClient).parameters
            client_kwargs: dict[str, Any] = {}
            if "max_retries" in supported_kwargs:
                client_kwargs["max_retries"] = 2
            if "timeout_secs" in supported_kwargs:
                client_kwargs["timeout_secs"] = self.timeout_seconds
            client = ApifyClient(self.api_token, **client_kwargs)
            run = client.actor(actor_id).call(run_input=run_input)
            dataset_id = run.get("defaultDatasetId") if isinstance(run, dict) else getattr(run, "default_dataset_id", None)
            if not dataset_id:
                return []
            dataset = client.dataset(dataset_id)
            return list(dataset.iterate_items())

        raw_items = await asyncio.wait_for(
            asyncio.to_thread(_run),
            timeout=self.timeout_seconds + 15,
        )
        normalized = [_normalize_item(item, index + 1, normalized_platform) for index, item in enumerate(raw_items)]
        return normalized[: (10 if self.debug_mode else limit)]

    @staticmethod
    def build_report(
        keyword: str,
        locale: str,
        top_n: int,
        products: list[dict[str, Any]],
        platform: str = "amazon",
        report_lang: str = "zh",
    ) -> dict[str, Any]:
        from app.services.llm_adapter import _normalize_report_lang, get_llm_adapter

        normalized_platform = _normalize_platform(platform)
        lang = _normalize_report_lang(report_lang)
        currency_code, currency_symbol = _currency_for_platform(normalized_platform)
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
                "shop_name": item.get("shop_name"),
                "shop_url": item.get("shop_url"),
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
            for token in re.findall(r"[A-Za-z0-9\u4e00-\u9fff]+", item["title"])
            if len(token) > 1
        )
        median_price = round(sorted(prices)[len(prices) // 2], 2) if prices else None
        metrics = {
            "product_count": len(products),
            "price_min": round(min(prices), 2) if prices else None,
            "price_median": median_price,
            "price_max": round(max(prices), 2) if prices else None,
            "avg_rating": round(sum(ratings) / len(ratings), 2) if ratings else None,
            "review_total": review_total,
            "top_brand_share": round(top_brand[0][1] / len(products), 2) if top_brand else None,
            "currency_symbol": currency_symbol,
        }

        llm = get_llm_adapter()
        enrichment = llm.enrich_report(
            keyword=keyword,
            platform=normalized_platform,
            products=products,
            metrics=metrics,
            report_lang=lang,
        )
        source_tag = str(enrichment.get("_source") or "fallback")
        if source_tag not in {"openrouter", "fallback", "mock"}:
            source_tag = "fallback"

        listing_focus = enrichment.get("listing_focus") or [token for token, _ in title_tokens.most_common(5)]
        suggested_price = enrichment.get("suggested_price")
        if suggested_price is None:
            suggested_price = median_price

        report_markdown = enrichment.get("report_markdown") or ""
        if not str(report_markdown).strip():
            from app.services.llm_adapter import _build_deterministic_report_markdown

            report_markdown = _build_deterministic_report_markdown(
                keyword=keyword,
                platform=normalized_platform,
                products=products,
                metrics=metrics,
                report_lang=lang,
                llm_source=source_tag,
            )

        return {
            "summary": {
                "keyword": keyword,
                "platform": normalized_platform,
                "locale": locale,
                "top_n": top_n,
                "currency_code": currency_code,
                "currency_symbol": currency_symbol,
            },
            "metrics": metrics,
            "price_distribution": _build_price_distribution(prices, currency_symbol),
            "top_competitors": top_competitors,
            "voc": {
                "pain_points": enrichment.get("pain_points") or [],
                "selling_points": enrichment.get("selling_points") or [],
                "visual_style": enrichment.get("visual_style") or [],
            },
            "recommendation": {
                "suggested_price": suggested_price,
                "positioning": enrichment.get("positioning") or "",
                "listing_focus": listing_focus[:5],
            },
            "narrative": enrichment.get("narrative") or "",
            "report_markdown": report_markdown,
            "report_lang": lang,
            "llm_source": source_tag,
            "source": "live_data",
        }
