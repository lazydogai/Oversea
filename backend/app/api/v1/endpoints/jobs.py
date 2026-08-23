from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.mock_pipeline import create_search_job, get_mock_job


router = APIRouter()


class JobCreateRequest(BaseModel):
    keyword: str = Field(min_length=1)
    platform: str = "amazon"
    locale: str = "US"
    top_n: int = Field(default=50, ge=1, le=50)


class JobCreateResponse(BaseModel):
    job_id: str
    status: str
    keyword: str
    progress: int


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: int
    keyword: str
    platform: str
    locale: str
    top_n: int
    created_at: str
    updated_at: str
    error_message: str | None = None
    report: dict | None = None


@router.post("/jobs", response_model=JobCreateResponse)
async def create_job(payload: JobCreateRequest) -> JobCreateResponse:
    job = create_search_job(
        keyword=payload.keyword,
        platform=payload.platform,
        locale=payload.locale,
        top_n=payload.top_n,
    )
    return JobCreateResponse(
        job_id=job["job_id"],
        status=job["status"],
        keyword=job["keyword"],
        progress=job["progress"],
    )


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
def read_job(job_id: UUID) -> JobStatusResponse:
    job = get_mock_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return JobStatusResponse(**job)
