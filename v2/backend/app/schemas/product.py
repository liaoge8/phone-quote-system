from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProductCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    brand: str = Field(min_length=1, max_length=40)
    model: str = Field(min_length=1, max_length=100)
    intro: str | None = None
    tagline: str | None = Field(default=None, max_length=160)
    selling_points: list[str] = Field(default_factory=list, max_length=8)

    @field_validator("brand", "model")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("不能为空或仅包含空格")
        return value


class ProductArchiveIn(BaseModel):
    reason: str = Field(min_length=5, max_length=500)


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    brand: str
    model: str
    intro: str | None
    status: str
    variants_count: int = 0
    colors_count: int = 0
