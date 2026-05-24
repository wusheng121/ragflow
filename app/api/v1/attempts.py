from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import PracticeAttempt, UserProfile
from app.schemas import AttemptRead
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/attempts", tags=["attempts"])


@router.get("", response_model=list[AttemptRead])
def list_attempts(
    db: Session = Depends(get_db),
    material_id: int | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    current_user: UserProfile = Depends(get_current_user),
) -> list[PracticeAttempt]:
    query = db.query(PracticeAttempt).options(joinedload(PracticeAttempt.material)).order_by(PracticeAttempt.created_at.desc())
    query = query.filter(PracticeAttempt.user_id == current_user.id)
    if material_id is not None:
        query = query.filter(PracticeAttempt.material_id == material_id)
    return query.limit(limit).all()

