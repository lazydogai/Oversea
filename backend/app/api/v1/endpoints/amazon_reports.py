from uuid import UUID, uuid4

from fastapi import APIRouter
from pydantic import BaseModel, Field


router = APIRouter()


class AmazonReportCreateRequest(BaseModel):
    keyword: str = Field(min_length=1)
    marketplace: str = "amazon_us"
    locale: str = "US"
    top_n: int = Field(default=50, ge=1, le=50)


class AmazonReportCreateResponse(BaseModel):
    report_id: UUID
    job_id: UUID
    status: str


@router.post("/reports", response_model=AmazonReportCreateResponse)
def create_report(payload: AmazonReportCreateRequest) -> AmazonReportCreateResponse:
    _ = payload
    return AmazonReportCreateResponse(report_id=uuid4(), job_id=uuid4(), status="queued")
