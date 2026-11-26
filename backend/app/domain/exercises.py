"""Exercise name resolution: history match first, Groq on miss (stubbed without key)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import PlannedExercise, Program, ProgramDay, SetLog


@dataclass
class ResolvedExercise:
    raw_name: str
    canonical_name: str
    normalized_key: str
    source: str  # history | groq | fallback


def normalize_key(text: str) -> str:
    cleaned = text.lower().strip()
    cleaned = re.sub(r"[^\w\s]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def title_case_fallback(raw: str) -> str:
    return " ".join(part.capitalize() for part in normalize_key(raw).split())


def _history_keys(db: Session, user_id: int, limit: int = 200) -> list[tuple[str, str]]:
    """Return (normalized_key, canonical_name) from user's recent set + plan names."""
    pairs: list[tuple[str, str]] = []

    set_rows = db.scalars(
        select(SetLog)
        .where(SetLog.user_id == user_id)
        .order_by(SetLog.id.desc())
        .limit(limit)
    ).all()
    for row in set_rows:
        pairs.append((row.normalized_key, row.canonical_name))

    plan_rows = db.scalars(
        select(PlannedExercise)
        .join(ProgramDay, PlannedExercise.program_day_id == ProgramDay.id)
        .join(Program, ProgramDay.program_id == Program.id)
        .where(Program.user_id == user_id)
        .limit(limit)
    ).all()
    for row in plan_rows:
        pairs.append((row.normalized_key, row.canonical_name))

    return pairs


def _match_history(raw: str, pairs: list[tuple[str, str]]) -> ResolvedExercise | None:
    key = normalize_key(raw)
    if not key:
        return None

    for nk, canonical in pairs:
        if nk == key:
            return ResolvedExercise(raw, canonical, nk, "history")

    for nk, canonical in pairs:
        if key in nk or nk in key:
            return ResolvedExercise(raw, canonical, nk, "history")

    return None


def _groq_canonicalize(raw: str) -> str | None:
    settings = get_settings()
    if not settings.groq_configured:
        return None

    prompt = (
        "Canonicalize this gym exercise name to Title Case. "
        "Merge common abbreviations. Do not invent equipment the user did not imply. "
        'Respond with JSON only: {"canonical_name": "..."}\n'
        f"Input: {raw}"
    )
    try:
        resp = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.groq_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": get_settings().groq_fast_model or "openai/gpt-oss-20b",
                "messages": [
                    {"role": "system", "content": "You normalize exercise names. JSON only."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0,
                "response_format": {"type": "json_object"},
            },
            timeout=20.0,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        data = json.loads(content)
        name = str(data.get("canonical_name", "")).strip()
        return name or None
    except Exception:
        return None


def resolve_exercise_name(db: Session, user_id: int, raw_text: str) -> ResolvedExercise:
    raw = raw_text.strip()
    pairs = _history_keys(db, user_id)
    hit = _match_history(raw, pairs)
    if hit:
        return hit

    groq_name = _groq_canonicalize(raw)
    if groq_name:
        return ResolvedExercise(
            raw_name=raw,
            canonical_name=groq_name,
            normalized_key=normalize_key(groq_name),
            source="groq",
        )

    # Fallback when Groq key missing or call fails
    canonical = title_case_fallback(raw) or raw
    return ResolvedExercise(
        raw_name=raw,
        canonical_name=canonical,
        normalized_key=normalize_key(canonical),
        source="fallback",
    )
