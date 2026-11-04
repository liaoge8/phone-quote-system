from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class PriceRecordCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    variant: str = Field(min_length=1, max_length=100)
    price_type: str = Field(min_length=1, max_length=32)
    price: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    effective_date: date
    note: str | None = None


class PriceRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    variant: str
    price_type: str
    price: Decimal
    effective_date: date
    note: str | None
    recorded_by: int
    created_at: datetime
    voided_at: datetime | None
    voided_by: int | None
    void_reason: str | None
