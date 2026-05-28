from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import KnowledgeCard, User
from app.deps import get_current_user, get_db
from app.schemas import KnowledgeCardOut
from app.utils.ownership import get_owned_card, get_owned_subject, owned_subject_ids

router = APIRouter(prefix="/knowledge-cards", tags=["knowledge-cards"])


@router.get("", response_model=list[KnowledgeCardOut])
def list_knowledge_cards(
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

    cards = (
        db.query(KnowledgeCard)
        .filter(KnowledgeCard.subject_id.in_(subject_ids))
        .order_by(KnowledgeCard.created_at.desc())
        .all()
    )
    return [
        KnowledgeCardOut(
            id=c.id,
            subject_id=c.subject_id,
            concept=c.concept,
            summary=c.summary,
            detail=c.detail or "",
            tags=c.tags or [],
            created_at=c.created_at,
        )
        for c in cards
    ]


@router.delete("", status_code=204)
def delete_knowledge_cards_by_subject(
    subject_id: str = Query(..., alias="subject_id"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_owned_subject(db, subject_id, user)
    db.query(KnowledgeCard).filter(KnowledgeCard.subject_id == subject_id).delete()
    db.commit()
    return None


@router.delete("/{card_id}", status_code=204)
def delete_knowledge_card(
    card_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    card = get_owned_card(db, card_id, user)
    db.delete(card)
    db.commit()
    return None
