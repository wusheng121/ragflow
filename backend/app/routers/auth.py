import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import User
from app.deps import get_current_user, get_db
from app.schemas import AuthTokenOut, UserLogin, UserOut, UserRegister
from app.services.auth import create_access_token, hash_password, verify_password
from app.utils.id_gen import new_id

router = APIRouter(prefix="/auth", tags=["auth"])


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _username_from_email(email: str, db: Session) -> str:
    local = email.split("@", 1)[0]
    base = re.sub(r"[^\w.-]", "", local)[:32] or "user"
    candidate = base
    n = 0
    while db.query(User).filter(User.username == candidate).first():
        n += 1
        candidate = f"{base}{n}"[:64]
    return candidate


@router.post("/register", response_model=AuthTokenOut)
def register(body: UserRegister, db: Session = Depends(get_db)):
    email = _normalize_email(body.email)
    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="请输入有效的邮箱地址")
    if len(body.password) < 6:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="密码至少 6 位")
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="该邮箱已被注册")

    user = User(
        id=new_id(),
        username=_username_from_email(email, db),
        email=email,
        password_hash=hash_password(body.password),
        created_at=datetime.utcnow(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(user.id, user.username)
    return AuthTokenOut(
        access_token=token,
        user=UserOut(id=user.id, username=user.username, email=user.email, created_at=user.created_at),
    )


@router.post("/login", response_model=AuthTokenOut)
def login(body: UserLogin, db: Session = Depends(get_db)):
    email = _normalize_email(body.email)
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="邮箱或密码错误")
    token = create_access_token(user.id, user.username)
    return AuthTokenOut(
        access_token=token,
        user=UserOut(id=user.id, username=user.username, email=user.email, created_at=user.created_at),
    )


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return UserOut(id=user.id, username=user.username, email=user.email, created_at=user.created_at)
