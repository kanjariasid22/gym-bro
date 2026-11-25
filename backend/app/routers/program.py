from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.domain import programs as program_domain
from app.models import User
from app.schemas import ProgramOut, ProgramPut

router = APIRouter(prefix="/program", tags=["program"])


@router.get("", response_model=ProgramOut | None)
def get_program(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProgramOut | None:
    prog = program_domain.get_current_program(db, user.id)
    return prog


@router.put("", response_model=ProgramOut)
def put_program(
    payload: ProgramPut,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProgramOut:
    prog = program_domain.upsert_program(db, user.id, payload)
    if prog is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save program",
        )
    return prog
