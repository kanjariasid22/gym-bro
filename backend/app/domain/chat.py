"""Chat message persistence + pagination."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AgentMode, ChatMessage, ChatRole


def add_message(
    db: Session,
    user_id: int,
    role: ChatRole,
    content: str,
    mode: AgentMode | None = None,
) -> ChatMessage:
    row = ChatMessage(user_id=user_id, role=role, content=content, mode=mode)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_messages(
    db: Session,
    user_id: int,
    *,
    limit: int = 30,
    before_id: int | None = None,
) -> list[ChatMessage]:
    """Return newest-first page, then reverse to chronological for the UI."""
    q = select(ChatMessage).where(ChatMessage.user_id == user_id)
    if before_id is not None:
        q = q.where(ChatMessage.id < before_id)
    q = q.order_by(ChatMessage.id.desc()).limit(limit)
    rows = list(db.scalars(q).all())
    rows.reverse()
    return rows
