from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any


def _normalize_report_lang(report_lang: str | None) -> str:
    value = (report_lang or "zh").strip().lower().replace("_", "-")
    if value in {"en", "en-us", "en-gb", "english"}:
        return "en"
    return "zh"


def _fallback_enrichment(keyword: str, platform: str, metrics: dict[str, Any], report_lang: str) -> dict[str, Any]:
    lang = _normalize_report_lang(report_lang)
    platform_label = "Taobao" if str(platform).lower() in {"taobao", "tmall", "tao"} else "Amazon"
    count = metrics.get("product_count")
    price_min = metrics.get("price_min")
    price_median = metrics.get("price_median")
    price_max = metrics.get("price_max")
    avg_rating = metrics.get("avg_rating")
    symbol = metrics.get("currency_symbol") or ("¥" if platform_label == "Taobao" else "$")

    if lang == "en":
        return {
            "pain_points": [
                "Public search results do not include deep review or Q&A VOC; treat listing claims carefully.",
                "Price and review gaps between leaders and long-tail listings can hide quality or fulfillment issues.",
                "Title keyword stuffing is common; buyers still need clearer benefit differentiation.",
            ],
            "selling_points": [
                "Unified price, rating, review count, brand, image, and product link from live search.",
                f"Median price for “{keyword}” sits near {symbol}{price_median}" if price_median is not None else f"Live {platform_label} search signals for “{keyword}”.",
                f"Average rating around {avg_rating}" if avg_rating is not None else "Rating coverage varies by listing maturity.",
            ],
            "visual_style": [
                "Clean hero image on white or soft gradient",
                "Close-up of primary benefit / key feature",
                "Size or use-scene comparison card",
            ],
            "positioning": f"Market positioning based on {platform_label} search results for “{keyword}”",
            "listing_focus": [token for token in re.findall(r"[A-Za-z0-9\u4e00-\u9fff]+", keyword) if len(token) > 1][:5] or [keyword],
            "narrative": (
                f"For “{keyword}” on {platform_label}, the live sample covers {count or '—'} listings"
                f" with prices from {symbol}{price_min} to {symbol}{price_max}"
                f" and a median near {symbol}{price_median}. "
                f"Average rating is {avg_rating if avg_rating is not None else 'n/a'}.\n\n"
                "Leaders usually win with review volume and clear benefit claims, while mid-pack listings compete on price or niche features. "
                "Without deep review mining, treat VOC as directional and validate with PDP bullets and customer questions before locking a listing draft.\n\n"
                "A practical next step is to price near the median, differentiate one or two proof points the top titles already cluster around, "
                "and keep imagery consistent with the dominant clean-product style in this SERP."
            ),
            "suggested_price": price_median,
            "_source": "fallback",
        }

    return {
        "pain_points": [
            "公开搜索结果缺少深度评论与问答 VOC，需谨慎对待 Listing 宣称。",
            "头部与长尾之间的价格、评论差距可能掩盖品质或履约问题。",
            "标题关键词堆砌常见，买家仍需要更清晰的利益点差异。",
        ],
        "selling_points": [
            "价格、评分、评论数、品牌、图片和商品链接会从实时搜索统一整理。",
            f"“{keyword}” 价格中位数约 {symbol}{price_median}" if price_median is not None else f"“{keyword}” 的 {platform_label} 实时搜索信号。",
            f"平均评分约 {avg_rating}" if avg_rating is not None else "评分覆盖随 Listing 成熟度变化。",
        ],
        "visual_style": [
            "白底或浅色背景主图",
            "核心卖点近景特写",
            "尺寸或使用场景对比卡",
        ],
        "positioning": f"基于 {platform_label} 搜索结果的「{keyword}」市场定位",
        "listing_focus": [token for token in re.findall(r"[A-Za-z0-9\u4e00-\u9fff]+", keyword) if len(token) > 1][:5] or [keyword],
        "narrative": (
            f"在 {platform_label} 搜索「{keyword}」时，本次样本覆盖 {count or '—'} 个商品，"
            f"价格区间约 {symbol}{price_min}–{symbol}{price_max}，中位数约 {symbol}{price_median}，"
            f"平均评分 {avg_rating if avg_rating is not None else '暂缺'}。\n\n"
            "头部商品通常靠评论量与清晰利益点占位，中腰部则靠价格或细分卖点竞争。"
            "在缺少深度评论挖掘前，VOC 仅作方向参考，落地前应再核对详情页卖点与买家问答。\n\n"
            "可执行建议：定价贴近中位数，突出 Top 标题已聚集的 1–2 个证明点，"
            "主图风格与当前 SERP 主流的干净产品图保持一致。"
        ),
        "suggested_price": price_median,
        "_source": "fallback",
    }


def _compact_products(products: list[dict[str, Any]], limit: int = 20) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for item in products[:limit]:
        compact.append(
            {
                "title": str(item.get("title") or "")[:160],
                "price": item.get("price"),
                "rating": item.get("rating"),
                "review_count": item.get("review_count"),
                "brand": str(item.get("brand") or "")[:80],
            }
        )
    return compact


