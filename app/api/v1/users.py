from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import UserProfile
from app.schemas import AuthResponse, UserLoginRequest, UserRead, UserRegisterRequest
from app.services.auth_service import create_access_token, get_current_user, hash_password, verify_password


router = APIRouter(prefix="/users", tags=["users"])


def _find_user(db: Session, name: str) -> UserProfile | None:
    return db.query(UserProfile).filter(UserProfile.name == name).first()


def _to_auth_response(user: UserProfile) -> AuthResponse:
    return AuthResponse(access_token=create_access_token(user), user=UserRead.model_validate(user))


@router.post("/register", response_model=AuthResponse)
def register_user(payload: UserRegisterRequest, db: Session = Depends(get_db)) -> AuthResponse:
    existing = _find_user(db, payload.name)
    if existing:
        raise HTTPException(status_code=400, detail="用户名已存在")
    user = UserProfile(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        level=payload.level,
        is_active=True,
        last_login_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _to_auth_response(user)


@router.post("/login", response_model=AuthResponse)
def login_user(payload: UserLoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
    user = _find_user(db, payload.name)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在，请先注册")
    if not user.password_hash or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    user.last_login_at = datetime.now(timezone.utc)
    db.add(user)
    db.commit()
    db.refresh(user)
    return _to_auth_response(user)


@router.get("/me", response_model=UserRead)
def read_me(current_user: UserProfile = Depends(get_current_user)) -> UserProfile:
    return current_user


@router.post("/logout")
def logout_user() -> dict[str, str]:
    return {"message": "已退出登录"}


@router.post("", response_model=AuthResponse)
def create_user(payload: UserRegisterRequest, db: Session = Depends(get_db)) -> AuthResponse:
    return register_user(payload, db)


@router.get("", response_model=list[UserRead])
def list_users(db: Session = Depends(get_db), current_user: UserProfile = Depends(get_current_user)) -> list[UserProfile]:
    return db.query(UserProfile).order_by(UserProfile.created_at.desc()).all()


@router.get("/{user_id}", response_model=UserRead)
def get_user(user_id: int, db: Session = Depends(get_db), current_user: UserProfile = Depends(get_current_user)) -> UserProfile:
    user = db.query(UserProfile).filter(UserProfile.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user


