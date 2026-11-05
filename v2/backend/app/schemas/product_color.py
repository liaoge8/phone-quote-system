from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProductColorCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    color_name: str = Field(min_length=1, max_length=60)

    @field_validator("color_name")
    @classmethod
    def strip_color(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("颜色名称不能为空")
        return value


class ProductColorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    product_id: int
    color_name: str
    created_at: datetime
