from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
class PriceRecord(Base):
    __tablename__ = 'price_records'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey('products.id', ondelete='RESTRICT'), index=True, nullable=False)
    variant: Mapped[str] = mapped_column(String(100), nullable=False)
    price_type: Mapped[str] = mapped_column(String(32), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    recorded_by: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='RESTRICT'), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    voided_by: Mapped[int | None] = mapped_column(ForeignKey('users.id', ondelete='RESTRICT'))
    void_reason: Mapped[str | None] = mapped_column(Text)
    product = relationship('Product', back_populates='price_records')
