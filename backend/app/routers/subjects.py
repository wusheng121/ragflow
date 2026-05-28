from datetime import datetime
import asyncio
import json

from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import KnowledgeCard, Material, Subject, User
from app.deps import get_current_user, get_db
from app.schemas import ExtractRequest, KnowledgeCardOut, MaterialOut, SubjectCreate, SubjectOut
from app.config import get_settings
from app.services.extract import RagflowError, extract_concepts_from_subject
from app.utils.id_gen import new_id
from app.utils.ownership import get_owned_subject

router = APIRouter(prefix="/subjects", tags=["subjects"])


def _save_knowledge_cards(db: Session, subject_id: str, concepts: list[dict]) -> list[KnowledgeCardOut]:
    now = datetime.utcnow()
    results: list[KnowledgeCardOut] = []
    for item in concepts:
        card = KnowledgeCard(
            id=new_id(),
            subject_id=subject_id,
            concept=item["concept"],
            summary=item["summary"],
            detail=item.get("detail", ""),
            tags=item.get("tags", []),
            created_at=now,
        )
        db.add(card)
        results.append(
            KnowledgeCardOut(
                id=card.id,
                subject_id=card.subject_id,
                concept=card.concept,
                summary=card.summary,
                detail=card.detail,
                tags=card.tags or [],
                created_at=card.created_at,
            )
        )
    db.commit()
    return results


def _subject_out(db: Session, subject: Subject) -> SubjectOut:
    material_count = db.query(func.count(Material.id)).filter(Material.subject_id == subject.id).scalar() or 0
    card_count = (
        db.query(func.count(KnowledgeCard.id)).filter(KnowledgeCard.subject_id == subject.id).scalar() or 0
    )
    return SubjectOut(
        id=subject.id,
        name=subject.name,
        description=subject.description or "",
        created_at=subject.created_at,
        material_count=material_count,
        card_count=card_count,
    )


@router.get("", response_model=list[SubjectOut])
def list_subjects(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    subjects = (
        db.query(Subject)
        .filter(Subject.user_id == user.id)
        .order_by(Subject.created_at.desc())
        .all()
    )
    return [_subject_out(db, s) for s in subjects]


@router.post("", response_model=SubjectOut, status_code=201)
def create_subject(
    body: SubjectCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    subject = Subject(
        id=new_id(),
        user_id=user.id,
        name=body.name.strip(),
        description=body.description.strip(),
        created_at=datetime.utcnow(),
    )
    db.add(subject)
    db.commit()
    db.refresh(subject)
    return _subject_out(db, subject)


@router.delete("/{subject_id}", status_code=204)
def delete_subject(
    subject_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    subject = get_owned_subject(db, subject_id, user)
    db.delete(subject)
    db.commit()
    return None


@router.get("/{subject_id}/materials", response_model=list[MaterialOut])
def list_materials(
    subject_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_owned_subject(db, subject_id, user)
    materials = (
        db.query(Material)
        .filter(Material.subject_id == subject_id)
        .order_by(Material.uploaded_at.desc())
        .all()
    )
    return [
        MaterialOut(
            id=m.id,
            subject_id=m.subject_id,
            name=m.name,
            size=m.size,
            status=m.status,
            uploaded_at=m.uploaded_at,
        )
        for m in materials
    ]


@router.post("/{subject_id}/materials", response_model=list[MaterialOut])
async def upload_materials(
    subject_id: str,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    subject = get_owned_subject(db, subject_id, user)
    if not files:
        raise HTTPException(status_code=400, detail="请上传至少一个文件")

    settings = get_settings()
    subject_dir = settings.upload_path / user.id / subject.id
    subject_dir.mkdir(parents=True, exist_ok=True)

    created: list[MaterialOut] = []
    for upload in files:
        safe_name = upload.filename or "unnamed"
        dest = subject_dir / f"{new_id()}_{safe_name}"
        content = await upload.read()
        dest.write_bytes(content)

        material = Material(
            id=new_id(),
            subject_id=subject_id,
            name=safe_name,
            file_path=str(dest),
            size=len(content),
            status="uploaded",
            uploaded_at=datetime.utcnow(),
        )
        db.add(material)
        created.append(
            MaterialOut(
                id=material.id,
                subject_id=material.subject_id,
                name=material.name,
                size=material.size,
                status=material.status,
                uploaded_at=material.uploaded_at,
            )
        )
    db.commit()
    return created


@router.delete("/{subject_id}/materials/{material_id}", status_code=204)
def delete_material(
    subject_id: str,
    material_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_owned_subject(db, subject_id, user)
    material = db.get(Material, material_id)
    if not material or material.subject_id != subject_id:
        raise HTTPException(status_code=404, detail="资料不存在")
    if material.file_path:
        Path(material.file_path).unlink(missing_ok=True)
    db.delete(material)
    db.commit()
    return None


@router.post("/{subject_id}/extract", response_model=list[KnowledgeCardOut])
async def extract_subject_concepts(
    subject_id: str,
    body: ExtractRequest | None = None,
    count: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    card_count = body.count if body else count
    subject = get_owned_subject(db, subject_id, user)

    materials = db.query(Material).filter(Material.subject_id == subject_id).all()
    if not materials:
        raise HTTPException(status_code=400, detail="请先上传资料")

    try:
        concepts = await extract_concepts_from_subject(
            db, subject, materials, count=card_count
        )
    except RagflowError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if not concepts:
        raise HTTPException(status_code=422, detail="未能从资料中抽取到重要概念，请检查文件内容")
    return _save_knowledge_cards(db, subject_id, concepts)


@router.post("/{subject_id}/extract/stream")
async def extract_subject_concepts_stream(
    subject_id: str,
    count: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    subject = get_owned_subject(db, subject_id, user)
    card_count = count

    materials = db.query(Material).filter(Material.subject_id == subject_id).all()
    if not materials:
        raise HTTPException(status_code=400, detail="请先上传资料")

    queue: asyncio.Queue[dict] = asyncio.Queue()

    def on_progress(percent: int, message: str) -> None:
        queue.put_nowait({"type": "progress", "progress": percent, "message": message})

    async def worker() -> None:
        try:
            concepts = await extract_concepts_from_subject(
                db, subject, materials, on_progress=on_progress, count=card_count
            )
            if not concepts:
                await queue.put({"type": "error", "message": "未能从资料中抽取到专业术语，请检查文件内容"})
                return
            on_progress(92, "保存知识卡片…")
            cards = _save_knowledge_cards(db, subject_id, concepts)
            await queue.put(
                {
                    "type": "done",
                    "progress": 100,
                    "message": f"完成，共抽取 {len(cards)} 个术语",
                    "cards": [c.model_dump(mode="json", by_alias=True) for c in cards],
                }
            )
        except RagflowError as exc:
            await queue.put({"type": "error", "message": str(exc)})
        except Exception as exc:
            await queue.put({"type": "error", "message": f"抽取失败: {exc}"})

    async def event_stream():
        task = asyncio.create_task(worker())
        try:
            while True:
                item = await queue.get()
                yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
                if item.get("type") in ("done", "error"):
                    break
        finally:
            await task

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
