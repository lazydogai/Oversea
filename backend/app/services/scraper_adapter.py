from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1
from typing import Any


@dataclass(frozen=True)
class AmazonSearchItem:
    asin: str
    title: str
    price: float
    bsr: int
    review_count: int
    image_url: str


class MockScraper:
    def search_top_products(self, keyword: str, marketplace: str = "amazon", top_n: int = 200) -> list[dict[str, Any]]:
        seed = int(sha1(f"{keyword}:{marketplace}".encode("utf-8")).hexdigest()[:8], 16)
        items: list[dict[str, Any]] = []

        for index in range(1, top_n + 1):
            asin = f"B0{(seed + index) % 100000000:08d}"[-10:]
            price = round(12.99 + ((seed + index * 17) % 7800) / 100, 2)
            bsr = 1 + ((seed // 3) + index * 41) % 5000
            review_count = 12 + ((seed // 5) + index * 137) % 12000
            items.append(
                {
                    "asin": asin,
                    "title": f"{keyword.title()} Product {index}",
                    "price": price,
                    "bsr": bsr,
                    "review_count": review_count,
                    "image_url": f"https://images.example.com/{asin}.jpg",
                    "marketplace": marketplace,
                }
            )

        return items
