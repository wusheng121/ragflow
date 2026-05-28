from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker
from sqlalchemy.types import JSON

from app.config import get_settings


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    subjects: Mapped[list["Subject"]] = relationship(back_populates="owner", cascade="all, delete-orphan")


class Subject(Base):
    __tablename__ = "subjects"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    ragflow_dataset_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    owner: Mapped["User | None"] = relationship(back_populates="subjects")
    materials: Mapped[list["Material"]] = relationship(back_populates="subject", cascade="all, delete-orphan")
    knowledge_cards: Mapped[list["KnowledgeCard"]] = relationship(back_populates="subject", cascade="all, delete-orphan")


class Material(Base):
    __tablename__ = "materials"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    subject_id: Mapped[str] = mapped_column(String(64), ForeignKey("subjects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    file_path: Mapped[str | None] = mapped_column(String(1024))
    ragflow_document_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    size: Mapped[int] = mapped_column(BigInteger, default=0)
    status: Mapped[str] = mapped_column(String(32), default="uploaded")
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    subject: Mapped["Subject"] = relationship(back_populates="materials")


class KnowledgeCard(Base):
    __tablename__ = "knowledge_cards"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    subject_id: Mapped[str] = mapped_column(String(64), ForeignKey("subjects.id", ondelete="CASCADE"), index=True)
    concept: Mapped[str] = mapped_column(String(512), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    detail: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[list | None] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    subject: Mapped["Subject"] = relationship(back_populates="knowledge_cards")


class PracticeSession(Base):
    __tablename__ = "practice_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    subject_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("subjects.id", ondelete="CASCADE"), index=True
    )
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    total: Mapped[int] = mapped_column(Integer, nullable=False)
    duration: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class WrongAnswer(Base):
    __tablename__ = "wrong_answers"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    subject_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("subjects.id", ondelete="CASCADE"), index=True
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    user_answer: Mapped[str] = mapped_column(Text, default="")
    correct_answer: Mapped[str] = mapped_column(Text, default="")
    concept_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True, pool_recycle=3600)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _upgrade_schema()


def _upgrade_schema() -> None:
    """Add new columns to existing tables (safe for dev upgrades)."""
    alters = [
        "ALTER TABLE subjects ADD COLUMN ragflow_dataset_id VARCHAR(64) NULL",
        "ALTER TABLE materials ADD COLUMN ragflow_document_id VARCHAR(64) NULL",
        "ALTER TABLE subjects ADD COLUMN user_id VARCHAR(64) NULL",
    ]
    with engine.connect() as conn:
        for stmt in alters:
            try:
                conn.execute(text(stmt))
                conn.commit()
            except Exception:
                conn.rollback()
