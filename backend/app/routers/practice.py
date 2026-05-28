import asyncio
import json
from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import PracticeSession, User, WrongAnswer
from app.deps import get_current_user, get_db
from app.schemas import PracticeSubmitOut, PracticeSubmitRequest, PracticeSessionOut, QuizGenerateRequest, QuizQuestionOut
from app.services.quiz import generate_quiz
from app.services.ragflow import RagflowError
from app.utils.id_gen import new_id
from app.utils.ownership import get_owned_subject

router = APIRouter(prefix="/practice", tags=["practice"])


@router.post("/generate", response_model=list[QuizQuestionOut])
async def generate_practice(
    body: QuizGenerateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_owned_subject(db, body.subject_id, user)
    return await generate_quiz(db, body.subject_id, body.count)


@router.post("/generate/stream")
async def generate_practice_stream(
    body: QuizGenerateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_owned_subject(db, body.subject_id, user)

    queue: asyncio.Queue[dict] = asyncio.Queue()

    def on_progress(percent: int, message: str) -> None:
        queue.put_nowait({"type": "progress", "progress": percent, "message": message})

    async def worker() -> None:
        try:
            questions = await generate_quiz(
                db,
                body.subject_id,
                body.count,
                on_progress=on_progress,
            )
            if not questions:
                await queue.put(
                    {"type": "error", "message": "该科目暂无知识卡片，请先从上传资料中抽取重要概念"}
                )
                return
            await queue.put(
                {
                    "type": "done",
                    "progress": 100,
                    "message": f"完成，共生成 {len(questions)} 道题",
                    "questions": [q.model_dump(mode="json", by_alias=True) for q in questions],
                }
            )
        except RagflowError as exc:
            await queue.put({"type": "error", "message": str(exc)})
        except Exception as exc:
            await queue.put({"type": "error", "message": f"生成题目失败: {exc}"})

    async def event_stream():
        task = asyncio.create_task(worker())
        try:
            while True:
                item = await queue.get()
                yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
                if item.get("type") in ("done", "error"):
                    break
        finally:
            await task

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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
