import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import Field
from sqlalchemy.orm import Session

from app.database import User
from app.deps import get_current_user, get_db
from app.schemas import CamelModel
from app.services.chat import chat_with_model, chat_with_model_stream
from app.services.chat_history import (
    MAX_CONVERSATIONS_LIST,
    MAX_TURNS_PER_CONVERSATION,
    append_chat_turn,
    conversation_to_summary,
    get_conversation_messages,
    get_owned_conversation,
    list_conversations,
)
from app.services.ragflow import RagflowError
from app.utils.ownership import get_owned_subject

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatMessageIn(CamelModel):
    role: str
    content: str


class ChatRequest(CamelModel):
    message: str = Field(min_length=1, max_length=4000)
    subject_id: str | None = None
    conversation_id: str | None = None
    history: list[ChatMessageIn] = []


class ChatResponse(CamelModel):
    reply: str
    conversation_id: str
    history: list[ChatMessageIn]
    title: str


class ConversationSummaryOut(CamelModel):
    id: str
    subject_id: str | None = None
    title: str
    turn_count: int
    updated_at: datetime
    created_at: datetime


class ConversationListResponse(CamelModel):
    conversations: list[ConversationSummaryOut]
    max_list: int = MAX_CONVERSATIONS_LIST
    max_turns_per_conversation: int = MAX_TURNS_PER_CONVERSATION


class ConversationDetailResponse(CamelModel):
    id: str
    subject_id: str | None = None
    title: str
    history: list[ChatMessageIn]
    max_turns: int = MAX_TURNS_PER_CONVERSATION


def _verify_subject(db: Session, user: User, subject_id: str | None) -> None:
    if subject_id:
        get_owned_subject(db, subject_id, user)


def _messages_out(messages: list[dict]) -> list[ChatMessageIn]:
    return [ChatMessageIn(role=m["role"], content=m["content"]) for m in messages]


@router.get("/conversations", response_model=ConversationListResponse)
def read_conversations(
    subject_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _verify_subject(db, user, subject_id)
    rows = list_conversations(db, user.id, subject_id)
    return ConversationListResponse(
        conversations=[ConversationSummaryOut(**conversation_to_summary(r)) for r in rows]
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationDetailResponse)
def read_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = get_owned_conversation(db, user.id, conversation_id)
    messages = get_conversation_messages(db, user.id, conversation_id)
    return ConversationDetailResponse(
        id=row.id,
        subject_id=row.subject_id,
        title=row.title,
        history=_messages_out(messages),
    )


@router.post("", response_model=ChatResponse)
async def send_chat_message(
    body: ChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _verify_subject(db, user, body.subject_id)
    history = (
        get_conversation_messages(db, user.id, body.conversation_id)
        if body.conversation_id
        else []
    )

    try:
        reply = await chat_with_model(
            db,
            message=body.message,
            history=history,
            subject_id=body.subject_id,
        )
    except RagflowError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        row, saved = append_chat_turn(
            db,
            user.id,
            body.subject_id,
            body.conversation_id,
            body.message,
            reply,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ChatResponse(
        reply=reply,
        conversation_id=row.id,
        history=_messages_out(saved),
        title=row.title,
    )


@router.post("/stream")
async def send_chat_message_stream(
    body: ChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _verify_subject(db, user, body.subject_id)
    history = (
        get_conversation_messages(db, user.id, body.conversation_id)
        if body.conversation_id
        else []
    )

    async def event_stream():
        full = ""
        try:
            async for chunk in chat_with_model_stream(
                db,
                message=body.message,
                history=history,
                subject_id=body.subject_id,
            ):
                full = chunk
                yield f"data: {json.dumps({'type': 'delta', 'content': full}, ensure_ascii=False)}\n\n"
            row, saved = append_chat_turn(
                db,
                user.id,
                body.subject_id,
                body.conversation_id,
                body.message,
                full,
            )
            summaries = [
                ConversationSummaryOut(**conversation_to_summary(r)).model_dump(
                    mode="json", by_alias=True
                )
                for r in list_conversations(db, user.id, body.subject_id)
            ]
            yield f"data: {json.dumps({
                'type': 'done',
                'reply': full,
                'history': saved,
                'conversationId': row.id,
                'title': row.title,
                'conversations': summaries,
            }, ensure_ascii=False, default=str)}\n\n"
        except RagflowError as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)}, ensure_ascii=False)}\n\n"
        except ValueError as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)}, ensure_ascii=False)}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': f'对话失败: {exc}'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
