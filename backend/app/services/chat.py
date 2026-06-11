import asyncio
from collections.abc import AsyncIterator

from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import KnowledgeCard, Material, Subject
from app.services.chat_history import MAX_TURNS_PER_CONVERSATION, trim_history
from app.services.ragflow import RagflowClient, RagflowError


async def _build_subject_context(db: Session, subject_id: str) -> tuple[str, str]:
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

    lines = [
        f"当前科目：{subject.name}",
        "请仅依据本科目下方知识背景回答，不要混用其他科目内容。",
        "",
    ]

    if cards:
        lines.append("以下是从该科目资料中抽取的重要概念：")
        lines.append("")
        for i, card in enumerate(cards, 1):
            lines.append(f"{i}. 【{card.concept}】")
            lines.append(f"   简介：{card.summary}")
            if card.detail:
                lines.append(f"   详情：{card.detail[:500]}")
            lines.append("")
    else:
        lines.append(f"当前科目「{subject.name}」暂无知识卡片。")

    settings = get_settings()
    if settings.ragflow_enabled and subject.ragflow_dataset_id:
        materials = (
            db.query(Material)
            .filter(Material.subject_id == subject_id)
            .filter(Material.ragflow_document_id.isnot(None))
            .all()
        )
        doc_ids = [m.ragflow_document_id for m in materials if m.ragflow_document_id]
        if doc_ids:
            try:
                client = RagflowClient()
                source_names = {
                    m.ragflow_document_id: m.name for m in materials if m.ragflow_document_id
                }
                corpus = await client.collect_corpus(
                    subject.ragflow_dataset_id, doc_ids, source_names
                )
                if corpus.strip():
                    lines.append("--- 该科目 RAGFlow 知识库原文摘录 ---")
                    lines.append("")
                    lines.append(corpus[:10000])
            except RagflowError:
                pass

    if not cards and len(lines) <= 4:
        lines.append("请基于通用知识回答，并说明该科目暂无结构化知识卡片。")

    return subject.name, "\n".join(lines)


async def _build_chat_messages(
    db: Session,
    message: str,
    history: list[dict],
    subject_id: str | None = None,
) -> list[dict]:
    messages: list[dict] = []

    system_parts = [
        "你是 RAGFlow 复习助手，专门帮助用户理解和复习课程知识。",
        "回答要求：准确、清晰、结构化；遇到公式用 plain text 或 LaTeX 保留原格式；",
        "若用户选择了科目，必须只使用该科目的知识背景；不确定时请如实说明。",
    ]

    if subject_id:
        subject_name, context = await _build_subject_context(db, subject_id)
        if subject_name:
            system_parts.append(f"\n--- 知识背景（{subject_name}）---\n{context}")
    else:
        system_parts.append("\n当前为通用对话模式，未绑定具体科目知识库。")

    messages.append({"role": "system", "content": "\n".join(system_parts)})

    effective_history = trim_history(history, max_turns=MAX_TURNS_PER_CONVERSATION)

    for item in effective_history:
        role = item.get("role", "user")
        content = (item.get("content") or "").strip()
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": message.strip()})
    return messages


def _local_fallback_reply(db: Session, message: str, subject_id: str | None) -> str:
    if subject_id:
        subject = db.get(Subject, subject_id)
        cards = (
            db.query(KnowledgeCard)
            .filter(KnowledgeCard.subject_id == subject_id)
            .limit(5)
            .all()
        )
        if cards:
            snippets = "\n".join(f"- {c.concept}：{c.summary}" for c in cards)
            return (
                f"（本地模式·{subject.name if subject else '当前科目'}）关于「{message}」：\n\n"
                f"相关概念：\n{snippets}\n\n"
                "请配置 RAGFLOW_API_URL 和 RAGFLOW_API_KEY 以启用完整 AI 对话。"
            )
        return (
            f"（本地模式）科目「{subject.name if subject else subject_id}」暂无知识卡片。\n\n"
            "请配置 RAGFLOW_API_URL 和 RAGFLOW_API_KEY 以启用 AI 模型对话。"
        )
    return (
        f"（本地模式）收到你的问题：{message}\n\n"
        "请配置 RAGFLOW_API_URL 和 RAGFLOW_API_KEY 以启用 AI 模型对话。"
    )


async def _simulate_stream(text: str) -> AsyncIterator[str]:
    step = max(1, len(text) // 40)
    for i in range(step, len(text) + step, step):
        yield text[: min(i, len(text))]
        await asyncio.sleep(0.02)
    yield text


async def chat_with_model(
    db: Session,
    message: str,
    history: list[dict],
    subject_id: str | None = None,
) -> str:
    settings = get_settings()
    messages = await _build_chat_messages(db, message, history, subject_id)

    if settings.ragflow_enabled:
        try:
            client = RagflowClient()
            return await client.chat_messages(messages)
        except RagflowError:
            raise
        except Exception as exc:
            raise RagflowError(f"模型对话失败: {exc}") from exc

    return _local_fallback_reply(db, message, subject_id)


async def chat_with_model_stream(
    db: Session,
    message: str,
    history: list[dict],
    subject_id: str | None = None,
) -> AsyncIterator[str]:
    settings = get_settings()
    messages = await _build_chat_messages(db, message, history, subject_id)

    if settings.ragflow_enabled:
        try:
            client = RagflowClient()
            async for chunk in client.chat_messages_stream(messages):
                yield chunk
            return
        except RagflowError:
            raise
        except Exception as exc:
            raise RagflowError(f"模型对话失败: {exc}") from exc

    reply = _local_fallback_reply(db, message, subject_id)
    async for chunk in _simulate_stream(reply):
        yield chunk
