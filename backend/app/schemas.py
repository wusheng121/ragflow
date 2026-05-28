from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.utils.camel import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=to_camel,
        serialize_by_alias=True,
    )


class SubjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = ""


class SubjectOut(CamelModel):
    id: str
    name: str
    description: str
    created_at: datetime
    material_count: int = 0
    card_count: int = 0


class MaterialOut(CamelModel):
    id: str
    subject_id: str
    name: str
    size: int
    status: str
    uploaded_at: datetime


class ExtractRequest(BaseModel):
    count: int = Field(default=10, ge=1, le=50)


class KnowledgeCardOut(CamelModel):
    id: str
    subject_id: str
    concept: str
    summary: str
    detail: str
    tags: list[str] = []
    created_at: datetime


class QuizGenerateRequest(BaseModel):
    subject_id: str
    count: int = Field(default=5, ge=1, le=50)


class QuizQuestionOut(CamelModel):
    id: str
    card_id: str
    subject_id: str
    question: str
    options: list[str]
    correct_index: int
    explanation: str


class PracticeAnswerIn(CamelModel):
    card_id: str | None = None
    question: str
    user_answer: str
    correct_answer: str
    is_correct: bool


class PracticeSubmitRequest(BaseModel):
    subject_id: str
    answers: list[PracticeAnswerIn]
    duration: int = 0


class PracticeSessionOut(CamelModel):
    id: str
    subject_id: str
    score: int
    total: int
    duration: int
    created_at: datetime


class PracticeSubmitOut(CamelModel):
    session: PracticeSessionOut
    wrong_count: int


class WrongAnswerOut(CamelModel):
    id: str
    subject_id: str
    question: str
    user_answer: str
    correct_answer: str
    concept_id: str | None = None
    created_at: datetime


class StatsOut(CamelModel):
    subject_count: int
    card_count: int
    wrong_count: int
    session_count: int


class UserRegister(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=6, max_length=128)


class UserLogin(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)


class UserOut(CamelModel):
    id: str
    username: str
    email: str | None = None
    created_at: datetime


class AuthTokenOut(CamelModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
