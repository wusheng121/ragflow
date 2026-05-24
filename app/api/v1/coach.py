from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import CourseMaterial, Flashcard, PracticeAttempt
from app.schemas import (
    ConsistencyRequest,
    ConsistencyResponse,
    FlashcardGenerateRequest,
    FlashcardItem,
    PracticeAnswerRequest,
    PracticeAnswerResponse,
    PracticeQuestionRequest,
    PracticeQuestionResponse,
)
from app.services.assistant_service import AssistantService
from app.services.mistake_service import MistakeService

router = APIRouter(prefix="/assistant", tags=["assistant"])
assistant_service = AssistantService()
settings = get_settings()


@router.post("/flashcards/generate", response_model=list[FlashcardItem])
async def generate_flashcards(payload: FlashcardGenerateRequest, db: Session = Depends(get_db)) -> list[FlashcardItem]:
    material = db.query(CourseMaterial).filter(CourseMaterial.id == payload.material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="资料不存在")

    cards = await assistant_service.build_flashcards(material.content, payload.count, payload.user_level)
    for card in cards:
        db.add(Flashcard(material_id=material.id, term=card["term"], question=card["question"]))
    db.commit()
    return [FlashcardItem(**card) for card in cards]


@router.post("/practice/question", response_model=PracticeQuestionResponse)
async def generate_practice_question(
    payload: PracticeQuestionRequest,
    db: Session = Depends(get_db),
) -> PracticeQuestionResponse:
    material = db.query(CourseMaterial).filter(CourseMaterial.id == payload.material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="资料不存在")

    question, refs = await assistant_service.generate_guided_question(
        payload.concept,
        payload.user_level,
        material_text=material.content,
        dataset_id=material.rag_dataset_id,
    )
    concept = payload.concept or "综合概念"
    return PracticeQuestionResponse(concept=concept, question=question, references=refs)


@router.post("/practice/answer", response_model=PracticeAnswerResponse)
async def answer_practice_question(
    payload: PracticeAnswerRequest,
    db: Session = Depends(get_db),
) -> PracticeAnswerResponse:
    material = db.query(CourseMaterial).filter(CourseMaterial.id == payload.material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="资料不存在")

    refs = await assistant_service.rag_client.retrieve(
        query=payload.concept or payload.question,
        source_text=material.content,
        top_k=3,
        dataset_id=material.rag_dataset_id,
    )

    eval_result = await assistant_service.evaluate_answer(
        concept=payload.concept,
        question=payload.question,
        answer=payload.answer,
        references=refs,
    )

    is_correct = eval_result.score >= settings.score_pass_line
    attempt = PracticeAttempt(
        material_id=material.id,
        concept=payload.concept,
        question=payload.question,
        answer=payload.answer,
        score=eval_result.score,
        feedback=eval_result.feedback,
        is_correct=is_correct,
    )
    db.add(attempt)

    if not is_correct:
        reason = f"{eval_result.feedback}；遗漏点: {', '.join(eval_result.missing_points)}"
        MistakeService.upsert_mistake(
            db=db,
            material_id=material.id,
            concept=payload.concept,
            question=payload.question,
            answer=payload.answer,
            correction=eval_result.correction,
            reason=reason,
        )
    else:
        db.commit()

    return PracticeAnswerResponse(
        score=eval_result.score,
        is_correct=is_correct,
        feedback=eval_result.feedback,
        correction=eval_result.correction,
        references=refs,
    )


@router.post("/consistency", response_model=ConsistencyResponse)
def consistency_score(payload: ConsistencyRequest) -> ConsistencyResponse:
    score = assistant_service._consistency_score(payload.answer, payload.references)
    if score >= 80:
        explanation = "与知识源基本一致"
    elif score >= 60:
        explanation = "部分一致，仍需补充关键条件"
    else:
        explanation = "与知识源偏差较大，建议重读原文后重答"
    return ConsistencyResponse(consistency_score=score, explanation=explanation)


