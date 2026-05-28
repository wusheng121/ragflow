from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import PracticeSession, User
from app.deps import get_current_user, get_db
from app.schemas import PracticeSessionOut
from app.utils.ownership import owned_subject_ids

router = APIRouter(prefix="/history", tags=["history"])


@router.get("", response_model=list[PracticeSessionOut])
def list_history(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    subject_ids = owned_subject_ids(db, user)
    if not subject_ids:
        return []

    sessions = (
        db.query(PracticeSession)
        .filter(PracticeSession.subject_id.in_(subject_ids))
        .order_by(PracticeSession.created_at.desc())
        .all()
    )
    return [
        PracticeSessionOut(
            id=s.id,
            subject_id=s.subject_id,
            score=s.score,
            total=s.total,
            duration=s.duration,
            created_at=s.created_at,
        )
        for s in sessions
    ]
