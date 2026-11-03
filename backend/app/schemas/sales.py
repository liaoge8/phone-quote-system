"""销量存档相关的请求 / 响应模型。"""
from pydantic import BaseModel, ConfigDict, Field


class SalesArchiveCreate(BaseModel):
    month: str = Field(description="月份，格式 YYYY-MM")
    shipments: float = Field(description="出货量（万部）")
    source: str = Field(default="", description="数据来源，如 信通院")


class SalesArchiveOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    month: str
    shipments: float
    source: str


class SalesCompareOut(BaseModel):
    """两月销量对比结果。"""

    m1: str
    m2: str
    m1_shipments: float | None
    m2_shipments: float | None
    diff: float | None = Field(description="差值（m2 - m1，万部）")
    change_rate: float | None = Field(description="涨跌幅（小数，如 0.12 表示 +12%）")
