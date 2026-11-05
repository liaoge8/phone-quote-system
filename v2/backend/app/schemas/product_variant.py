from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProductVariantCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(min_length=1, max_length=100)
    ram: str | None = Field(default=None, max_length=20)
    storage: str | None = Field(default=None, max_length=20)

    @field_validator("display_name")
    @classmethod
    def clean_display_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("配置名称不能为空")
        return value


class ProductVariantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    display_name: str
    ram: str | None
    storage: str | None
    is_active: bool
    created_at: datetime
