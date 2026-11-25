"""Set log domain — create / patch / delete."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.exercises import resolve_exercise_name
from app.models import SessionStatus, SetLog, WorkoutSession
from app.schemas import SetCreate, SetPatch


def _owned_session(db: Session, user_id: int, session_id: int) -> WorkoutSession:
    session = db.get(WorkoutSession, session_id)
    if session is None or session.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return session


def _next_set_index(db: Session, session_id: int, normalized_key: str) -> int:
    current = db.scalar(
        select(func.max(SetLog.set_index)).where(
            SetLog.session_id == session_id,
            SetLog.normalized_key == normalized_key,
        )
    )
    return int(current or 0) + 1


def create_set(db: Session, user_id: int, session_id: int, payload: SetCreate) -> SetLog:
    session = _owned_session(db, user_id, session_id)
    if session.status != SessionStatus.active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Can only add sets to an active session",
        )

    resolved = resolve_exercise_name(db, user_id, payload.raw_name)
    canonical = payload.canonical_name or resolved.canonical_name
    key = resolved.normalized_key
    set_index = payload.set_index or _next_set_index(db, session_id, key)

    row = SetLog(
        session_id=session_id,
        user_id=user_id,
        raw_name=resolved.raw_name,
        canonical_name=canonical,
        normalized_key=key,
        set_index=set_index,
        weight=payload.weight,
        unit=payload.unit,
        reps=payload.reps,
        notes=payload.notes,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def patch_set(db: Session, user_id: int, set_id: int, payload: SetPatch) -> SetLog:
    row = db.get(SetLog, set_id)
    if row is None or row.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Set not found")

    data = payload.model_dump(exclude_unset=True)
    if "raw_name" in data and data["raw_name"] is not None:
        resolved = resolve_exercise_name(db, user_id, data["raw_name"])
        row.raw_name = resolved.raw_name
        row.canonical_name = resolved.canonical_name
        row.normalized_key = resolved.normalized_key

    for field in ("weight", "unit", "reps", "notes", "set_index"):
        if field in data:
            setattr(row, field, data[field])

    db.commit()
    db.refresh(row)
    return row


def delete_set(db: Session, user_id: int, set_id: int) -> None:
    row = db.get(SetLog, set_id)
    if row is None or row.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Set not found")
    db.delete(row)
    db.commit()
