from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import KnowledgeCard, Subject
from app.services.ragflow import RagflowClient, RagflowError


def _build_subject_context(db: Session, subject_id: str) -> tuple[str, str]:
    subject = db.get(Subject, subject_id)
    if not subject:
        return "", ""

    cards = (
        db.query(KnowledgeCard)
        .filter(KnowledgeCard.subject_id == subject_id)
        .order_by(KnowledgeCard.created_at.desc())
        .limit(30)
        .all()
    )
    if not cards:
        return subject.name, f"当前科目「{subject.name}」暂无知识卡片，请基于通用知识回答。"

    lines = [f"科目：{subject.name}", "以下是从用户上传资料中抽取的重要概念：", ""]
    for i, card in enumerate(cards, 1):
        lines.append(f"{i}. 【{card.concept}】")
        lines.append(f"   简介：{card.summary}")
        if card.detail:
            lines.append(f"   详情：{card.detail[:500]}")
        lines.append("")
    return subject.name, "\n".join(lines)


async def chat_with_model(
    db: Session,
    message: str,
    history: list[dict],
    subject_id: str | None = None,
) -> str:
    settings = get_settings()
    messages: list[dict] = []

    system_parts = [
        "你是 RAGFlow 复习助手，专门帮助用户理解和复习课程知识。",
        "回答要求：准确、清晰、结构化；遇到公式用 plain text 或 LaTeX 保留原格式；",
        "若用户问题与所选科目相关，优先依据下方知识背景作答；不确定时请如实说明。",
    ]

    if subject_id:
        subject_name, context = _build_subject_context(db, subject_id)
        if subject_name:
            system_parts.append(f"\n--- 知识背景（{subject_name}）---\n{context}")

    messages.append({"role": "system", "content": "\n".join(system_parts)})

    for item in history[-12:]:
        role = item.get("role", "user")
        content = (item.get("content") or "").strip()
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": message.strip()})

    if settings.ragflow_enabled:
        try:
            client = RagflowClient()
            return await client.chat_messages(messages)
        except RagflowError:
            raise
        except Exception as exc:
            raise RagflowError(f"模型对话失败: {exc}") from exc

    # Local fallback when RAGFlow not configured
    if subject_id:
        _, context = _build_subject_context(db, subject_id)
        return (
            f"（本地模式）关于你的问题「{message}」，我找到了以下相关背景供参考：\n\n"
            f"{context[:800]}\n\n"
            "请配置 RAGFLOW_API_URL 和 RAGFLOW_API_KEY 以启用完整 AI 对话。"
        )
    return (
        f"（本地模式）收到你的问题：{message}\n\n"
        "请配置 RAGFLOW_API_URL 和 RAGFLOW_API_KEY 以启用 AI 模型对话。"
    )
