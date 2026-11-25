"""Workout session domain — shared by REST and agent tools."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import SessionStatus, WorkoutSession


def get_active_session(db: Session, user_id: int) -> WorkoutSession | None:
    return db.scalar(
        select(WorkoutSession)
        .where(
            WorkoutSession.user_id == user_id,
            WorkoutSession.status == SessionStatus.active,
        )
        .order_by(WorkoutSession.started_at.desc())
    )


def start_workout(db: Session, user_id: int) -> WorkoutSession:
    existing = get_active_session(db, user_id)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An active workout session already exists",
        )
    session = WorkoutSession(user_id=user_id, status=SessionStatus.active)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def _get_owned_session(db: Session, user_id: int, session_id: int) -> WorkoutSession:
    session = db.get(WorkoutSession, session_id)
    if session is None or session.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return session


def complete_workout(
    db: Session, user_id: int, session_id: int, summary: str | None = None
) -> WorkoutSession:
    session = _get_owned_session(db, user_id, session_id)
    if session.status != SessionStatus.active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Session is {session.status.value}, not active",
        )
    session.status = SessionStatus.completed
    session.ended_at = datetime.now(timezone.utc)
    if summary is not None:
        session.summary = summary
    db.commit()
    db.refresh(session)
    return session


def cancel_workout(db: Session, user_id: int, session_id: int) -> WorkoutSession:
    session = _get_owned_session(db, user_id, session_id)
    if session.status != SessionStatus.active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Session is {session.status.value}, not active",
        )
    session.status = SessionStatus.cancelled
    session.ended_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(session)
    return session


def list_sessions(db: Session, user_id: int, limit: int = 50) -> list[WorkoutSession]:
    return list(
        db.scalars(
            select(WorkoutSession)
            .where(WorkoutSession.user_id == user_id)
            .order_by(WorkoutSession.started_at.desc())
            .limit(limit)
        ).all()
    )


def get_session_detail(db: Session, user_id: int, session_id: int) -> WorkoutSession:
    session = db.scalar(
        select(WorkoutSession)
        .options(selectinload(WorkoutSession.set_logs))
        .where(WorkoutSession.id == session_id, WorkoutSession.user_id == user_id)
    )
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return session
