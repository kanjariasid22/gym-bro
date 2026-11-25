from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.domain import sets as set_domain
from app.models import User
from app.schemas import SetLogOut, SetPatch

router = APIRouter(prefix="/sets", tags=["sets"])


@router.patch("/{set_id}", response_model=SetLogOut)
def patch_set(
    set_id: int,
    payload: SetPatch,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SetLogOut:
    return set_domain.patch_set(db, user.id, set_id, payload)


@router.delete("/{set_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_set(
    set_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    set_domain.delete_set(db, user.id, set_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
