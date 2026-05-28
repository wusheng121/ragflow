from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import KnowledgeCard, PracticeSession, Subject, User, WrongAnswer
from app.deps import get_current_user, get_db
from app.schemas import StatsOut
from app.utils.ownership import owned_subject_ids

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("", response_model=StatsOut)
def get_stats(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    subject_ids = owned_subject_ids(db, user)
    if not subject_ids:
        return StatsOut(subject_count=0, card_count=0, wrong_count=0, session_count=0)

    return StatsOut(
        subject_count=db.query(func.count(Subject.id)).filter(Subject.id.in_(subject_ids)).scalar() or 0,
        card_count=(
            db.query(func.count(KnowledgeCard.id))
            .filter(KnowledgeCard.subject_id.in_(subject_ids))
            .scalar()
            or 0
        ),
        wrong_count=(
            db.query(func.count(WrongAnswer.id))
            .filter(WrongAnswer.subject_id.in_(subject_ids))
            .scalar()
            or 0
        ),
        session_count=(
            db.query(func.count(PracticeSession.id))
            .filter(PracticeSession.subject_id.in_(subject_ids))
            .scalar()
            or 0
        ),
    )
