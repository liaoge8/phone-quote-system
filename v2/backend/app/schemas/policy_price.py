from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PolicyPriceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: int = Field(gt=0)
    variant: str = Field(min_length=1, max_length=100)
    effective_date: date
    policy_price: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    interpretation: str = Field(min_length=5, max_length=5000)
    note: str | None = Field(default=None, max_length=2000)

    @field_validator("variant", "interpretation")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("内容不能为空")
        return value


class PolicyPriceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_price: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    interpretation: str = Field(min_length=5, max_length=5000)
    note: str | None = Field(default=None, max_length=2000)


class PolicyPriceVoid(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=5, max_length=500)


class PolicyPriceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    variant: str
    variant_id: int | None
    effective_month: date
    effective_date: date
    policy_price: Decimal
    interpretation: str
    note: str | None
    recorded_by: int
    created_at: datetime
    updated_at: datetime
    voided_at: datetime | None
    voided_by: int | None
    void_reason: str | None


class PolicyEvidenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    policy_price_id: int
    original_filename: str
    content_type: str
    file_size: int
    sha256: str
    uploaded_by: int
    created_at: datetime
