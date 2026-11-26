"""Tool implementations shared by Trainer/Guide nodes (same domain as REST)."""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.domain import programs as program_domain
from app.domain import sessions as session_domain
from app.domain import sets as set_domain
from app.domain.exercises import resolve_exercise_name
from app.models import UnitPreference, User
from app.schemas import ProgramDayIn, ProgramPut, PlannedExerciseIn, SetCreate


def tool_start_workout(db: Session, user: User) -> dict[str, Any]:
    s = session_domain.start_workout(db, user.id)
    return {"ok": True, "session_id": s.id, "status": s.status.value}


def tool_complete_workout(
    db: Session, user: User, session_id: int | None = None, summary: str | None = None
) -> dict[str, Any]:
    active = session_domain.get_active_session(db, user.id)
    sid = session_id or (active.id if active else None)
    if sid is None:
        return {"ok": False, "error": "No active session"}
    s = session_domain.complete_workout(db, user.id, sid, summary)
    # Handoff Guide turn is triggered by the chat/session API layer after tools
    return {
        "ok": True,
        "session_id": s.id,
        "status": s.status.value,
        "summary": s.summary,
        "needs_handoff": True,
    }


def tool_cancel_workout(db: Session, user: User, session_id: int | None = None) -> dict[str, Any]:
    active = session_domain.get_active_session(db, user.id)
    sid = session_id or (active.id if active else None)
    if sid is None:
        return {"ok": False, "error": "No active session"}
    s = session_domain.cancel_workout(db, user.id, sid)
    return {"ok": True, "session_id": s.id, "status": s.status.value}


def tool_log_sets(
    db: Session,
    user: User,
    *,
    exercise: str,
    weight: float,
    reps: int,
    unit: str | None = None,
    notes: str | None = None,
    set_count: int = 1,
) -> dict[str, Any]:
    active = session_domain.get_active_session(db, user.id)
    if active is None:
        return {"ok": False, "error": "No active session — start a workout first"}
    u = UnitPreference(unit) if unit in ("kg", "lbs") else user.unit_preference
    created = []
    for _ in range(max(1, set_count)):
        row = set_domain.create_set(
            db,
            user.id,
            active.id,
            SetCreate(
                raw_name=exercise,
                weight=weight,
                unit=u,
                reps=reps,
                notes=notes,
            ),
        )
        created.append(
            {
                "id": row.id,
                "canonical_name": row.canonical_name,
                "set_index": row.set_index,
                "weight": row.weight,
                "unit": row.unit.value,
                "reps": row.reps,
            }
        )
    return {"ok": True, "sets": created, "session_id": active.id}


def _session_overrides(db: Session, user_id: int) -> dict[str, Any]:
    active = session_domain.get_active_session(db, user_id)
    if active is None or not active.plan_overrides_json:
        return {}
    try:
        data = json.loads(active.plan_overrides_json)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def tool_get_today_plan(db: Session, user: User) -> dict[str, Any]:
    prog = program_domain.get_current_program(db, user.id)
    if prog is None:
        return {"ok": True, "program": None, "today": None}
    today = date.today()
    day = next((d for d in prog.days if d.scheduled_date == today), None)
    if day is None and prog.days:
        day = prog.days[0]
    overrides = _session_overrides(db, user.id)
    exercises = []
    for e in day.exercises if day else []:
        ov = overrides.get(e.normalized_key)
        exercises.append(
            {
                "canonical_name": (ov or {}).get("canonical_name") or e.canonical_name,
                "raw_name": (ov or {}).get("raw_name") or e.raw_name,
                "target_sets": e.target_sets,
                "target_reps": e.target_reps,
                "notes": e.notes,
                "swapped": bool(ov),
            }
        )
    return {
        "ok": True,
        "program": {
            "id": prog.id,
            "goals": prog.goals,
            "end_date": prog.end_date.isoformat() if prog.end_date else None,
        },
        "today": {
            "label": day.label if day else None,
            "exercises": exercises,
        }
        if day
        else None,
    }


def tool_upsert_program(db: Session, user: User, payload: dict[str, Any]) -> dict[str, Any]:
    days_in: list[ProgramDayIn] = []
    for d in payload.get("days") or []:
        exercises = [
            PlannedExerciseIn(
                raw_name=e.get("raw_name") or e.get("name") or e.get("canonical_name") or "Exercise",
                canonical_name=e.get("canonical_name"),
                target_sets=e.get("target_sets"),
                target_reps=str(e["target_reps"]) if e.get("target_reps") is not None else None,
                notes=e.get("notes"),
                order_index=int(e.get("order_index") or 0),
            )
            for e in (d.get("exercises") or [])
        ]
        days_in.append(
            ProgramDayIn(
                day_index=int(d.get("day_index") or 0),
                label=d.get("label"),
                scheduled_date=date.fromisoformat(d["scheduled_date"])
                if d.get("scheduled_date")
                else None,
                exercises=exercises,
            )
        )
    end = payload.get("end_date")
    put = ProgramPut(
        goals=payload.get("goals"),
        end_date=date.fromisoformat(end) if isinstance(end, str) else end,
        notes=payload.get("notes"),
        days=days_in,
    )
    prog = program_domain.upsert_program(db, user.id, put)
    return {"ok": True, "program_id": prog.id if prog else None, "days": len(days_in)}


