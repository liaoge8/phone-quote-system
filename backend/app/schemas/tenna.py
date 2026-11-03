"""入网台账相关的请求 / 响应模型。"""
from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class TennaCreate(BaseModel):
    reg_date: date | None = Field(default=None, description="入网日期，默认今天")
    phone_model: str = Field(default="", description="机型")
    tenna_model: str = Field(description="入网型号")
    specs: str = Field(default="", description="配置要点")
    status: str = Field(default="pending", description="pending/followed/done")


class TennaUpdate(BaseModel):
    reg_date: date | None = None
    phone_model: str | None = None
    tenna_model: str | None = None
    specs: str | None = None
    status: str | None = None


class TennaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reg_date: date
    phone_model: str
    tenna_model: str
    specs: str
    status: str
