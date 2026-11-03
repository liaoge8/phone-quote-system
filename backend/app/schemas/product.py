"""商品相关的请求 / 响应模型。"""
from pydantic import BaseModel, ConfigDict, Field


class VariantIn(BaseModel):
    """单个配置：配置名 + 各层价格。"""

    name: str = Field(description="配置名，如 12GB+256GB")
    official_price: float | None = Field(default=None, description="官网价")
    normal_price: float | None = Field(default=None, description="正常价格")
    adjusted_price: float | None = Field(default=None, description="调价后价格")


class ProductCreate(BaseModel):
    brand: str
    model: str
    intro: str = ""
    selling_points: list[str] = []
    status: str = Field(default="on_sale", description="on_sale 在售 / discontinued 停产")
    variants: list[VariantIn] = []
    colors: list[str] = []
    virtual_price: float | None = Field(default=None, description="虚拟价：首次进货价")


class ProductUpdate(BaseModel):
    """更新商品：全部字段可选（停产用 status=discontinued）。"""

    brand: str | None = None
    model: str | None = None
    intro: str | None = None
    selling_points: list[str] | None = None
    status: str | None = None
    variants: list[VariantIn] | None = None
    colors: list[str] | None = None
    virtual_price: float | None = None


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    brand: str
    model: str
    intro: str
    selling_points: list
    status: str
    variants: list
    colors: list
    virtual_price: float | None
