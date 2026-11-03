"""本月政策价模型：每月一条，政策价即最终报价，附政策解释。"""
import sqlalchemy as sa
from sqlalchemy import UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from ..db.session import Base


class PolicyPrice(Base):
    __tablename__ = "policy_prices"
    __table_args__ = (UniqueConstraint("product_id", "month", name="uq_policy_product_month"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(
        sa.ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    # 月份，格式 YYYY-MM，如 2026-11
    month: Mapped[str] = mapped_column(sa.String(7), index=True)
    # 政策价（即最终报价）
    final_price: Mapped[float] = mapped_column(sa.Float)
    # 政策解释文本：显示在本月政策价（最终报价）后面
    explanation: Mapped[str] = mapped_column(sa.Text, default="")

    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now()
    )
