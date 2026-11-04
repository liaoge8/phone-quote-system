from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_admin
from app.core.security import create_access_token, hash_password, verify_password
from app.core.time import utc_now
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.auth import (
    LoginIn,
    TokenOut,
    UserCreate,
    PasswordChangeIn,
    PasswordResetIn,
    UserStatusIn,
    UserOut,
)

router = APIRouter()


def _audit(db: Session, actor_id: int, action: str, target_id: int, detail: dict | None = None):
    db.add(AuditLog(
        actor_id=actor_id,
        action=action,
        target_type="user",
        target_id=str(target_id),
        detail=detail,
    ))


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == body.username))
    if not user or not user.is_active or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "账号或密码错误")
    return TokenOut(access_token=create_access_token(user.id, user.role, user.token_epoch))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.post("/password")
def change_own_password(
    body: PasswordChangeIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not verify_password(body.old_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "原密码不正确")
    try:
        user.password_hash = hash_password(body.new_password)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    user.token_epoch += 1
    user.updated_at = utc_now()
    _audit(db, user.id, "user.password_changed", user.id)
    db.commit()
    return {"message": "密码已修改，请使用新密码重新登录"}


@router.get("/users", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    return list(db.scalars(select(User).order_by(User.id)).all())


@router.post("/users", status_code=201)
def create_user(
    body: UserCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if body.role not in {"admin", "member"}:
        raise HTTPException(422, "角色只能是 admin 或 member")
    if db.scalar(select(User).where(User.username == body.username)):
        raise HTTPException(409, "用户名已存在")
    try:
        password_hash = hash_password(body.password)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    user = User(username=body.username, password_hash=password_hash, role=body.role)
    db.add(user)
    db.flush()
    _audit(db, admin.id, "user.created", user.id, {"username": user.username, "role": user.role})
    db.commit()
    return {"id": user.id, "username": user.username, "role": user.role}


@router.post("/users/{user_id}/reset-password")
def reset_user_password(
    user_id: int,
    body: PasswordResetIn,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(404, "成员不存在")
    try:
        target.password_hash = hash_password(body.new_password)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    target.token_epoch += 1
    target.updated_at = utc_now()
    _audit(db, admin.id, "user.password_reset", target.id)
    db.commit()
    return {"message": "密码已重置，该成员原有登录状态已失效"}


@router.patch("/users/{user_id}/status")
def set_user_status(
    user_id: int,
    body: UserStatusIn,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(404, "成员不存在")
    if target.id == admin.id and not body.is_active:
        raise HTTPException(400, "不能停用当前登录的管理员账号")
    if target.is_active == body.is_active:
        return {"id": target.id, "is_active": target.is_active, "changed": False}
    if not body.is_active and target.role == "admin":
        active_admins = db.scalar(
            select(func.count(User.id)).where(User.role == "admin", User.is_active.is_(True))
        ) or 0
        if active_admins <= 1:
            raise HTTPException(400, "不能停用最后一个启用中的管理员")
    target.is_active = body.is_active
    target.token_epoch += 1
    target.updated_at = utc_now()
    action = "user.enabled" if body.is_active else "user.disabled"
    _audit(db, admin.id, action, target.id, {"username": target.username})
    db.commit()
    return {"id": target.id, "is_active": target.is_active, "changed": True}


@router.get("/audit-logs")
def list_audit_logs(
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Admin-only audit trail; records are append-only and returned newest first."""
    if limit < 1 or limit > 500 or offset < 0:
        raise HTTPException(422, "limit 范围为 1-500，offset 不能小于 0")
    rows = db.scalars(
        select(AuditLog).order_by(AuditLog.id.desc()).offset(offset).limit(limit)
    ).all()
    return [
        {
            "id": row.id,
            "actor_id": row.actor_id,
            "action": row.action,
            "target_type": row.target_type,
            "target_id": row.target_id,
            "detail": row.detail,
            "created_at": row.created_at,
        }
        for row in rows
    ]
