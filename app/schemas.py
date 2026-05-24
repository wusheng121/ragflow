from datetime import datetime
from typing import Literal

from pydantic import ConfigDict
from pydantic import BaseModel, Field, field_validator, model_validator


class MaterialCreate(BaseModel):
    title: str
    content: str
    source_name: str = "manual"
    subject_id: int | None = None


class MaterialRead(BaseModel):
    id: int
    title: str
    source_name: str
    created_at: datetime
    user_id: int | None = None
    subject_id: int | None = None

    model_config = ConfigDict(from_attributes=True)


class FlashcardGenerateRequest(BaseModel):
    material_id: int | None = None
    subject_id: int | None = None
    count: int = Field(default=8, ge=1, le=30)
    user_level: Literal["beginner", "intermediate", "advanced"] = "beginner"

    @model_validator(mode="after")
    def validate_scope(self) -> "FlashcardGenerateRequest":
        if not self.material_id and not self.subject_id:
            raise ValueError("material_id 和 subject_id 至少需要一个")
        return self


class FlashcardItem(BaseModel):
    concept: str
    explanation: str
    example: str = ""


class MaterialDetail(BaseModel):
    id: int
    title: str
    source_name: str
    content: str
    user_id: int | None = None
    subject_id: int | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PracticeQuestionRequest(BaseModel):
    material_id: int | None = None
    subject_id: int | None = None
    concept: str = ""
    user_level: Literal["beginner", "intermediate", "advanced"] = "beginner"

    @model_validator(mode="after")
    def validate_scope(self) -> "PracticeQuestionRequest":
        if not self.material_id and not self.subject_id:
            raise ValueError("material_id 和 subject_id 至少需要一个")
        return self


class PracticeQuestionResponse(BaseModel):
    concept: str
    question: str
    references: list[str]
    basis_points: list[str] = []


class PracticeAnswerRequest(BaseModel):
    material_id: int | None = None
    subject_id: int | None = None
    concept: str
    question: str
    answer: str
    user_level: Literal["beginner", "intermediate", "advanced"] = "beginner"

    @model_validator(mode="after")
    def validate_scope(self) -> "PracticeAnswerRequest":
        if not self.material_id and not self.subject_id:
            raise ValueError("material_id 和 subject_id 至少需要一个")
        return self


class PracticeAnswerResponse(BaseModel):
    score: int
    is_correct: bool
    feedback: str
    correction: str
    references: list[str]
    basis_points: list[str] = []


class MistakeRead(BaseModel):
    id: int
    material_id: int
    material_title: str = ""
    concept: str
    assistant_correction: str = ""
    reason: str
    user_note: str
    status: str
    review_count: int
    user_id: int | None = None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AttemptRead(BaseModel):
    id: int
    material_id: int
    material_title: str = ""
    concept: str
    question: str
    answer: str
    score: int
    feedback: str
    is_correct: bool
    user_id: int | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserRegisterRequest(BaseModel):
    name: str = Field(min_length=3, max_length=20, pattern=r"^[A-Za-z0-9_]{3,20}$")
    password: str = Field(min_length=8, max_length=32)
    email: str | None = Field(default=None, max_length=200)
    level: Literal["beginner", "intermediate", "advanced"] = "beginner"

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not any(ch.isalpha() for ch in value) or not any(ch.isdigit() for ch in value):
            raise ValueError("密码需至少包含一个字母和一个数字")
        return value


class UserLoginRequest(BaseModel):
    name: str = Field(min_length=3, max_length=20)
    password: str = Field(min_length=8, max_length=32)


class UserRead(BaseModel):
    id: int
    name: str
    email: str | None = None
    level: str
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead


class MistakeUpdateRequest(BaseModel):
    reason: str | None = None
    user_note: str | None = None
    status: Literal["open", "reviewing", "mastered"] | None = None


class ConsistencyRequest(BaseModel):
    answer: str
    references: list[str]


class ConsistencyResponse(BaseModel):
    consistency_score: int
    explanation: str


class SubjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=300)


class SubjectRead(BaseModel):
    id: int
    name: str
    description: str
    user_id: int
    created_at: datetime
    materials_count: int = 0

    model_config = ConfigDict(from_attributes=True)


