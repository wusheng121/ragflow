from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), default="")
    level: Mapped[str] = mapped_column(String(32), default="beginner")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class StudySubject(Base):
    __tablename__ = "study_subjects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(String(300), default="")
    user_id: Mapped[int] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    materials: Mapped[list["CourseMaterial"]] = relationship(back_populates="subject")


class CourseMaterial(Base):
    __tablename__ = "course_materials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    source_name: Mapped[str] = mapped_column(String(200), default="manual")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("user_profiles.id"), nullable=True)
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("study_subjects.id"), nullable=True, index=True)
    rag_dataset_id: Mapped[str] = mapped_column(String(100), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    flashcards: Mapped[list["Flashcard"]] = relationship(back_populates="material")
    attempts: Mapped[list["PracticeAttempt"]] = relationship(back_populates="material")
    mistakes: Mapped[list["MistakeNote"]] = relationship(back_populates="material")
    subject: Mapped[StudySubject | None] = relationship(back_populates="materials")


class Flashcard(Base):
    __tablename__ = "flashcards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("course_materials.id"), index=True)
    term: Mapped[str] = mapped_column(String(128), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    material: Mapped[CourseMaterial] = relationship(back_populates="flashcards")
    user_id: Mapped[int | None] = mapped_column(ForeignKey("user_profiles.id"), nullable=True)

    @property
    def material_title(self) -> str:
        return self.material.title if self.material else ""


class PracticeAttempt(Base):
    __tablename__ = "practice_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("course_materials.id"), index=True)
    concept: Mapped[str] = mapped_column(String(128), default="")
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[int] = mapped_column(Integer, default=0)
    feedback: Mapped[str] = mapped_column(Text, default="")
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    material: Mapped[CourseMaterial] = relationship(back_populates="attempts")
    user_id: Mapped[int | None] = mapped_column(ForeignKey("user_profiles.id"), nullable=True)

    @property
    def material_title(self) -> str:
        return self.material.title if self.material else ""


class MistakeNote(Base):
    __tablename__ = "mistake_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("course_materials.id"), index=True)
    concept: Mapped[str] = mapped_column(String(128), nullable=False)
    last_question: Mapped[str] = mapped_column(Text, default="")
    user_answer: Mapped[str] = mapped_column(Text, default="")
    assistant_correction: Mapped[str] = mapped_column(Text, default="")
    user_id: Mapped[int | None] = mapped_column(ForeignKey("user_profiles.id"), nullable=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    user_note: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="open")
    review_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    material: Mapped[CourseMaterial] = relationship(back_populates="mistakes")

    @property
    def material_title(self) -> str:
        return self.material.title if self.material else ""

