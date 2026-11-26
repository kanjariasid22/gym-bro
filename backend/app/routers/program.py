from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.domain import programs as program_domain
from app.models import User
from app.schemas import ProgramOut, ProgramPut, ProgramSummaryOut

router = APIRouter(tags=["program"])


@router.get("/program", response_model=ProgramOut | None)
def get_program(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProgramOut | None:
    return program_domain.get_current_program(db, user.id)


@router.put("/program", response_model=ProgramOut)
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


@router.get("/programs", response_model=list[ProgramSummaryOut])
def list_programs(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ProgramSummaryOut]:
    return program_domain.list_programs(db, user.id)


@router.get("/programs/{program_id}", response_model=ProgramOut)
def get_program_by_id(
    program_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProgramOut:
    return program_domain.get_program_detail(db, user.id, program_id)
