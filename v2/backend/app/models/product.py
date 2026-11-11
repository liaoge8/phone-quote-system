from datetime import datetime
from decimal import Decimal
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
class Product(Base):
    __tablename__ = 'products'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    brand: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    model: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    intro: Mapped[str | None] = mapped_column(Text)
    tagline: Mapped[str | None] = mapped_column(String(160))
    selling_points: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(20), default='on_sale', nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_by: Mapped[int | None] = mapped_column(ForeignKey('users.id', ondelete='RESTRICT'))
    archive_reason: Mapped[str | None] = mapped_column(Text)

    official_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    official_url: Mapped[str | None] = mapped_column(String(500))
    official_price_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    price_records = relationship('PriceRecord', back_populates='product', passive_deletes=True)
    variants = relationship('ProductVariant', passive_deletes=True, order_by='ProductVariant.id')
    colors = relationship('ProductColor', passive_deletes=True, order_by='ProductColor.id')
