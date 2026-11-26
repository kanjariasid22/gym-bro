from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agents.graph import run_chat_turn
from app.database import get_db
from app.deps import get_current_user
from app.domain import chat as chat_domain
from app.models import User
from app.rate_limit import check_rate_limit, client_key
from app.schemas import ChatMessageOut

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)


class ChatResponse(BaseModel):
    reply: str
    mode: str
    intent: str | None = None
    tool_results: list = Field(default_factory=list)
    ui_hints: dict = Field(default_factory=dict)
    handoff_summary: str | None = None


@router.post("", response_model=ChatResponse)
def post_chat(
    body: ChatRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ChatResponse:
    check_rate_limit(client_key(request, user.id))
    result = run_chat_turn(db, user, body.message.strip())
    return ChatResponse(**result)


@router.get("/messages", response_model=list[ChatMessageOut])
def get_messages(
    before: int | None = Query(default=None, description="Load messages with id < before"),
    limit: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ChatMessageOut]:
    return chat_domain.list_messages(db, user.id, limit=limit, before_id=before)
