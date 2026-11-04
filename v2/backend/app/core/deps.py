from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.user import User
from app.core.security import decode_access_token
bearer = HTTPBearer(auto_error=False)
def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User:
    if credentials is None: raise HTTPException(status.HTTP_401_UNAUTHORIZED, '请先登录')
    try:
        claims = decode_access_token(credentials.credentials)
        user_id, role, epoch = int(claims['uid']), claims['role'], int(claims['ep'])
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, '登录状态无效或已过期')
    user = db.get(User, user_id)
    if not user or not user.is_active or user.token_epoch != epoch or user.role != role:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, '登录状态已失效')
    return user
def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != 'admin': raise HTTPException(status.HTTP_403_FORBIDDEN, '无权执行此操作')
    return user
