"""销量分析：销量存档 + 两月同比/环比对比。"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.deps import get_current_user, get_db
from ..models import SalesArchive
from ..schemas import SalesArchiveCreate, SalesArchiveOut, SalesCompareOut

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("/archives", response_model=list[SalesArchiveOut], summary="销量存档列表")
def list_archives(db: Session = Depends(get_db)) -> list[SalesArchive]:
    stmt = select(SalesArchive).order_by(SalesArchive.month.desc())
    return list(db.scalars(stmt).all())


@router.post(
    "/archives",
    response_model=SalesArchiveOut,
    status_code=status.HTTP_201_CREATED,
    summary="新增/更新月度销量存档",
)
def upsert_archive(body: SalesArchiveCreate, db: Session = Depends(get_db)) -> SalesArchive:
    """同一月份只保留一条：存在则更新，不存在则新增。"""
    stmt = select(SalesArchive).where(SalesArchive.month == body.month)
    archive = db.scalars(stmt).first()
    if archive is None:
        archive = SalesArchive(month=body.month, shipments=body.shipments, source=body.source)
        db.add(archive)
    else:
        archive.shipments = body.shipments
        archive.source = body.source
    db.commit()
    db.refresh(archive)
    return archive


@router.get("/compare", response_model=SalesCompareOut, summary="两月销量对比")
def compare_sales(
    m1: str = Query(description="基准月份，格式 YYYY-MM，如 2025-10"),
    m2: str = Query(description="对比月份，格式 YYYY-MM，如 2026-10"),
    db: Session = Depends(get_db),
) -> SalesCompareOut:
    """返回两月出货量、差值、涨跌幅（如去年 10 月 vs 今年 10 月）。"""
    a1 = db.scalars(select(SalesArchive).where(SalesArchive.month == m1)).first()
    a2 = db.scalars(select(SalesArchive).where(SalesArchive.month == m2)).first()
    if a1 is None or a2 is None:
        missing = [m for m, a in ((m1, a1), (m2, a2)) if a is None]
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"缺少存档数据：{', '.join(missing)}"
        )
    diff = round(a2.shipments - a1.shipments, 2)
    change_rate = round(diff / a1.shipments, 4) if a1.shipments else None
    return SalesCompareOut(
        m1=m1,
        m2=m2,
        m1_shipments=a1.shipments,
        m2_shipments=a2.shipments,
        diff=diff,
        change_rate=change_rate,
    )
