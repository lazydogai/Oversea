from fastapi import APIRouter


router = APIRouter()


@router.get("/readyz")
def readyz() -> dict[str, str]:
    return {"status": "ready"}

