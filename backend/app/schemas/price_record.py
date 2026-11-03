"""价格记录相关的请求 / 响应模型。"""
# 注意：字段名 date 会遮蔽 datetime.date，所以导入时用了别名 date_type
from datetime import date as date_type

from pydantic import BaseModel, ConfigDict, Field


class PriceRecordCreate(BaseModel):
    variant: str = Field(default="", description="配置名")
    type: str = Field(description="virtual/normal/adjusted/policy/official/official_promo")
    price: float = Field(description="价格（元）")
    date: date_type | None = Field(default=None, description="生效日期，默认今天")
    note: str = Field(default="", description="备注，如调价原因")


class PriceRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    variant: str
    type: str
    price: float
    date: date_type
    note: str
