from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import PracticeSession, User, WrongAnswer
from app.deps import get_current_user, get_db
from app.schemas import PracticeSubmitOut, PracticeSubmitRequest, PracticeSessionOut, QuizGenerateRequest, QuizQuestionOut
from app.services.quiz import generate_quiz
from app.utils.id_gen import new_id
from app.utils.ownership import get_owned_subject

router = APIRouter(prefix="/practice", tags=["practice"])


@router.post("/generate", response_model=list[QuizQuestionOut])
def generate_practice(
    body: QuizGenerateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_owned_subject(db, body.subject_id, user)
    return generate_quiz(db, body.subject_id, body.count)


@router.post("/submit", response_model=PracticeSubmitOut)
def submit_practice(
    body: PracticeSubmitRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_owned_subject(db, body.subject_id, user)
    correct = sum(1 for a in body.answers if a.is_correct)
    now = datetime.utcnow()

    session = PracticeSession(
        id=new_id(),
        subject_id=body.subject_id,
        score=correct,
        total=len(body.answers),
        duration=body.duration,
        created_at=now,
    )
    db.add(session)

    wrong_count = 0
    for ans in body.answers:
        if ans.is_correct:
            continue
        wrong_count += 1
        db.add(
            WrongAnswer(
                id=new_id(),
                subject_id=body.subject_id,
                question=ans.question,
                user_answer=ans.user_answer,
                correct_answer=ans.correct_answer,
                concept_id=ans.card_id,
                created_at=now,
            )
        )

    db.commit()
    db.refresh(session)

    return PracticeSubmitOut(
        session=PracticeSessionOut(
            id=session.id,
            subject_id=session.subject_id,
            score=session.score,
            total=session.total,
            duration=session.duration,
            created_at=session.created_at,
        ),
        wrong_count=wrong_count,
    )
