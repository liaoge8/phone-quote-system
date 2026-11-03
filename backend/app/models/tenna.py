"""入网台账模型：工信部 / TENAA 新入网登记的手机，置顶展示用。"""
import sqlalchemy as sa
from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column

from ..db.session import Base


class TennaRecord(Base):
    __tablename__ = "tenna_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # 入网日期
    reg_date: Mapped[sa.Date] = mapped_column(sa.Date, server_default=func.current_date())
    # 机型，如 "小米 19 Pro"（对外名称，可能暂缺）
    phone_model: Mapped[str] = mapped_column(sa.String(128), default="")
    # 入网型号，如 "25128PNA1C"
    tenna_model: Mapped[str] = mapped_column(sa.String(64), index=True)
    # 配置要点，如 "6.8 英寸屏 / 骁龙 8 Elite Gen6 / 5500mAh"
    specs: Mapped[str] = mapped_column(sa.Text, default="")
    # 跟进状态：pending 待跟进 / followed 已跟进 / done 已完结
    status: Mapped[str] = mapped_column(sa.String(16), default="pending", index=True)

    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now()
    )
