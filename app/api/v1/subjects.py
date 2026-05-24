from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import StudySubject, UserProfile
from app.schemas import SubjectCreate, SubjectRead
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/subjects", tags=["subjects"])


def _to_subject_read(subject: StudySubject) -> SubjectRead:
    return SubjectRead(
        id=subject.id,
        name=subject.name,
        description=subject.description,
        user_id=subject.user_id,
        created_at=subject.created_at,
        materials_count=len(subject.materials or []),
    )


@router.post("", response_model=SubjectRead)
def create_subject(
    payload: SubjectCreate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user),
) -> SubjectRead:
    exists = (
        db.query(StudySubject)
        .filter(StudySubject.user_id == current_user.id, StudySubject.name == payload.name.strip())
        .first()
    )
    if exists:
        raise HTTPException(status_code=400, detail="该学科名称已存在")

    subject = StudySubject(name=payload.name.strip(), description=payload.description.strip(), user_id=current_user.id)
    db.add(subject)
    db.commit()
    db.refresh(subject)
    return _to_subject_read(subject)


@router.get("", response_model=list[SubjectRead])
def list_subjects(
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user),
) -> list[SubjectRead]:
    subjects = (
        db.query(StudySubject)
        .filter(StudySubject.user_id == current_user.id)
        .order_by(StudySubject.created_at.desc())
        .all()
    )
    return [_to_subject_read(item) for item in subjects]


@router.get("/{subject_id}", response_model=SubjectRead)
def get_subject(
    subject_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user),
) -> SubjectRead:
    subject = (
        db.query(StudySubject)
        .filter(StudySubject.id == subject_id, StudySubject.user_id == current_user.id)
        .first()
    )
    if not subject:
        raise HTTPException(status_code=404, detail="学科不存在")
    return _to_subject_read(subject)

