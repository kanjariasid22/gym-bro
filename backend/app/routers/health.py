from fastapi import APIRouter

from app.config import get_settings
from app.memory import memory_backend

router = APIRouter(tags=["ops"])


@router.get("/health")
def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "groq_configured": settings.groq_configured,
        "memory_backend": memory_backend(),
    }
