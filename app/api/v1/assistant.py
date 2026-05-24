from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import cast

from app.config import get_settings
from app.database import get_db
from app.models import CourseMaterial, Flashcard, PracticeAttempt, UserProfile
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
from app.services.auth_service import get_current_user
from app.services.assistant_service import AssistantService
from app.services.mistake_service import MistakeService

router = APIRouter(prefix="/assistant", tags=["assistant"])
assistant_service = AssistantService()
settings = get_settings()


def _resolve_scope(
	payload: FlashcardGenerateRequest | PracticeQuestionRequest | PracticeAnswerRequest,
	db: Session,
	current_user: UserProfile,
) -> tuple[list[CourseMaterial], str, int, str]:
	if payload.subject_id:
		materials = cast(
			list[CourseMaterial],
			db.query(CourseMaterial)
			.filter(CourseMaterial.subject_id == payload.subject_id, CourseMaterial.user_id == current_user.id)
			.order_by(CourseMaterial.created_at.asc())
			.all(),
		)
		if not materials:
			raise HTTPException(status_code=404, detail="该学科下暂无资料")
		combined_text = "\n\n".join(str(m.content) for m in materials if m.content)
		primary_id = int(materials[0].id)
		dataset_id = str(materials[0].rag_dataset_id)
		return materials, combined_text, primary_id, dataset_id

	if not payload.material_id:
		raise HTTPException(status_code=422, detail="material_id 和 subject_id 至少提供一个")

	material = cast(
		CourseMaterial | None,
		db.query(CourseMaterial)
		.filter(CourseMaterial.id == payload.material_id, CourseMaterial.user_id == current_user.id)
		.first(),
	)
	if not material:
		raise HTTPException(status_code=404, detail="资料不存在")
	return [material], str(material.content), int(material.id), str(material.rag_dataset_id)


@router.post("/knowledge-cards/generate", response_model=list[FlashcardItem])
@router.post("/flashcards/generate", response_model=list[FlashcardItem])
async def generate_flashcards(
	payload: FlashcardGenerateRequest,
	db: Session = Depends(get_db),
	current_user: UserProfile = Depends(get_current_user),
) -> list[FlashcardItem]:
	_, combined_text, primary_id, _ = _resolve_scope(payload, db, current_user)
	cards = await assistant_service.build_flashcards(combined_text, payload.count, payload.user_level)
	for card in cards:
		db.add(
			Flashcard(
				material_id=primary_id,
				term=card["concept"],
				question=card["explanation"],
				user_id=current_user.id,
			)
		)
	db.commit()
	return [FlashcardItem(**card) for card in cards]


@router.post("/practice/question", response_model=PracticeQuestionResponse)
async def generate_practice_question(
	payload: PracticeQuestionRequest,
	db: Session = Depends(get_db),
	current_user: UserProfile = Depends(get_current_user),
) -> PracticeQuestionResponse:
	_, combined_text, _, dataset_id = _resolve_scope(payload, db, current_user)

	question, refs = await assistant_service.generate_guided_question(
		payload.concept,
		payload.user_level,
		material_text=combined_text,
		dataset_id=dataset_id,
	)
	basis_points = assistant_service._derive_basis_points(payload.concept or "", refs, question=question)
	refs_for_output = await assistant_service.format_supporting_points_for_output(refs, combined_text)
	basis_for_output = await assistant_service.format_supporting_points_for_output(basis_points, combined_text)
	concept = payload.concept or assistant_service._normalize_concept("", combined_text)
	return PracticeQuestionResponse(
		concept=concept,
		question=question,
		references=refs_for_output,
		basis_points=basis_for_output,
	)


@router.post("/practice/answer", response_model=PracticeAnswerResponse)
async def answer_practice_question(
	payload: PracticeAnswerRequest,
	db: Session = Depends(get_db),
	current_user: UserProfile = Depends(get_current_user),
) -> PracticeAnswerResponse:
	_, combined_text, primary_id, dataset_id = _resolve_scope(payload, db, current_user)

	refs = await assistant_service.rag_client.retrieve(
		query=payload.concept or payload.question,
		source_text=combined_text,
		top_k=3,
		dataset_id=dataset_id,
	)

	eval_result = await assistant_service.evaluate_answer(
		concept=payload.concept,
		question=payload.question,
		answer=payload.answer,
		references=refs,
	)
	basis_points = assistant_service._derive_basis_points(payload.concept, refs, question=payload.question)
	refs_for_output = await assistant_service.format_supporting_points_for_output(refs, combined_text)
	basis_for_output = await assistant_service.format_supporting_points_for_output(basis_points, combined_text)

	is_correct = eval_result.score >= settings.score_pass_line
	attempt = PracticeAttempt(
		material_id=primary_id,
		concept=payload.concept,
		question=payload.question,
		answer=payload.answer,
		score=eval_result.score,
		feedback=eval_result.feedback,
		is_correct=is_correct,
		user_id=current_user.id,
	)
	db.add(attempt)

	if not is_correct:
		reason = f"{eval_result.feedback}；遗漏点: {', '.join(eval_result.missing_points)}"
		MistakeService.upsert_mistake(
			db=db,
			material_id=primary_id,
			concept=payload.concept,
			question=payload.question,
			answer=payload.answer,
			correction=eval_result.correction,
			reason=reason,
			user_id=current_user.id,
		)
	else:
		db.commit()

	return PracticeAnswerResponse(
		score=eval_result.score,
		is_correct=is_correct,
		feedback=eval_result.feedback,
		correction=eval_result.correction,
		references=refs_for_output,
		basis_points=basis_for_output,
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



