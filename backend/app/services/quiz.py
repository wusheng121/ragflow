import random

from sqlalchemy.orm import Session

from app.database import KnowledgeCard
from app.schemas import QuizQuestionOut
from app.utils.id_gen import new_id


def generate_quiz(db: Session, subject_id: str, count: int) -> list[QuizQuestionOut]:
    cards = (
        db.query(KnowledgeCard)
        .filter(KnowledgeCard.subject_id == subject_id)
        .all()
    )
    if not cards:
        return []

    selected = random.sample(cards, k=min(count, len(cards)))
    questions: list[QuizQuestionOut] = []

    for card in selected:
        pool = [c for c in cards if c.id != card.id]
        distractors = random.sample([c.summary for c in pool], k=min(3, len(pool))) if pool else []
        while len(distractors) < 3:
            distractors.append("以上都不正确")
        options = [card.summary, *distractors[:3]]
        random.shuffle(options)
        questions.append(
            QuizQuestionOut(
                id=new_id(),
                card_id=card.id,
                subject_id=card.subject_id,
                question=f"关于「{card.concept}」，以下哪项描述最准确？",
                options=options,
                correct_index=options.index(card.summary),
                explanation=card.detail or card.summary,
            )
        )
    return questions
