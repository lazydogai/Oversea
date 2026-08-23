from fastapi import APIRouter

from app.api.v1.endpoints.amazon_reports import router as amazon_reports_router
from app.api.v1.endpoints.jobs import router as jobs_router
from app.api.v1.endpoints.health import router as health_router


api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(jobs_router, tags=["jobs"])
api_router.include_router(amazon_reports_router, prefix="/amazon", tags=["amazon"])
