from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field
from sqlalchemy.orm import Session

from app.database import User
from app.deps import get_current_user, get_db
from app.schemas import CamelModel
from app.services.chat import chat_with_model
from app.services.ragflow import RagflowError
from app.utils.ownership import get_owned_subject

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatMessageIn(CamelModel):
    role: str
    content: str


class ChatRequest(CamelModel):
    message: str = Field(min_length=1, max_length=4000)
    subject_id: str | None = None
    history: list[ChatMessageIn] = []


class ChatResponse(CamelModel):
    reply: str


@router.post("", response_model=ChatResponse)
async def send_chat_message(
    body: ChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if body.subject_id:
        get_owned_subject(db, body.subject_id, user)

    try:
        reply = await chat_with_model(
            db,
            message=body.message,
            history=[h.model_dump() for h in body.history],
            subject_id=body.subject_id,
        )
    except RagflowError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return ChatResponse(reply=reply)
