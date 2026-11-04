from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import LoginIn, TokenOut, UserCreate
from app.core.deps import require_admin
router = APIRouter()
@router.post('/login', response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == body.username))
    if not user or not user.is_active or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, '账号或密码错误')
    return TokenOut(access_token=create_access_token(user.id, user.role, user.token_epoch))
@router.post('/users', status_code=201)
def create_user(body: UserCreate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    if body.role not in {'admin', 'member'}:
        raise HTTPException(422, '角色只能是 admin 或 member')
    if db.scalar(select(User).where(User.username == body.username)):
        raise HTTPException(409, '用户名已存在')
    user = User(username=body.username, password_hash=hash_password(body.password), role=body.role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return {'id': user.id, 'username': user.username, 'role': user.role}
