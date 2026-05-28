import json
import random
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import KnowledgeCard, Subject
from app.schemas import QuizQuestionOut
from app.services.ragflow import RagflowClient, RagflowError
from app.utils.id_gen import new_id

ProgressCallback = Callable[[int, str], None]


def _report(on_progress: ProgressCallback | None, percent: int, message: str) -> None:
    if on_progress:
        on_progress(min(99, max(0, percent)), message)


def _build_cards_context(cards: list[KnowledgeCard]) -> str:
    lines = []
    for i, card in enumerate(cards, 1):
        lines.append(f"{i}. [card_id={card.id}] 【{card.concept}】")
        lines.append(f"   简介：{card.summary}")
        if card.detail:
            lines.append(f"   详情：{card.detail[:400]}")
        lines.append("")
    return "\n".join(lines)


def _build_quiz_prompt(subject_name: str, cards_context: str, count: int) -> str:
    return f"""你是一位专业的课程测验出题助手。请根据下方「{subject_name}」科目的知识卡片，生成 {count} 道单项选择题。

**出题要求：**
1. 题目和全部 4 个选项必须由你原创生成，考查对概念的理解，不要直接复制知识卡片中的「简介」原文作为选项
2. 每题 4 个选项，仅 1 个正确；干扰项应合理但错误
3. 题干清晰、选项长度尽量均衡，避免「以上都对/都不对」类选项
4. 每题关联一个 card_id（从下方知识卡片 id 中选择最相关的一个）
5. explanation 写简要解析（1-3 句）

**输出格式：** 仅返回 JSON 数组，不要 markdown，不要其他文字：
[
  {{
    "card_id": "知识卡片id",
    "question": "题干",
    "options": ["选项A", "选项B", "选项C", "选项D"],
    "correct_index": 0,
    "explanation": "解析"
  }}
]

**知识卡片：**
{cards_context}
"""


def _parse_quiz_json(content: str) -> list[dict]:
    text = content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
    start = text.find("[")
    end = text.rfind("]") + 1
    if start < 0 or end <= start:
        raise RagflowError("AI 未返回有效的题目 JSON 数组")
    items = json.loads(text[start:end])
    if not isinstance(items, list):
        raise RagflowError("AI 返回的题目格式错误")
    return items


def _resolve_card_id(raw_id: str | None, concept: str | None, cards: list[KnowledgeCard]) -> str:
    card_map = {c.id: c for c in cards}
    if raw_id and raw_id in card_map:
        return raw_id
    if concept:
        for card in cards:
            if card.concept == concept or concept in card.concept:
                return card.id
    return cards[0].id if cards else ""


def _normalize_question(item: dict, cards: list[KnowledgeCard], subject_id: str) -> QuizQuestionOut | None:
    question = (item.get("question") or "").strip()
    options = item.get("options") or []
    if isinstance(options, str):
        options = [options]
    options = [str(o).strip() for o in options if str(o).strip()]
    if not question or len(options) < 2:
        return None

    while len(options) < 4:
        options.append(f"选项 {len(options) + 1}（占位）")
    options = options[:4]

    correct_index = item.get("correct_index", 0)
    if not isinstance(correct_index, int) or correct_index < 0 or correct_index >= len(options):
        correct_index = 0

    card_id = _resolve_card_id(
        item.get("card_id") or item.get("cardId"),
        item.get("concept"),
        cards,
    )
    explanation = (item.get("explanation") or "").strip() or options[correct_index]

    return QuizQuestionOut(
        id=new_id(),
        card_id=card_id,
        subject_id=subject_id,
        question=question,
        options=options,
        correct_index=correct_index,
        explanation=explanation,
    )


def _local_generate_quiz(
    cards: list[KnowledgeCard],
    subject_id: str,
    count: int,
) -> list[QuizQuestionOut]:
    """Fallback when RAGFlow is not configured."""
    selected = random.sample(cards, k=min(count, len(cards)))
    questions: list[QuizQuestionOut] = []

    for card in selected:
        others = [c for c in cards if c.id != card.id]
        correct = (card.detail or card.summary).split("。")[0].strip()
        if correct and not correct.endswith("。"):
            correct += "。"

        distractors: list[str] = []
        for other in random.sample(others, k=min(3, len(others))):
            snippet = (other.detail or other.summary).split("。")[0].strip()
            if snippet:
                distractors.append(f"「{other.concept}」是指{snippet}。")

        templates = [
            f"关于「{other.concept}」的说法与「{card.concept}」相同",
            f"「{card.concept}」与「{other.concept}」完全无关",
            "该概念仅适用于日常生活，与学科理论无关",
        ]
        for t in templates:
            if len(distractors) >= 3:
                break
            if t not in distractors:
                distractors.append(t)

        while len(distractors) < 3:
            distractors.append(f"「{card.concept}」的定义与上述知识卡片中的描述完全相反")

        options = [correct, *distractors[:3]]
        random.shuffle(options)

        questions.append(
            QuizQuestionOut(
                id=new_id(),
                card_id=card.id,
                subject_id=subject_id,
                question=f"以下关于「{card.concept}」的表述，哪一项最准确？",
                options=options,
                correct_index=options.index(correct),
                explanation=card.detail or card.summary,
            )
        )

    return questions


async def generate_quiz(
    db: Session,
    subject_id: str,
    count: int,
    on_progress: ProgressCallback | None = None,
) -> list[QuizQuestionOut]:
    _report(on_progress, 5, "读取知识卡片…")
    subject = db.get(Subject, subject_id)
    cards = (
        db.query(KnowledgeCard)
        .filter(KnowledgeCard.subject_id == subject_id)
        .order_by(KnowledgeCard.created_at.desc())
        .all()
    )
    if not cards:
        return []

    subject_name = subject.name if subject else "当前科目"
    count = max(1, min(50, count))

    settings = get_settings()
    if not settings.ragflow_enabled:
        _report(on_progress, 40, "本地模式生成题目…")
        questions = _local_generate_quiz(cards, subject_id, count)
        _report(on_progress, 95, f"已生成 {len(questions)} 道题")
        return questions

    _report(on_progress, 15, "构建出题上下文…")
    context_cards = cards[:30]
    cards_context = _build_cards_context(context_cards)
    prompt = _build_quiz_prompt(subject_name, cards_context, count)

    _report(on_progress, 35, "AI 正在生成题目…")
    try:
        client = RagflowClient()
        content = await client.chat_messages(
            [
                {
                    "role": "system",
                    "content": "你是专业的课程测验出题助手，擅长根据知识要点设计高质量选择题。",
                },
                {"role": "user", "content": prompt},
            ]
        )
    except RagflowError:
        raise
    except Exception as exc:
        raise RagflowError(f"AI 出题失败: {exc}") from exc

    _report(on_progress, 75, "解析题目…")
    raw_items = _parse_quiz_json(content)

    questions: list[QuizQuestionOut] = []
    for item in raw_items[:count]:
        q = _normalize_question(item, context_cards, subject_id)
        if q:
            questions.append(q)

    if not questions:
        raise RagflowError("AI 未能生成有效题目，请稍后重试")

    _report(on_progress, 95, f"已生成 {len(questions)} 道题")
    return questions
