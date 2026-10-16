from __future__ import annotations

import json
import os
import re
import statistics
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo


def _normalize_report_lang(report_lang: str | None) -> str:
    value = (report_lang or "zh").strip().lower().replace("_", "-")
    if value in {"en", "en-us", "en-gb", "english"}:
        return "en"
    return "zh"


def _platform_label(platform: str) -> str:
    return "Taobao" if str(platform).lower() in {"taobao", "tmall", "tao"} else "Amazon"


def _detect_seed(products: list[dict[str, Any]], metrics: dict[str, Any], keyword: str) -> dict[str, Any] | None:
    seed_asin = str(metrics.get("seed_asin") or metrics.get("seed") or "").strip().upper()
    if not seed_asin:
        kw = (keyword or "").strip().upper()
        if re.fullmatch(r"B0[A-Z0-9]{8}", kw):
            seed_asin = kw
    if not seed_asin:
        return None
    for index, item in enumerate(products):
        asin = str(item.get("asin") or item.get("item_id") or "").strip().upper()
        if asin == seed_asin:
            return {
                "asin": asin,
                "rank": index + 1,
                "title": str(item.get("title") or ""),
                "price": item.get("price"),
                "rating": item.get("rating"),
                "review_count": item.get("review_count"),
                "monthly_purchase_volume": item.get("monthly_purchase_volume"),
            }
    return {"asin": seed_asin, "rank": None, "title": "", "price": None, "rating": None}


def _price_band(price: float | None, median: float | None) -> str:
    if price is None or median is None or median <= 0:
        return "mid"
    if price < median * 0.75:
        return "budget"
    if price > median * 1.35:
        return "premium"
    return "mid"


