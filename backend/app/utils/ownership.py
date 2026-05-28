from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.database import KnowledgeCard, Subject, User, WrongAnswer


def get_owned_subject(db: Session, subject_id: str, user: User) -> Subject:
    subject = db.get(Subject, subject_id)
    if not subject or subject.user_id != user.id:
        raise HTTPException(status_code=404, detail="科目不存在")
    return subject


def owned_subject_ids(db: Session, user: User) -> list[str]:
    rows = db.query(Subject.id).filter(Subject.user_id == user.id).all()
    return [r[0] for r in rows]


def get_owned_card(db: Session, card_id: str, user: User) -> KnowledgeCard:
    card = db.get(KnowledgeCard, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="知识卡片不存在")
    get_owned_subject(db, card.subject_id, user)
    return card


def get_owned_wrong_item(db: Session, item_id: str, user: User) -> WrongAnswer:
    item = db.get(WrongAnswer, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="错题不存在")
    get_owned_subject(db, item.subject_id, user)
    return item
