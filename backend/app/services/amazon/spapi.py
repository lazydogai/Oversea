from dataclasses import dataclass
from typing import Any


@dataclass
class ValidationPreviewResult:
    status: str
    issues: list[dict[str, Any]]


class AmazonSPAPIAdapter:
    def validate_listing_draft(self, draft: dict[str, Any]) -> ValidationPreviewResult:
        _ = draft
        return ValidationPreviewResult(status="not_connected", issues=[])

