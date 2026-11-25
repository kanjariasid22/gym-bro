from fastapi import APIRouter

from app.config import get_settings

router = APIRouter(tags=["ops"])


@router.get("/health")
def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "groq_configured": settings.groq_configured,
    }
