from pathlib import Path
import tempfile
from os import unlink
from typing import Any, cast

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.clients.ragflow_client import RagflowClient
from app.database import get_db
from app.models import CourseMaterial, StudySubject, UserProfile
from app.schemas import MaterialCreate, MaterialDetail, MaterialRead
from app.services.doc_parser import extract_text_from_file
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/materials", tags=["materials"])
ALLOWED_UPLOAD_EXTENSIONS = {".pdf", ".pptx", ".docx", ".txt", ".md"}


@router.post("", response_model=MaterialRead)
def create_material(
    payload: MaterialCreate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user),
) -> CourseMaterial:
    if payload.subject_id is not None:
        subject = (
            db.query(StudySubject)
            .filter(StudySubject.id == payload.subject_id, StudySubject.user_id == current_user.id)
            .first()
        )
        if not subject:
            raise HTTPException(status_code=404, detail="学科不存在")

    material = CourseMaterial(
        title=payload.title,
        content=payload.content,
        source_name=payload.source_name,
        user_id=current_user.id,
        subject_id=payload.subject_id,
    )
    db.add(material)
    db.commit()
    db.refresh(material)
    material = cast(CourseMaterial, material)
    return material


@router.post("/upload", response_model=MaterialRead)
async def upload_material(
    title: str = Form(...),
    subject_id: int | None = Form(default=None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user),
) -> CourseMaterial:
    if subject_id is not None:
        subject = (
            db.query(StudySubject)
            .filter(StudySubject.id == subject_id, StudySubject.user_id == current_user.id)
            .first()
        )
        if not subject:
            raise HTTPException(status_code=404, detail="学科不存在")

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(status_code=400, detail="仅支持 PDF / PPTX / DOCX / TXT / MD 文件")

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        data = await file.read()
        tmp.write(data)
        tmp.flush()
        tmp_path = Path(tmp.name)

    content = ""
    try:
        content = extract_text_from_file(tmp_path).strip()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        try:
            unlink(tmp_path)
        except OSError:
            pass

    if not content:
        raise HTTPException(status_code=400, detail="上传内容为空")

    ragflow = RagflowClient()
    dataset_id = await ragflow.upload_document(content, source_name=file.filename or "upload")
    if ragflow.settings.ragflow_enabled and not dataset_id:
        raise HTTPException(
            status_code=502,
            detail="RAGFlow 上传失败：请检查 RAGFlow_BASE_URL / API_KEY / DATASET_ID / 上传接口路径是否正确",
        )

    material: Any = CourseMaterial(
        title=title,
        source_name=file.filename or "upload",
        content=content,
        rag_dataset_id=dataset_id,
        user_id=current_user.id,
        subject_id=subject_id,
    )
    db.add(material)
    db.commit()
    db.refresh(material)
    material = cast(CourseMaterial, material)
    return material


@router.get("", response_model=list[MaterialRead])
def list_materials(db: Session = Depends(get_db), current_user: UserProfile = Depends(get_current_user)) -> list[CourseMaterial]:
    query = db.query(CourseMaterial).order_by(CourseMaterial.created_at.desc())
    query = query.filter(CourseMaterial.user_id == current_user.id)
    materials = cast(list[CourseMaterial], query.all())
    return materials


@router.get("/{material_id}", response_model=MaterialDetail)
def get_material(
    material_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user),
) -> CourseMaterial:
    material = cast(Any, db.get(CourseMaterial, material_id))
    if not material:
        raise HTTPException(status_code=404, detail="资料不存在")
    if material.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问该资料")
    return material

