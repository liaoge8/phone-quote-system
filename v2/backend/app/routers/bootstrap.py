import os
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.core.security import hash_password
from app.db.session import get_db
from app.models.user import User
router = APIRouter()
class FirstAdminIn(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r'^[a-zA-Z0-9_.-]+$')
    password: str = Field(min_length=10, max_length=128)
@router.post('/first-admin', include_in_schema=False)
def create_first_admin(body: FirstAdminIn, db: Session = Depends(get_db)):
    # One-time bootstrap is enabled only when explicitly configured and user table is empty.
    if os.getenv('ALLOW_FIRST_ADMIN_BOOTSTRAP') != 'true':
        raise HTTPException(404, 'Not found')
    if db.scalar(select(func.count()).select_from(User)):
        raise HTTPException(409, '管理员已初始化')
    user = User(username=body.username, password_hash=hash_password(body.password), role='admin')
    db.add(user)
    db.commit()
    return {'id': user.id, 'username': user.username, 'role': user.role}
