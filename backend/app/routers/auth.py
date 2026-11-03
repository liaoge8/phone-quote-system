"""登录接口：密码正确即签发 JWT。"""
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from ..core.security import create_access_token, verify_password

router = APIRouter()


class LoginIn(BaseModel):
    password: str


class LoginOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/login", response_model=LoginOut, summary="密码登录")
def login(body: LoginIn) -> LoginOut:
    if not verify_password(body.password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "密码不正确")
    return LoginOut(access_token=create_access_token())
