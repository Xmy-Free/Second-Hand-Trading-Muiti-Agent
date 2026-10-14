"""公共依赖：当前用户 / 管理员 / 交易冻结拦截。"""
from __future__ import annotations

from fastapi import Depends, Header
from sqlmodel import Session

from app.core.database import get_session
from app.core.response import BizError
from app.core.security import decode_token
from app.models import User


def current_user(
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise BizError("未登录或令牌缺失", code=401, http_status=401)
    uid = decode_token(authorization.removeprefix("Bearer ").strip())
    if uid is None:
        raise BizError("登录状态已过期，请重新登录", code=401, http_status=401)
    user = session.get(User, uid)
    if user is None:
        raise BizError("用户不存在", code=401, http_status=401)
    return user


def admin_user(user: User = Depends(current_user)) -> User:
    if not user.is_admin:
        raise BizError("需要管理员权限", code=403, http_status=403)
    return user


def trading_user(user: User = Depends(current_user)) -> User:
    if user.status == "frozen":
        raise BizError("账号已被冻结，仅可浏览与申诉", code=403, http_status=403)
    return user
