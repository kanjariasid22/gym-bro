from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agents.graph import run_handoff_after_complete
from app.database import get_db
from app.deps import get_current_user
from app.domain import sessions as session_domain
from app.domain import sets as set_domain
from app.models import User
from app.rate_limit import check_rate_limit, client_key
from app.schemas import SessionDetailOut, SessionOut, SetCreate, SetLogOut

router = APIRouter(prefix="/sessions", tags=["sessions"])


class CompleteBody(BaseModel):
    summary: str | None = None
    run_handoff: bool = True


class CompleteResponse(BaseModel):
    session: SessionOut
    handoff: dict | None = None


@router.post("/start", response_model=SessionOut, status_code=201)
def start_session(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SessionOut:
    return session_domain.start_workout(db, user.id)


@router.post("/{session_id}/complete", response_model=CompleteResponse)
def complete_session(
    session_id: int,
    request: Request,
    body: CompleteBody | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CompleteResponse:
    summary = body.summary if body else None
    run_handoff = body.run_handoff if body else True
    session = session_domain.complete_workout(db, user.id, session_id, summary)
    handoff = None
    if run_handoff:
        check_rate_limit(client_key(request, user.id))
        handoff = run_handoff_after_complete(db, user, session_id)
    return CompleteResponse(session=session, handoff=handoff)


@router.post("/{session_id}/cancel", response_model=SessionOut)
def cancel_session(
    session_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SessionOut:
    return session_domain.cancel_workout(db, user.id, session_id)


@router.get("/active", response_model=SessionOut | None)
def active_session(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SessionOut | None:
    return session_domain.get_active_session(db, user.id)


@router.get("", response_model=list[SessionOut])
def list_sessions(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[SessionOut]:
    return session_domain.list_sessions(db, user.id)


@router.get("/{session_id}", response_model=SessionDetailOut)
def session_detail(
    session_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SessionDetailOut:
    return session_domain.get_session_detail(db, user.id, session_id)


@router.post("/{session_id}/sets", response_model=SetLogOut, status_code=201)
def create_session_set(
    session_id: int,
    payload: SetCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SetLogOut:
    return set_domain.create_set(db, user.id, session_id, payload)
