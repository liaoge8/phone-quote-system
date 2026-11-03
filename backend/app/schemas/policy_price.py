"""本月政策价相关的请求 / 响应模型。"""
from pydantic import BaseModel, ConfigDict, Field


class PolicyPriceCreate(BaseModel):
    month: str = Field(description="月份，格式 YYYY-MM，如 2026-11")
    final_price: float = Field(description="政策价（即最终报价）")
    explanation: str = Field(default="", description="政策解释文本")


class PolicyPriceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    month: str
    final_price: float
    explanation: str
