"""销量存档模型：每月一条，用于同比 / 环比对比。"""
import sqlalchemy as sa
from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column

from ..db.session import Base


class SalesArchive(Base):
    __tablename__ = "sales_archives"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # 月份，格式 YYYY-MM，唯一（如 2026-10）
    month: Mapped[str] = mapped_column(sa.String(7), unique=True, index=True)
    # 出货量（万部）
    shipments: Mapped[float] = mapped_column(sa.Float)
    # 数据来源，如 "信通院" / "数码闲聊站"
    source: Mapped[str] = mapped_column(sa.String(64), default="")

    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now()
    )
