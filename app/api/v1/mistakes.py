from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import MistakeNote, UserProfile
from app.schemas import MistakeRead, MistakeUpdateRequest
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/mistakes", tags=["mistakes"])


@router.get("", response_model=list[MistakeRead])
def list_mistakes(db: Session = Depends(get_db), current_user: UserProfile = Depends(get_current_user)) -> list[MistakeNote]:
    query = db.query(MistakeNote).options(joinedload(MistakeNote.material)).order_by(MistakeNote.updated_at.desc())
    query = query.filter(MistakeNote.user_id == current_user.id)
    return query.all()


@router.put("/{mistake_id}", response_model=MistakeRead)
def update_mistake(mistake_id: int, payload: MistakeUpdateRequest, db: Session = Depends(get_db), current_user: UserProfile = Depends(get_current_user)) -> MistakeNote:
    note = db.query(MistakeNote).filter(MistakeNote.id == mistake_id, MistakeNote.user_id == current_user.id).first()
    if not note:
        raise HTTPException(status_code=404, detail="错题不存在")

    if payload.reason is not None:
        note.reason = payload.reason
    if payload.user_note is not None:
        note.user_note = payload.user_note
    if payload.status is not None:
        note.status = payload.status

    db.add(note)
    db.commit()
    db.refresh(note)
    return note


@router.post("/{mistake_id}/review", response_model=MistakeRead)
def mark_reviewed(mistake_id: int, db: Session = Depends(get_db), current_user: UserProfile = Depends(get_current_user)) -> MistakeNote:
    note = db.query(MistakeNote).filter(MistakeNote.id == mistake_id, MistakeNote.user_id == current_user.id).first()
    if not note:
        raise HTTPException(status_code=404, detail="错题不存在")

    note.review_count += 1
    if note.review_count >= 3:
        note.status = "mastered"
    else:
        note.status = "reviewing"

    db.add(note)
    db.commit()
    db.refresh(note)
    return note

