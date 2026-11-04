import os
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.core.security import hash_password
from app.db.session import get_db
from app.models.user import User
router = APIRouter()
@router.post('/first-admin', include_in_schema=False)
def create_first_admin(username: str, password: str, db: Session = Depends(get_db)):
    # One-time bootstrap is enabled only when explicitly configured and user table is empty.
    if os.getenv('ALLOW_FIRST_ADMIN_BOOTSTRAP') != 'true':
        raise HTTPException(404, 'Not found')
    if db.scalar(select(func.count()).select_from(User)):
        raise HTTPException(409, '管理员已初始化')
    if len(password) < 10:
        raise HTTPException(422, '初始密码至少 10 位')
    user = User(username=username, password_hash=hash_password(password), role='admin')
    db.add(user)
    db.commit()
    return {'id': user.id, 'username': user.username, 'role': user.role}
