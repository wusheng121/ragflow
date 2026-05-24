from sqlalchemy.orm import Session

from app.models import MistakeNote


class MistakeService:
    @staticmethod
    def upsert_mistake(
        db: Session,
        material_id: int,
        concept: str,
        question: str,
        answer: str,
        correction: str,
        reason: str,
        user_id: int | None = None,
    ) -> MistakeNote:
        existing = (
            db.query(MistakeNote)
            .filter(MistakeNote.material_id == material_id, MistakeNote.concept == concept, MistakeNote.user_id == user_id)
            .order_by(MistakeNote.updated_at.desc())
            .first()
        )

        if existing:
            existing.last_question = question
            existing.user_answer = answer
            existing.assistant_correction = correction
            existing.reason = reason
            existing.review_count += 1
            existing.status = "reviewing" if existing.review_count > 1 else "open"
            existing.user_id = user_id
            db.add(existing)
            db.commit()
            db.refresh(existing)
            return existing

        note = MistakeNote(
            material_id=material_id,
            concept=concept,
            last_question=question,
            user_answer=answer,
            assistant_correction=correction,
            user_id=user_id,
            reason=reason,
            status="open",
        )
        db.add(note)
        db.commit()
        db.refresh(note)
        return note