def _sanitize_enrichment(raw: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    def _str_list(value: Any, default: list[str], max_items: int = 8) -> list[str]:
        if not isinstance(value, list):
            return default
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        return cleaned[:max_items] if cleaned else default

    suggested = raw.get("suggested_price", fallback.get("suggested_price"))
    if suggested is not None:
        try:
            suggested = float(suggested)
        except (TypeError, ValueError):
            suggested = fallback.get("suggested_price")

    return {
        "pain_points": _str_list(raw.get("pain_points"), fallback["pain_points"]),
        "selling_points": _str_list(raw.get("selling_points"), fallback["selling_points"]),
        "visual_style": _str_list(raw.get("visual_style"), fallback["visual_style"], max_items=6),
        "positioning": str(raw.get("positioning") or fallback["positioning"]).strip() or fallback["positioning"],
        "listing_focus": _str_list(raw.get("listing_focus"), fallback["listing_focus"], max_items=5),
        "narrative": str(raw.get("narrative") or fallback["narrative"]).strip() or fallback["narrative"],
        "suggested_price": suggested,
        "_source": raw.get("_source") or "openrouter",
    }


class MockLLMAdapter:
    """Deterministic bilingual fallback used when OpenRouter is not configured."""

    def analyze_voc(self, products: list[dict[str, Any]]) -> dict[str, Any]:
        enriched = self.enrich_report(
            keyword="product",
            platform="amazon",
            products=products,
            metrics={"product_count": len(products)},
            report_lang="zh",
        )
        return {
            "pain_points": enriched["pain_points"],
            "selling_points": enriched["selling_points"],
            "visual_style": enriched["visual_style"],
        }

    def enrich_report(
        self,
        keyword: str,
        platform: str,
        products: list[dict[str, Any]],
        metrics: dict[str, Any],
        report_lang: str = "zh",
    ) -> dict[str, Any]:
        _ = products
        result = _fallback_enrichment(keyword, platform, metrics or {}, report_lang)
        result["_source"] = "mock"
        return result


class OpenRouterLLMAdapter:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout_seconds: int = 60,
    ) -> None:
        self.api_key = (api_key if api_key is not None else os.getenv("OPENROUTER_API_KEY") or "").strip()
        self.base_url = (base_url or os.getenv("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1").rstrip("/")
        self.model = (model or os.getenv("OPENROUTER_MODEL") or "deepseek/deepseek-v4-flash").strip()
        self.timeout_seconds = timeout_seconds

    def enrich_report(
        self,
        keyword: str,
        platform: str,
        products: list[dict[str, Any]],
        metrics: dict[str, Any],
        report_lang: str = "zh",
    ) -> dict[str, Any]:
        lang = _normalize_report_lang(report_lang)
        fallback = _fallback_enrichment(keyword, platform, metrics or {}, lang)
        if not self.api_key:
            fallback["_source"] = "fallback"
            return fallback

        language_name = "Simplified Chinese" if lang == "zh" else "English"
        compact = _compact_products(products)
        payload_obj = {
            "keyword": keyword,
            "platform": platform,
            "report_lang": lang,
            "metrics": {
                "product_count": metrics.get("product_count"),
                "price_min": metrics.get("price_min"),
                "price_median": metrics.get("price_median"),
                "price_max": metrics.get("price_max"),
                "avg_rating": metrics.get("avg_rating"),
                "review_total": metrics.get("review_total"),
                "top_brand_share": metrics.get("top_brand_share"),
                "currency_symbol": metrics.get("currency_symbol"),
            },
            "products": compact,
        }
        user_content = (
            f"Write a concise human market-research brief for keyword analysis.\n"
            f"ALL narrative strings must be in {language_name} (report_lang={lang}).\n"
            "Return a JSON object with keys: pain_points (array of strings), "
            "selling_points (array of strings), visual_style (array of strings), "
            "positioning (string), listing_focus (array of up to 5 short strings), "
            "narrative (string with 2-4 short paragraphs), suggested_price (number or null).\n"
            "Base claims only on the provided metrics and product list; do not invent ASINs or sales volumes.\n"
            f"DATA:\n{json.dumps(payload_obj, ensure_ascii=False)}"
        )
        # Cap prompt size roughly.
        if len(user_content) > 12000:
            user_content = user_content[:12000] + "\n...(truncated)"

        body = json.dumps(
            {
                "model": self.model,
                "temperature": 0.3,
                "response_format": {"type": "json_object"},
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a senior e-commerce market analyst. "
                            "Reply with a single JSON object only, no markdown fences."
                        ),
                    },
                    {"role": "user", "content": user_content},
                ],
            }
        ).encode("utf-8")

        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://lazydogai.com",
                "X-Title": "Oversea-Market-Report",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = json.loads(response.read().decode("utf-8"))
            content = raw["choices"][0]["message"]["content"]
            content = content.strip()
            if content.startswith("```"):
                content = re.sub(r"^```(?:json)?\s*", "", content)
                content = re.sub(r"\s*```$", "", content)
            parsed = json.loads(content)
            if not isinstance(parsed, dict):
                raise ValueError("LLM response is not a JSON object")
            parsed["_source"] = "openrouter"
            return _sanitize_enrichment(parsed, fallback)
        except Exception:  # noqa: BLE001 — any failure falls back so the report still completes
            fallback["_source"] = "fallback"
            return fallback


def get_llm_adapter() -> MockLLMAdapter | OpenRouterLLMAdapter:
    key = (os.getenv("OPENROUTER_API_KEY") or "").strip()
    if key:
        return OpenRouterLLMAdapter(api_key=key)
    return MockLLMAdapter()
