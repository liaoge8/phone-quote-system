from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class STRebateCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    variant: str = Field(min_length=1, max_length=100)
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    effective_date: date
    note: str | None = None


class STRebateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    variant: str
    variant_id: int | None
    amount: Decimal
    effective_date: date
    note: str | None
    recorded_by: int
    created_at: datetime
    voided_at: datetime | None
    voided_by: int | None
    void_reason: str | None
