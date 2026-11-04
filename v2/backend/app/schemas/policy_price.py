from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PolicyPriceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: int = Field(gt=0)
    variant: str = Field(min_length=1, max_length=100)
    effective_month: date
    policy_price: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    note: str | None = Field(default=None, max_length=2000)

    @field_validator("variant")
    @classmethod
    def strip_variant(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("版本配置不能为空")
        return value

    @field_validator("effective_month")
    @classmethod
    def first_day_of_month(cls, value: date) -> date:
        if value.day != 1:
            raise ValueError("effective_month 必须使用当月第一天，例如 2026-11-01")
        return value


class PolicyPriceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_price: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    note: str | None = Field(default=None, max_length=2000)


class PolicyPriceVoid(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=5, max_length=500)


class PolicyPriceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    variant: str
    effective_month: date
    policy_price: Decimal
    note: str | None
    recorded_by: int
    created_at: datetime
    updated_at: datetime
    voided_at: datetime | None
    voided_by: int | None
    void_reason: str | None
