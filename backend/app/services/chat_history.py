from datetime import datetime

from sqlalchemy.orm import Session

from app.database import ChatConversation
from app.utils.id_gen import new_id

MAX_CONVERSATIONS_LIST = 10
MAX_TURNS_PER_CONVERSATION = 50


def subject_filter_value(subject_id: str | None) -> str | None:
    return subject_id if subject_id else None


def trim_history(messages: list[dict], max_turns: int = MAX_TURNS_PER_CONVERSATION) -> list[dict]:
    cleaned: list[dict] = []
    for item in messages:
        role = item.get("role")
        content = (item.get("content") or "").strip()
        if role in {"user", "assistant"} and content:
            cleaned.append({"role": role, "content": content})
    max_messages = max_turns * 2
    if len(cleaned) <= max_messages:
        return cleaned
    return cleaned[-max_messages:]


def count_turns(messages: list[dict]) -> int:
    return sum(1 for m in messages if m.get("role") == "user" and (m.get("content") or "").strip())


def make_title(first_user_message: str) -> str:
    text = first_user_message.strip().replace("\n", " ")
    if len(text) <= 48:
        return text or "新对话"
    return text[:48] + "…"


def _conversation_query(db: Session, user_id: str, subject_id: str | None):
    q = db.query(ChatConversation).filter(ChatConversation.user_id == user_id)
    if subject_id:
        return q.filter(ChatConversation.subject_id == subject_id)
    return q.filter(ChatConversation.subject_id.is_(None))


def prune_old_conversations(db: Session, user_id: str, subject_id: str | None) -> None:
    rows = (
        _conversation_query(db, user_id, subject_id)
        .order_by(ChatConversation.updated_at.desc())
        .all()
    )
    for row in rows[MAX_CONVERSATIONS_LIST:]:
        db.delete(row)
    db.commit()


def list_conversations(db: Session, user_id: str, subject_id: str | None) -> list[ChatConversation]:
    return (
        _conversation_query(db, user_id, subject_id)
        .order_by(ChatConversation.updated_at.desc())
        .limit(MAX_CONVERSATIONS_LIST)
        .all()
    )


def get_owned_conversation(db: Session, user_id: str, conversation_id: str) -> ChatConversation:
    row = (
        db.query(ChatConversation)
        .filter(ChatConversation.id == conversation_id, ChatConversation.user_id == user_id)
        .first()
    )
    if not row:
        raise ValueError("对话不存在或无权访问")
    return row


def get_conversation_messages(db: Session, user_id: str, conversation_id: str) -> list[dict]:
    row = get_owned_conversation(db, user_id, conversation_id)
    return trim_history(list(row.messages or []))


def create_conversation(
    db: Session,
    user_id: str,
    subject_id: str | None,
    first_user_message: str,
) -> ChatConversation:
    now = datetime.utcnow()
    row = ChatConversation(
        id=new_id(),
        user_id=user_id,
        subject_id=subject_filter_value(subject_id),
        title=make_title(first_user_message),
        messages=[],
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    prune_old_conversations(db, user_id, subject_id)
    return row


def append_chat_turn(
    db: Session,
    user_id: str,
    subject_id: str | None,
    conversation_id: str | None,
    user_message: str,
    assistant_message: str,
) -> tuple[ChatConversation, list[dict]]:
    if conversation_id:
        row = get_owned_conversation(db, user_id, conversation_id)
        if subject_filter_value(subject_id) != row.subject_id:
            raise ValueError("对话与当前科目不匹配")
    else:
        row = create_conversation(db, user_id, subject_id, user_message)

    messages = list(row.messages or [])
    messages.append({"role": "user", "content": user_message.strip()})
    messages.append({"role": "assistant", "content": assistant_message.strip()})
    row.messages = trim_history(messages)
    row.updated_at = datetime.utcnow()
    if not row.title or row.title == "新对话":
        row.title = make_title(user_message)
    db.commit()
    db.refresh(row)
    prune_old_conversations(db, user_id, subject_id)
    return row, list(row.messages)


def conversation_to_summary(row: ChatConversation) -> dict:
    messages = list(row.messages or [])
    return {
        "id": row.id,
        "subject_id": row.subject_id,
        "title": row.title,
        "turn_count": count_turns(messages),
        "updated_at": row.updated_at,
        "created_at": row.created_at,
    }
