"""SQLAlchemy models — system of record."""

from __future__ import annotations

import enum
from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UnitPreference(str, enum.Enum):
    kg = "kg"
    lbs = "lbs"


class SessionStatus(str, enum.Enum):
    active = "active"
    completed = "completed"
    cancelled = "cancelled"


class ChatRole(str, enum.Enum):
    user = "user"
    assistant = "assistant"
    system = "system"


class AgentMode(str, enum.Enum):
    guide = "guide"
    trainer = "trainer"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    unit_preference: Mapped[UnitPreference] = mapped_column(
        Enum(UnitPreference), default=UnitPreference.kg, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    programs: Mapped[list[Program]] = relationship(back_populates="user")
    sessions: Mapped[list[WorkoutSession]] = relationship(back_populates="user")
    set_logs: Mapped[list[SetLog]] = relationship(back_populates="user")
    chat_messages: Mapped[list[ChatMessage]] = relationship(back_populates="user")


class Program(Base):
    __tablename__ = "programs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    goals: Mapped[str | None] = mapped_column(Text, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped[User] = relationship(back_populates="programs")
    days: Mapped[list[ProgramDay]] = relationship(
        back_populates="program",
        cascade="all, delete-orphan",
        order_by="ProgramDay.day_index",
    )


class ProgramDay(Base):
    __tablename__ = "program_days"
    __table_args__ = (UniqueConstraint("program_id", "day_index", name="uq_program_day"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    program_id: Mapped[int] = mapped_column(
        ForeignKey("programs.id", ondelete="CASCADE"), index=True
    )
    day_index: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    scheduled_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    program: Mapped[Program] = relationship(back_populates="days")
    exercises: Mapped[list[PlannedExercise]] = relationship(
        back_populates="program_day",
        cascade="all, delete-orphan",
        order_by="PlannedExercise.order_index",
    )


class PlannedExercise(Base):
    __tablename__ = "planned_exercises"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    program_day_id: Mapped[int] = mapped_column(
        ForeignKey("program_days.id", ondelete="CASCADE"), index=True
    )
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    raw_name: Mapped[str] = mapped_column(String(200), nullable=False)
    canonical_name: Mapped[str] = mapped_column(String(200), nullable=False)
    normalized_key: Mapped[str] = mapped_column(String(200), index=True, nullable=False)
    target_sets: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_reps: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    program_day: Mapped[ProgramDay] = relationship(back_populates="exercises")


class WorkoutSession(Base):
    __tablename__ = "workout_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus), default=SessionStatus.active, nullable=False, index=True
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped[User] = relationship(back_populates="sessions")
    set_logs: Mapped[list[SetLog]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="SetLog.set_index",
    )


class SetLog(Base):
    __tablename__ = "set_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("workout_sessions.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    raw_name: Mapped[str] = mapped_column(String(200), nullable=False)
    canonical_name: Mapped[str] = mapped_column(String(200), nullable=False)
    normalized_key: Mapped[str] = mapped_column(String(200), index=True, nullable=False)
    set_index: Mapped[int] = mapped_column(Integer, nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[UnitPreference] = mapped_column(Enum(UnitPreference), nullable=False)
    reps: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    session: Mapped[WorkoutSession] = relationship(back_populates="set_logs")
    user: Mapped[User] = relationship(back_populates="set_logs")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[ChatRole] = mapped_column(Enum(ChatRole), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[AgentMode | None] = mapped_column(Enum(AgentMode), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    user: Mapped[User] = relationship(back_populates="chat_messages")
