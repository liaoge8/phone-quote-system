"""数据库引擎与会话。默认 SQLite；DATABASE_URL 可切换为 PostgreSQL。"""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from ..core.config import settings

# SQLite 需要 check_same_thread=False 才能在 FastAPI 多线程中使用
connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

# pool_pre_ping：远程库连接断开后自动重连，避免长时间空闲后首次请求报错
engine = create_engine(settings.DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """所有 ORM 模型的基类。"""


def init_db() -> None:
    """建表（v1 用 create_all；生产建议改用 Alembic 做迁移）。"""
    from .. import models  # noqa: F401 触发全部模型注册

    Base.metadata.create_all(bind=engine)
