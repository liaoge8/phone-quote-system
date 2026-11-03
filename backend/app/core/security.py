"""安全相关：密码比对（secrets 恒定时间比对）与 JWT 签发/校验。"""
import secrets
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from .config import settings

ALGORITHM = "HS256"


def verify_password(plain_password: str) -> bool:
    """把用户输入的密码与环境变量中的管理员密码做恒定时间比对。"""
    return secrets.compare_digest(plain_password, settings.ADMIN_PASSWORD)


def create_access_token() -> str:
    """签发 JWT（单管理员，sub 固定为 admin）。"""
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    return jwt.encode({"sub": "admin", "exp": expire}, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> str | None:
    """校验 JWT，成功返回 sub，失败返回 None。"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None
