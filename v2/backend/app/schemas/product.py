from pydantic import BaseModel, ConfigDict, Field


class ProductCreate(BaseModel):
    brand: str = Field(min_length=1, max_length=40)
    model: str = Field(min_length=1, max_length=100)
    intro: str | None = None


class ProductArchiveIn(BaseModel):
    reason: str = Field(min_length=5, max_length=500)


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    brand: str
    model: str
    intro: str | None
    status: str