def _cluster_products(products: list[dict[str, Any]], prices: list[float]) -> dict[str, dict[str, Any]]:
    if not prices:
        return {
            "budget": {"lo": None, "hi": None, "examples": [], "note_zh": "暂无价格样本。", "note_en": "No priced sample."},
            "mid": {"lo": None, "hi": None, "examples": [], "note_zh": "暂无价格样本。", "note_en": "No priced sample."},
            "premium": {"lo": None, "hi": None, "examples": [], "note_zh": "暂无价格样本。", "note_en": "No priced sample."},
        }
    sorted_prices = sorted(prices)
    p33 = sorted_prices[max(0, len(sorted_prices) // 3)]
    p66 = sorted_prices[max(0, (2 * len(sorted_prices)) // 3)]
    budget_hi = round(p33, 2)
    mid_hi = round(p66, 2)
    clusters = {
        "budget": {"lo": round(min(prices), 2), "hi": budget_hi, "examples": [], "items": []},
        "mid": {"lo": round(budget_hi + 0.01, 2) if budget_hi else None, "hi": mid_hi, "examples": [], "items": []},
        "premium": {"lo": round(mid_hi + 0.01, 2) if mid_hi else None, "hi": round(max(prices), 2), "examples": [], "items": []},
    }
    for item in products:
        price = item.get("price")
        if not isinstance(price, (int, float)):
            continue
        asin = str(item.get("asin") or item.get("item_id") or "")[:14]
        if price <= budget_hi:
            key = "budget"
        elif price <= mid_hi:
            key = "mid"
        else:
            key = "premium"
        clusters[key]["items"].append(item)
        if asin and asin not in clusters[key]["examples"] and len(clusters[key]["examples"]) < 5:
            clusters[key]["examples"].append(asin)
    clusters["budget"]["note_zh"] = "以基础功能、入门无线/有线为主，适合价格敏感买家。"
    clusters["budget"]["note_en"] = "Entry wireless/wired basics for price-sensitive buyers."
    clusters["mid"]["note_zh"] = "多数具备蓝牙/双模、静音或可调 DPI，主流成交带。"
    clusters["mid"]["note_en"] = "Often Bluetooth/dual-mode, quiet clicks, or adjustable DPI — the mainstream band."
    clusters["premium"]["note_zh"] = "品牌旗舰、人体工学或专业电竞，价格更高、证明要求更强。"
    clusters["premium"]["note_en"] = "Flagship, ergonomic, or pro/gaming SKUs with higher proof requirements."
    return clusters


def _build_deterministic_report_markdown(
    keyword: str,
    platform: str,
    products: list[dict[str, Any]],
    metrics: dict[str, Any],
    report_lang: str,
    llm_model: str | None = None,
    llm_source: str = "fallback",
    seed: dict[str, Any] | None = None,
) -> str:
    lang = _normalize_report_lang(report_lang)
    platform_label = _platform_label(platform)
    currency = metrics.get("currency_symbol") or ("¥" if platform_label == "Taobao" else "$")
    now = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S CST")
    n = int(metrics.get("product_count") or len(products) or 0)
    prices = [float(p["price"]) for p in products if isinstance(p.get("price"), (int, float))]
    ratings = [float(p["rating"]) for p in products if isinstance(p.get("rating"), (int, float))]
    n_price = len(prices)
    n_rating = len(ratings)
    price_min = metrics.get("price_min")
    price_median = metrics.get("price_median")
    price_max = metrics.get("price_max")
    price_mean = round(statistics.mean(prices), 2) if prices else None
    model = llm_model or os.getenv("OPENROUTER_MODEL") or "deepseek/deepseek-v4-flash"
    seed = seed or _detect_seed(products, metrics, keyword)

    stats = {
        "n": n,
        "n_with_price": n_price,
        "n_with_rating": n_rating,
        "currency": "CNY" if currency == "¥" else "USD",
        "price_min": price_min,
        "price_max": price_max,
        "price_median": price_median,
        "price_mean": price_mean,
    }
    if seed:
        stats["seed_rank"] = seed.get("rank")
        stats["seed_price"] = seed.get("price")
        stats["seed_title"] = (seed.get("title") or "")[:180]
        stats["seed_rating"] = seed.get("rating")
        if isinstance(seed.get("price"), (int, float)) and prices:
            sp = float(seed["price"])
            stats["seed_price_position"] = {
                "cheaper_than_seed": sum(1 for p in prices if p < sp),
                "pricier_than_seed": sum(1 for p in prices if p > sp),
                "equal": sum(1 for p in prices if abs(p - sp) < 0.005),
            }

    clusters = _cluster_products(products, prices)

    # Bestsellers by monthly volume / reviews
    scored = []
    for index, item in enumerate(products):
        vol = str(item.get("monthly_purchase_volume") or "")
        reviews = int(item.get("review_count") or 0)
        scored.append((reviews, vol, index, item))
    scored.sort(key=lambda x: (-x[0], x[2]))
    top_sellers = scored[:5]

    top15_lines = []
    for index, item in enumerate(products[:15]):
        asin = str(item.get("asin") or item.get("item_id") or "—")
        price = item.get("price")
        rating = item.get("rating")
        title = str(item.get("title") or "")[:90]
        price_s = f"{currency}{price}" if isinstance(price, (int, float)) else "—"
        rating_s = f"★{rating}" if isinstance(rating, (int, float)) else ""
        seed_tag = " (SEED)" if seed and str(seed.get("asin") or "").upper() == asin.upper() else ""
        top15_lines.append(f"- #{index + 1} `{asin}` {price_s} {rating_s}{seed_tag} {title}".rstrip())

    if lang == "en":
        title = f"# {platform_label} SERP market brief · `{keyword}`"
        meta = [
            f"- Time: {now}",
            f"- Keyword: `{keyword}`",
        ]
        if seed and seed.get("asin"):
            rank = seed.get("rank") or "—"
            sp = seed.get("price")
            sp_s = f"{currency}{sp}" if isinstance(sp, (int, float)) else "—"
            meta.append(f"- Seed: `{seed['asin']}` · SERP rank: **{rank}** · price **{sp_s}**")
        meta.extend(
            [
                f"- Results: {n} / with price: {n_price} / with rating: {n_rating}",
                f"- LLM: `{model}` · source={llm_source}",
                f"- Source: live {platform_label} search (normalized SERP fields)",
            ]
        )
        snapshot = (
            f"SERP for “{keyword}” returns {n} rows on {platform_label}. "
            f"Priced range {currency}{price_min}–{currency}{price_max} (n={n_price}), "
            f"median {currency}{price_median}. "
            + (
                f"Seed `{seed['asin']}` sits at rank {seed.get('rank')} at {currency}{seed.get('price')}."
                if seed and seed.get("rank")
                else "No seed ASIN supplied — treat ranking as category landscape only."
            )
        )
        price_band = (
            f"- {stats['currency']} min/median/max = {price_min} / {price_median} / {price_max} (n={n_price})\n"
            f"- Mean ≈ {price_mean}. Distribution spans budget entry SKUs through premium brand/ergonomic listings."
        )
        if seed and seed.get("rank"):
            band = _price_band(seed.get("price") if isinstance(seed.get("price"), (int, float)) else None, price_median if isinstance(price_median, (int, float)) else None)
            delta = None
            if isinstance(seed.get("price"), (int, float)) and isinstance(price_median, (int, float)):
                delta = round(float(seed["price"]) - float(price_median), 2)
            seed_sec = (
                f"- Seed `{seed['asin']}` rank={seed.get('rank')} · band=`{band}`"
                + (f" · {delta:+} vs median" if delta is not None else "")
                + f"\n- Title: {(seed.get('title') or '—')[:160]}"
            )
        else:
            seed_sec = "- N/A — no seed ASIN in this run."

        bestseller_lines = []
        for reviews, vol, index, item in top_sellers:
            asin = item.get("asin") or item.get("item_id") or "—"
            price = item.get("price")
            price_s = f"{currency}{price}" if isinstance(price, (int, float)) else "—"
            title_s = str(item.get("title") or "")[:70]
            vol_s = f", bought={vol}" if vol else ""
            bestseller_lines.append(
                f"- #{index + 1} `{asin}` {price_s} · reviews={reviews}{vol_s} · {title_s}"
            )
        if not bestseller_lines:
            bestseller_lines = ["- Insufficient sales/review signals in this SERP sample."]

        cluster_blocks = []
        labels = {"budget": "budget: value", "mid": "mid: mainstream", "premium": "premium: proof"}
        for key in ("budget", "mid", "premium"):
            c = clusters[key]
            lo, hi = c.get("lo"), c.get("hi")
            range_s = f"{lo} - {hi}" if lo is not None and hi is not None else "—"
            examples = ", ".join(c.get("examples") or []) or "—"
            cluster_blocks.append(
                f"### {labels[key]}\n- {range_s}\n- examples: {examples}\n- {c.get('note_en')}"
            )

        gaps = [
            "- SERP may include accessories or off-category noise; filter before locking assortment bets.",
            f"- Mid band around median {currency}{price_median} is crowded; differentiate on proof (reviews, feature, brand ecosystem), not title stuffing alone.",
            "- Review-volume leaders set trust bars; low-review high-rank SKUs need conversion work.",
            "- Without PDP Q&A mining, VOC here is directional — validate bullets before Listing Draft.",
            "- Price gaps between lookalike titles can signal variant/bundle differences; check PDP before undercutting.",
        ]
        headlines = [
            f"- Median {currency}{price_median} with {n_price}/{n} priced rows — use as pricing anchor.",
            "- Review and bought signals concentrate on a few leaders; mid-pack competes on niche or price.",
            "- Clear budget / mid / premium stacks exist; pick one lane and one proof point.",
        ]
        recs = [
            f"1. Price near the median ({currency}{price_median}) unless a premium proof story is ready.",
            "2. Mirror 1–2 benefit claims already clustered in Top-15 titles; avoid pure keyword stuffing.",
            "3. Prioritize review velocity / social proof if rank is strong but review count lags leaders.",
            "4. Keep hero imagery consistent with the dominant clean-product SERP style.",
            "5. Re-run after filtering off-category accessories to tighten cluster and gap analysis.",
        ]
        quality = [
            f"- {n - n_price} rows missing price; {n - n_rating} missing rating — completeness affects medians.",
            "- Treat monthly-bought strings as directional when present; absences are not zero demand.",
            f"- Analysis source={llm_source}; regenerate with live LLM for denser analyst narrative when configured.",
        ]
        footer = "---\n*SERP-first market brief · Oversea*"
        parts = [
            title,
            "",
            "\n".join(meta),
            "",
            "## Category snapshot",
            snapshot,
            "",
            "## Price band",
            price_band,
            "",
            "```json",
            json.dumps(stats, ensure_ascii=False, indent=2),
            "```",
            "",
            "## Seed positioning",
            seed_sec,
            "",
            "## Bestsellers pattern",
            "\n".join(bestseller_lines),
            "",
            "## Clusters",
            "\n\n".join(cluster_blocks),
            "",
            "## Gaps & risks",
            "\n".join(gaps),
            "",
            "## Headlines",
            "\n".join(headlines),
            "",
            "## Five recommendations",
            "\n".join(recs),
            "",
            "## Data quality",
            "\n".join(quality),
            "",
            "## Top 15 SERP",
            "\n".join(top15_lines) if top15_lines else "- No products.",
            "",
            footer,
        ]
        return "\n".join(parts)

    # zh
    title = f"# {platform_label} 搜尋結果市調簡報 · `{keyword}`"
    meta = [
        f"- 時間：{now}",
        f"- 關鍵字：`{keyword}`",
    ]
    if seed and seed.get("asin"):
        rank = seed.get("rank") or "—"
        sp = seed.get("price")
        sp_s = f"{currency}{sp}" if isinstance(sp, (int, float)) else "—"
        meta.append(f"- Seed：`{seed['asin']}` · SERP 排名：**{rank}** · 價 **{sp_s}**")
    meta.extend(
        [
            f"- 結果數：{n}／有價：{n_price}／有評分：{n_rating}",
            f"- LLM：`{model}` · source={llm_source}",
            f"- 來源：{platform_label} 公開搜尋（標準化 SERP 欄位）",
        ]
    )
    snapshot = (
        f"此搜尋「{keyword}」在 {platform_label} 共 {n} 條結果。"
        f"有價區間 {currency}{price_min}–{currency}{price_max}（n={n_price}），中位數 {currency}{price_median}。"
        + (
            f"種子 `{seed['asin']}` 排名第 {seed.get('rank')}，價 {currency}{seed.get('price')}。"
            if seed and seed.get("rank")
            else "本次未指定種子 ASIN，以下按品類格局解讀。"
        )
    )
    price_band = (
        f"- {stats['currency']} min/median/max = {price_min} / {price_median} / {price_max} (n={n_price})\n"
        f"- 均值約 {price_mean}。價帶覆蓋入門平價至高階品牌／人體工學。"
    )
    if seed and seed.get("rank"):
        band = _price_band(seed.get("price") if isinstance(seed.get("price"), (int, float)) else None, price_median if isinstance(price_median, (int, float)) else None)
        delta = None
        if isinstance(seed.get("price"), (int, float)) and isinstance(price_median, (int, float)):
            delta = round(float(seed["price"]) - float(price_median), 2)
        seed_sec = (
            f"- 種子 `{seed['asin']}` rank={seed.get('rank')} · `{band}`"
            + (f" · 相對中位數 {delta:+}" if delta is not None else "")
            + f"\n- 標題：{(seed.get('title') or '—')[:160]}"
        )
    else:
        seed_sec = "- N/A — 本次無種子 ASIN。"

    bestseller_lines = []
    for reviews, vol, index, item in top_sellers:
        asin = item.get("asin") or item.get("item_id") or "—"
        price = item.get("price")
        price_s = f"{currency}{price}" if isinstance(price, (int, float)) else "—"
        title_s = str(item.get("title") or "")[:70]
        vol_s = f"，bought={vol}" if vol else ""
        bestseller_lines.append(
            f"- #{index + 1} `{asin}` {price_s} · 評論={reviews}{vol_s} · {title_s}"
        )
    if not bestseller_lines:
        bestseller_lines = ["- 本次樣本缺乏可靠銷量／評論信號。"]

    cluster_blocks = []
    labels = {"budget": "budget: 平價", "mid": "mid: 中階", "premium": "premium: 高階"}
    for key in ("budget", "mid", "premium"):
        c = clusters[key]
        lo, hi = c.get("lo"), c.get("hi")
        range_s = f"{lo} - {hi}" if lo is not None and hi is not None else "—"
        examples = ", ".join(c.get("examples") or []) or "—"
        cluster_blocks.append(
            f"### {labels[key]}\n- {range_s}\n- examples: {examples}\n- {c.get('note_zh')}"
        )

    gaps = [
        "- SERP 可能混入配件／離題商品，定策略前應先過濾雜訊。",
        f"- 中位數附近（約 {currency}{price_median}）競爭密集，需用評論／功能／生態證明差異，而非堆關鍵字。",
        "- 高評論頭部定下信任門檻；排名高但評論少的 SKU 需補轉換。",
        "- 缺少 PDP 問答深挖時，VOC 僅作方向，Listing Draft 前再核對賣點。",
        "- 標題相似但價差大的商品可能是變體／捆綁差異，降價前先對詳情頁。",
    ]
    headlines = [
        f"- 中位數 {currency}{price_median}，有價 {n_price}/{n} —— 可作定價錨。",
        "- 評論／bought 信號集中在少數頭部；中腰部靠價格或細分賣點。",
        "- budget／mid／premium 分層清晰；選一條賽道 + 一個證明點。",
    ]
    recs = [
        f"1. 定價貼近中位數（{currency}{price_median}），除非已有高階證明故事。",
        "2. 标题突出 Top 15 已聚集的 1–2 個利益點，避免純關鍵字堆砌。",
        "3. 若排名強但評論落後頭部，優先衝評論與社會證明。",
        "4. 主圖風格對齊當前 SERP 主流乾淨產品圖。",
        "5. 過濾離題配件後再跑一輪，收緊集群與缺口判斷。",
    ]
    quality = [
        f"- 缺價 {n - n_price} 條、缺評分 {n - n_rating} 條，會影響中位數穩定度。",
        "- monthly bought 字串僅作方向；缺失不代表零需求。",
        f"- 本次 source={llm_source}；配置 live LLM 後可生成更密的分析師敘事。",
    ]
    footer = "---\n*SERP-first 市調簡報 · Oversea*"
    parts = [
        title,
        "",
        "\n".join(meta),
        "",
        "## 品類快照",
        snapshot,
        "",
        "## 價帶",
        price_band,
        "",
        "```json",
        json.dumps(stats, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Seed 定位",
        seed_sec,
        "",
        "## 暢銷格局",
        "\n".join(bestseller_lines),
        "",
        "## 集群",
        "\n\n".join(cluster_blocks),
        "",
        "## 缺口／風險",
        "\n".join(gaps),
        "",
        "## 頭條",
        "\n".join(headlines),
        "",
        "## 五個建議",
        "\n".join(recs),
        "",
        "## 數據質素",
        "\n".join(quality),
        "",
        "## Top 15 SERP",
        "\n".join(top15_lines) if top15_lines else "- 無商品。",
        "",
        footer,
    ]
    return "\n".join(parts)


def _fallback_enrichment(
    keyword: str,
    platform: str,
    metrics: dict[str, Any],
    report_lang: str,
    products: list[dict[str, Any]] | None = None,
    llm_source: str = "fallback",
) -> dict[str, Any]:
    lang = _normalize_report_lang(report_lang)
    platform_label = _platform_label(platform)
    products = products or []
    count = metrics.get("product_count")
    price_min = metrics.get("price_min")
    price_median = metrics.get("price_median")
    price_max = metrics.get("price_max")
    avg_rating = metrics.get("avg_rating")
    symbol = metrics.get("currency_symbol") or ("¥" if platform_label == "Taobao" else "$")
    report_markdown = _build_deterministic_report_markdown(
        keyword=keyword,
        platform=platform,
        products=products,
        metrics=metrics or {},
        report_lang=lang,
        llm_source=llm_source,
    )

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
            "report_markdown": report_markdown,
            "_source": llm_source,
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
        "report_markdown": report_markdown,
        "_source": llm_source,
    }


def _compact_products(products: list[dict[str, Any]], limit: int = 50) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for index, item in enumerate(products[:limit]):
        compact.append(
            {
                "rank": index + 1,
                "asin": str(item.get("asin") or item.get("item_id") or "")[:20],
                "title": str(item.get("title") or "")[:160],
                "price": item.get("price"),
                "rating": item.get("rating"),
                "review_count": item.get("review_count"),
                "brand": str(item.get("brand") or "")[:80],
                "monthly_purchase_volume": item.get("monthly_purchase_volume"),
            }
        )
    return compact


def _looks_like_full_report(md: str, lang: str) -> bool:
    text = md or ""
    if lang == "en":
        markers = ["## Category snapshot", "## Five recommendations", "## Price band", "## Top 15 SERP"]
    else:
        markers = ["## 品類快照", "## 五個建議", "## 價帶", "## Top 15 SERP"]
        # Also accept simplified-chinese headings the model might emit
        markers += ["## 品类快照", "## 五个建议", "## 价带"]
    hits = sum(1 for m in markers if m in text)
    return hits >= 2 and len(text) > 400


def _sanitize_enrichment(
    raw: dict[str, Any],
    fallback: dict[str, Any],
    *,
    keyword: str,
    platform: str,
    products: list[dict[str, Any]],
    metrics: dict[str, Any],
    report_lang: str,
    llm_source: str = "openrouter",
    llm_model: str | None = None,
) -> dict[str, Any]:
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

    lang = _normalize_report_lang(report_lang)
    report_markdown = str(raw.get("report_markdown") or "").strip()
    if not _looks_like_full_report(report_markdown, lang):
        report_markdown = _build_deterministic_report_markdown(
            keyword=keyword,
            platform=platform,
            products=products,
            metrics=metrics,
            report_lang=lang,
            llm_model=llm_model,
            llm_source=llm_source,
        )

    return {
        "pain_points": _str_list(raw.get("pain_points"), fallback["pain_points"]),
        "selling_points": _str_list(raw.get("selling_points"), fallback["selling_points"]),
        "visual_style": _str_list(raw.get("visual_style"), fallback["visual_style"], max_items=6),
        "positioning": str(raw.get("positioning") or fallback["positioning"]).strip() or fallback["positioning"],
        "listing_focus": _str_list(raw.get("listing_focus"), fallback["listing_focus"], max_items=5),
        "narrative": str(raw.get("narrative") or fallback["narrative"]).strip() or fallback["narrative"],
        "suggested_price": suggested,
        "report_markdown": report_markdown,
        "_source": raw.get("_source") or llm_source,
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
        result = _fallback_enrichment(
            keyword,
            platform,
            metrics or {},
            report_lang,
            products=products or [],
            llm_source="mock",
        )
        result["_source"] = "mock"
        return result


class OpenRouterLLMAdapter:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout_seconds: int = 90,
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
        fallback = _fallback_enrichment(
            keyword,
            platform,
            metrics or {},
            lang,
            products=products or [],
            llm_source="fallback",
        )
        if not self.api_key:
            fallback["_source"] = "fallback"
            return fallback

        language_name = "Traditional Chinese (Hong Kong style OK) or Simplified Chinese" if lang == "zh" else "English"
        section_guide = (
            "Required markdown sections IN ORDER (use these exact ## headings):\n"
            "## 品類快照\n## 價帶\n## Seed 定位\n## 暢銷格局\n## 集群\n"
            "## 缺口／風險\n## 頭條\n## 五個建議\n## 數據質素\n## Top 15 SERP\n"
            if lang == "zh"
            else "Required markdown sections IN ORDER (use these exact ## headings):\n"
            "## Category snapshot\n## Price band\n## Seed positioning\n## Bestsellers pattern\n## Clusters\n"
            "## Gaps & risks\n## Headlines\n## Five recommendations\n## Data quality\n## Top 15 SERP\n"
        )
        seed = _detect_seed(products or [], metrics or {}, keyword)
        compact = _compact_products(products or [], limit=50)
        payload_obj = {
            "keyword": keyword,
            "platform": platform,
            "report_lang": lang,
            "seed": seed,
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
            f"Write a dense human SERP market-research REPORT like a real analyst brief.\n"
            f"ALL narrative in report_markdown must be in {language_name} (report_lang={lang}).\n"
            "Return a JSON object with keys:\n"
            "- report_markdown (string): FULL markdown report — this is the primary deliverable\n"
            "- pain_points (array of strings)\n"
            "- selling_points (array of strings)\n"
            "- visual_style (array of strings)\n"
            "- positioning (string)\n"
            "- listing_focus (array of up to 5 short strings)\n"
            "- narrative (string, 2-4 short paragraphs summarizing the same story)\n"
            "- suggested_price (number or null)\n\n"
            "report_markdown structure:\n"
            "1) Title line: # ... keyword\n"
            "2) Meta bullets: time, keyword, seed (if any), counts, LLM model, source\n"
            f"{section_guide}"
            "Under ## 價帶 / ## Price band include a compact ```json stats block with n, n_with_price, "
            "price_min/median/max/mean, and seed fields when known.\n"
            "Under ## 集群 / ## Clusters use ### budget / ### mid / ### premium with price range + example ASINs.\n"
            "Under ## Top 15 SERP list rank, ASIN, price, rating, title (mark SEED if applicable).\n"
            "Tone: concise, concrete numbers, actionable. Do NOT invent ASINs, bought volumes, or review counts "
            "not present in DATA. If seed is null, say N/A in Seed section.\n"
            f"DATA:\n{json.dumps(payload_obj, ensure_ascii=False)}"
        )
        if len(user_content) > 28000:
            user_content = user_content[:28000] + "\n...(truncated)"

        body = json.dumps(
            {
                "model": self.model,
                "temperature": 0.35,
                "response_format": {"type": "json_object"},
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a senior e-commerce market analyst writing SERP research briefs. "
                            "Reply with a single JSON object only, no markdown fences around the JSON. "
                            "report_markdown must contain the full multi-section report."
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
            return _sanitize_enrichment(
                parsed,
                fallback,
                keyword=keyword,
                platform=platform,
                products=products or [],
                metrics=metrics or {},
                report_lang=lang,
                llm_source="openrouter",
                llm_model=self.model,
            )
        except Exception:  # noqa: BLE001 — any failure falls back so the report still completes
            fallback["_source"] = "fallback"
            return fallback


def get_llm_adapter() -> MockLLMAdapter | OpenRouterLLMAdapter:
    key = (os.getenv("OPENROUTER_API_KEY") or "").strip()
    if key:
        return OpenRouterLLMAdapter(api_key=key)
    return MockLLMAdapter()
