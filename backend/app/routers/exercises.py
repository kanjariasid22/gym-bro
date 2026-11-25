from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.domain.exercises import resolve_exercise_name
from app.models import User
from app.schemas import ExerciseResolveOut

router = APIRouter(prefix="/exercises", tags=["exercises"])


class ResolveBody(BaseModel):
    raw_name: str = Field(min_length=1)


@router.post("/resolve", response_model=ExerciseResolveOut)
def resolve(
    body: ResolveBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ExerciseResolveOut:
    resolved = resolve_exercise_name(db, user.id, body.raw_name)
    return ExerciseResolveOut(
        raw_name=resolved.raw_name,
        canonical_name=resolved.canonical_name,
        normalized_key=resolved.normalized_key,
        source=resolved.source,
    )
