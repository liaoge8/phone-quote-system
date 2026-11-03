"""商品模型：品牌 / 型号 / 介绍 / 卖点 / 状态 / 配置 / 颜色 / 虚拟价。"""
import sqlalchemy as sa
from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column

from ..db.session import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # 品牌，如：苹果 / 华为 / 小米
    brand: Mapped[str] = mapped_column(sa.String(64), index=True)
    # 型号，如：Mate 90 Pro
    model: Mapped[str] = mapped_column(sa.String(128))
    # 手机介绍（长文本）
    intro: Mapped[str] = mapped_column(sa.Text, default="")
    # 卖点列表，JSON 数组，如 ["麒麟芯片", "卫星通信"]
    selling_points: Mapped[list] = mapped_column(sa.JSON, default=list)
    # 状态：on_sale 在售 / discontinued 停产（停产商品自动沉到目录末尾）
    status: Mapped[str] = mapped_column(sa.String(16), default="on_sale", index=True)
    # 配置列表，JSON 数组，每项形如：
    # {"name": "12GB+256GB", "official_price": 6499, "normal_price": 5999, "adjusted_price": 5799}
    variants: Mapped[list] = mapped_column(sa.JSON, default=list)
    # 颜色列表，JSON 数组，如 ["曜石黑", "云白色"]
    colors: Mapped[list] = mapped_column(sa.JSON, default=list)
    # 虚拟价：该手机首次进货的价格，只记一次
    virtual_price: Mapped[float | None] = mapped_column(sa.Float, nullable=True)

    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
