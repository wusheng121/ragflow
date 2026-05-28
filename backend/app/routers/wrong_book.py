from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import User, WrongAnswer
from app.deps import get_current_user, get_db
from app.schemas import WrongAnswerOut
from app.utils.ownership import get_owned_subject, get_owned_wrong_item, owned_subject_ids

router = APIRouter(prefix="/wrong-book", tags=["wrong-book"])


@router.get("", response_model=list[WrongAnswerOut])
def list_wrong_answers(
    subject_id: str | None = Query(default=None, alias="subject_id"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    subject_ids = owned_subject_ids(db, user)
    if not subject_ids:
        return []

    if subject_id:
        get_owned_subject(db, subject_id, user)
        subject_ids = [subject_id]

    items = (
        db.query(WrongAnswer)
        .filter(WrongAnswer.subject_id.in_(subject_ids))
        .order_by(WrongAnswer.created_at.desc())
        .all()
    )
    return [
        WrongAnswerOut(
            id=w.id,
            subject_id=w.subject_id,
            question=w.question,
            user_answer=w.user_answer,
            correct_answer=w.correct_answer,
            concept_id=w.concept_id,
            created_at=w.created_at,
        )
        for w in items
    ]


@router.delete("/{item_id}", status_code=204)
def delete_wrong_answer(
    item_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = get_owned_wrong_item(db, item_id, user)
    db.delete(item)
    db.commit()
    return None
