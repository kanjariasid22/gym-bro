"""Program CRUD domain — archive-on-upsert, one active per user."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.domain.exercises import normalize_key, resolve_exercise_name, title_case_fallback
from app.models import PlannedExercise, Program, ProgramDay, ProgramStatus
from app.schemas import ProgramPut


def _with_days():
    return selectinload(Program.days).selectinload(ProgramDay.exercises)


def get_current_program(db: Session, user_id: int) -> Program | None:
    return db.scalar(
        select(Program)
        .options(_with_days())
        .where(
            Program.user_id == user_id,
            Program.status == ProgramStatus.active.value,
        )
        .order_by(Program.updated_at.desc())
    )


def list_programs(db: Session, user_id: int) -> list[Program]:
    return list(
        db.scalars(
            select(Program)
            .where(Program.user_id == user_id)
            .order_by(Program.created_at.desc())
        ).all()
    )


def get_program_detail(db: Session, user_id: int, program_id: int) -> Program:
    prog = db.scalar(
        select(Program)
        .options(_with_days())
        .where(Program.id == program_id, Program.user_id == user_id)
    )
    if prog is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")
    return prog


def _archive_active(db: Session, user_id: int) -> None:
    now = datetime.now(timezone.utc)
    actives = list(
        db.scalars(
            select(Program).where(
                Program.user_id == user_id,
                Program.status == ProgramStatus.active.value,
            )
        ).all()
    )
    for prog in actives:
        prog.status = ProgramStatus.archived.value
        prog.archived_at = now
        prog.updated_at = now


def upsert_program(db: Session, user_id: int, payload: ProgramPut) -> Program:
    """Archive current active program (if any), then insert a new active program."""
    _archive_active(db, user_id)
    db.flush()

    program = Program(
        user_id=user_id,
        status=ProgramStatus.active.value,
        goals=payload.goals,
        end_date=payload.end_date,
        notes=payload.notes,
    )
    db.add(program)
    db.flush()

    for day_in in payload.days:
        day = ProgramDay(
            program_id=program.id,
            day_index=day_in.day_index,
            label=day_in.label,
            scheduled_date=day_in.scheduled_date,
        )
        db.add(day)
        db.flush()

        for i, ex_in in enumerate(day_in.exercises):
            if ex_in.canonical_name and ex_in.normalized_key:
                raw = ex_in.raw_name
                canonical = ex_in.canonical_name
                key = ex_in.normalized_key
            else:
                resolved = resolve_exercise_name(db, user_id, ex_in.raw_name)
                raw = resolved.raw_name
                canonical = ex_in.canonical_name or resolved.canonical_name
                key = ex_in.normalized_key or resolved.normalized_key
                if not key:
                    key = normalize_key(canonical or title_case_fallback(raw))

            db.add(
                PlannedExercise(
                    program_day_id=day.id,
                    order_index=ex_in.order_index if ex_in.order_index else i,
                    raw_name=raw,
                    canonical_name=canonical,
                    normalized_key=key,
                    target_sets=ex_in.target_sets,
                    target_reps=ex_in.target_reps,
                    notes=ex_in.notes,
                )
            )

    db.commit()
    return get_current_program(db, user_id)  # type: ignore[return-value]
