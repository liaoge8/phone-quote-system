"""价格记录模型：只追加不覆盖，一年后仍可查每个时段的价格。"""
import enum

import sqlalchemy as sa
from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column

from ..db.session import Base


class PriceType(str, enum.Enum):
    """价格类型（与前端五层价格 + 官网价格对应）。"""

    VIRTUAL = "virtual"  # 首次进货价（虚拟价）
    NORMAL = "normal"  # 正常价格
    ADJUSTED = "adjusted"  # 调价后价格
    POLICY = "policy"  # 政策价格
    OFFICIAL = "official"  # 官网价
    OFFICIAL_PROMO = "official_promo"  # 官网优惠后价格


class PriceRecord(Base):
    __tablename__ = "price_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(
        sa.ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    # 配置名，如 "12GB+256GB"（与 Product.variants 中的 name 对应）
    variant: Mapped[str] = mapped_column(sa.String(64), default="")
    # 价格类型（PriceType 的值）
    type: Mapped[str] = mapped_column(sa.String(16), index=True)
    # 价格（元）
    price: Mapped[float] = mapped_column(sa.Float)
    # 该价格生效/记录的日期
    date: Mapped[sa.Date] = mapped_column(sa.Date, server_default=func.current_date())
    # 备注，如调价原因、政策月份
    note: Mapped[str] = mapped_column(sa.String(256), default="")

    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now()
    )
