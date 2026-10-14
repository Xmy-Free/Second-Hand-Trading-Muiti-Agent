"""认证路由：注册 / 登录 / 当前用户。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.api.deps import current_user
from app.core.database import get_session
from app.core.response import BizError, ok
from app.core.security import create_access_token, hash_password, verify_password
from app.models import User
from app.schemas.auth import AuthOut, LoginIn, RegisterIn, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


def to_user_out(u: User) -> UserOut:
    return UserOut.model_validate(u, from_attributes=True)


@router.post("/register")
def register(body: RegisterIn, session: Session = Depends(get_session)):
    exists = session.exec(select(User).where(User.student_no == body.student_no)).first()
    if exists:
        raise BizError("该学号已注册")
    user = User(
        student_no=body.student_no,
        password_hash=hash_password(body.password),
        nickname=body.nickname,
        risk_tag="new",
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    token = create_access_token(user.id)
    return ok(AuthOut(token=token, user=to_user_out(user)).model_dump(), "注册成功")


@router.post("/login")
def login(body: LoginIn, session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.student_no == body.student_no)).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise BizError("学号或密码错误", code=401, http_status=401)
    token = create_access_token(user.id)
    return ok(AuthOut(token=token, user=to_user_out(user)).model_dump(), "登录成功")


@router.get("/me")
def me(user: User = Depends(current_user)):
    return ok(to_user_out(user).model_dump())
