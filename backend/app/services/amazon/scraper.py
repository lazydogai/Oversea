from dataclasses import dataclass
from typing import Any


@dataclass
class AmazonSearchResult:
    keyword: str
    marketplace: str
    items: list[dict[str, Any]]


class AmazonScraperAdapter:
    def search_top_products(self, keyword: str, marketplace: str, top_n: int) -> AmazonSearchResult:
        return AmazonSearchResult(keyword=keyword, marketplace=marketplace, items=[])

