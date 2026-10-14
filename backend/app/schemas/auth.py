"""认证相关 Pydantic 契约。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class RegisterIn(BaseModel):
    student_no: str = Field(min_length=4, max_length=32)
    password: str = Field(min_length=6, max_length=64)
    nickname: str = Field(min_length=1, max_length=64)


class LoginIn(BaseModel):
    student_no: str
    password: str


class UserOut(BaseModel):
    id: int
    student_no: str
    nickname: str
    is_admin: bool
    is_buyer: bool
    is_seller: bool
    is_ai: bool = False
    ai_persona: str = ""
    credit_score: int
    risk_tag: str
    status: str
    avatar_seed: str


class AuthOut(BaseModel):
    token: str
    user: UserOut
