"""Pydantic request/response schemas."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import AgentMode, ChatRole, SessionStatus, UnitPreference


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Auth ---


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    unit_preference: UnitPreference = UnitPreference.kg


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(OrmModel):
    id: int
    email: EmailStr
    unit_preference: UnitPreference
    created_at: datetime


# --- Program ---


class PlannedExerciseIn(BaseModel):
    raw_name: str
    canonical_name: str | None = None
    normalized_key: str | None = None
    target_sets: int | None = None
    target_reps: str | None = None
    notes: str | None = None
    order_index: int = 0


class ProgramDayIn(BaseModel):
    day_index: int
    label: str | None = None
    scheduled_date: date | None = None
    exercises: list[PlannedExerciseIn] = Field(default_factory=list)


class ProgramPut(BaseModel):
    goals: str | None = None
    end_date: date | None = None
    notes: str | None = None
    days: list[ProgramDayIn] = Field(default_factory=list)


class PlannedExerciseOut(OrmModel):
    id: int
    order_index: int
    raw_name: str
    canonical_name: str
    normalized_key: str
    target_sets: int | None
    target_reps: str | None
    notes: str | None


class ProgramDayOut(OrmModel):
    id: int
    day_index: int
    label: str | None
    scheduled_date: date | None
    exercises: list[PlannedExerciseOut]


class ProgramOut(OrmModel):
    id: int
    goals: str | None
    end_date: date | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
    days: list[ProgramDayOut]


# --- Sessions / sets ---


class SetLogOut(OrmModel):
    id: int
    session_id: int
    raw_name: str
    canonical_name: str
    normalized_key: str
    set_index: int
    weight: float
    unit: UnitPreference
    reps: int
    notes: str | None
    created_at: datetime
    updated_at: datetime


class SessionOut(OrmModel):
    id: int
    status: SessionStatus
    started_at: datetime
    ended_at: datetime | None
    summary: str | None


class SessionDetailOut(SessionOut):
    set_logs: list[SetLogOut]


class SetCreate(BaseModel):
    raw_name: str
    weight: float
    unit: UnitPreference
    reps: int = Field(ge=0)
    notes: str | None = None
    set_index: int | None = None
    canonical_name: str | None = None


class SetPatch(BaseModel):
    raw_name: str | None = None
    weight: float | None = None
    unit: UnitPreference | None = None
    reps: int | None = Field(default=None, ge=0)
    notes: str | None = None
    set_index: int | None = None


class ExerciseResolveOut(BaseModel):
    raw_name: str
    canonical_name: str
    normalized_key: str
    source: str  # history | groq | fallback


# --- Chat (model only; API later) ---


class ChatMessageOut(OrmModel):
    id: int
    role: ChatRole
    content: str
    mode: AgentMode | None
    created_at: datetime