def tool_swap_exercise_today(
    db: Session, user: User, *, from_name: str, to_name: str
) -> dict[str, Any]:
    """Light same-day swap — session-local only; does not mutate the stored program."""
    active = session_domain.get_active_session(db, user.id)
    if active is None:
        return {"ok": False, "error": "Start a workout before swapping exercises"}
    prog = program_domain.get_current_program(db, user.id)
    if prog is None or not prog.days:
        return {"ok": False, "error": "No program to swap against"}
    today = date.today()
    day = next((d for d in prog.days if d.scheduled_date == today), prog.days[0])
    resolved_from = resolve_exercise_name(db, user.id, from_name)
    resolved_to = resolve_exercise_name(db, user.id, to_name)
    matched_key = None
    matched_canonical = None
    for ex in day.exercises:
        if (
            ex.normalized_key == resolved_from.normalized_key
            or resolved_from.normalized_key in ex.normalized_key
            or ex.normalized_key in resolved_from.normalized_key
        ):
            matched_key = ex.normalized_key
            matched_canonical = ex.canonical_name
            break
    if not matched_key:
        return {"ok": False, "error": f"No planned exercise matching '{from_name}' today"}

    overrides = {}
    if active.plan_overrides_json:
        try:
            overrides = json.loads(active.plan_overrides_json)
            if not isinstance(overrides, dict):
                overrides = {}
        except json.JSONDecodeError:
            overrides = {}
    overrides[matched_key] = {
        "raw_name": resolved_to.raw_name,
        "canonical_name": resolved_to.canonical_name,
        "normalized_key": resolved_to.normalized_key,
    }
    active.plan_overrides_json = json.dumps(overrides)
    db.commit()
    return {
        "ok": True,
        "from": matched_canonical or resolved_from.canonical_name,
        "to": resolved_to.canonical_name,
        "day_label": day.label,
        "session_local": True,
        "session_id": active.id,
    }


TOOL_SPECS = [
    {
        "name": "start_workout",
        "description": "Start an active workout session for the user.",
        "params": {},
    },
    {
        "name": "complete_workout",
        "description": "Complete the active workout and optionally attach a summary.",
        "params": {"summary": "string optional"},
    },
    {
        "name": "cancel_workout",
        "description": "Cancel the active workout without full handoff.",
        "params": {},
    },
    {
        "name": "log_sets",
        "description": "Log one or more identical sets for an exercise.",
        "params": {
            "exercise": "string",
            "weight": "number",
            "reps": "integer",
            "unit": "kg|lbs optional",
            "notes": "string optional",
            "set_count": "integer optional default 1",
        },
    },
    {
        "name": "get_today_plan",
        "description": "Fetch current program goals and today's planned exercises.",
        "params": {},
    },
    {
        "name": "upsert_program",
        "description": "Create/replace the training program through an end date.",
        "params": {
            "goals": "string",
            "end_date": "YYYY-MM-DD",
            "notes": "string optional",
            "days": "list of {day_index, label, scheduled_date?, exercises:[{raw_name,target_sets,target_reps,notes}]}",
        },
    },
    {
        "name": "swap_exercise_today",
        "description": "Light same-day swap of one planned exercise (Trainer only).",
        "params": {"from_name": "string", "to_name": "string"},
    },
]


def dispatch_tool(db: Session, user: User, name: str, args: dict[str, Any]) -> dict[str, Any]:
    try:
        if name == "start_workout":
            return tool_start_workout(db, user)
        if name == "complete_workout":
            return tool_complete_workout(
                db, user, summary=args.get("summary")
            )
        if name == "cancel_workout":
            return tool_cancel_workout(db, user)
        if name == "log_sets":
            return tool_log_sets(
                db,
                user,
                exercise=str(args.get("exercise") or args.get("raw_name") or ""),
                weight=float(args.get("weight")),
                reps=int(args.get("reps")),
                unit=args.get("unit"),
                notes=args.get("notes"),
                set_count=int(args.get("set_count") or 1),
            )
        if name == "get_today_plan":
            return tool_get_today_plan(db, user)
        if name == "upsert_program":
            return tool_upsert_program(db, user, args)
        if name == "swap_exercise_today":
            return tool_swap_exercise_today(
                db,
                user,
                from_name=str(args.get("from_name") or ""),
                to_name=str(args.get("to_name") or ""),
            )
        return {"ok": False, "error": f"Unknown tool {name}"}
    except Exception as exc:  # noqa: BLE001 — surface to agent
        return {"ok": False, "error": str(exc)}
