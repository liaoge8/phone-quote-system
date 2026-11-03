"""情报中心：入网台账 CRUD（新入网登记的手机，置顶展示用）。"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.deps import get_current_user, get_db
from ..models import TennaRecord
from ..schemas import TennaCreate, TennaOut, TennaUpdate

router = APIRouter(dependencies=[Depends(get_current_user)])


def _get_record(db: Session, record_id: int) -> TennaRecord:
    record = db.get(TennaRecord, record_id)
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "记录不存在")
    return record


@router.get("/tenna", response_model=list[TennaOut], summary="入网台账列表（新的在前）")
def list_tenna(db: Session = Depends(get_db)) -> list[TennaRecord]:
    stmt = select(TennaRecord).order_by(TennaRecord.reg_date.desc(), TennaRecord.id.desc())
    return list(db.scalars(stmt).all())


@router.post("/tenna", response_model=TennaOut, status_code=status.HTTP_201_CREATED, summary="新增入网记录")
def create_tenna(body: TennaCreate, db: Session = Depends(get_db)) -> TennaRecord:
    from datetime import date

    record = TennaRecord(
        reg_date=body.reg_date or date.today(),
        phone_model=body.phone_model,
        tenna_model=body.tenna_model,
        specs=body.specs,
        status=body.status,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.put("/tenna/{record_id}", response_model=TennaOut, summary="更新入网记录（含跟进状态）")
def update_tenna(
    record_id: int, body: TennaUpdate, db: Session = Depends(get_db)
) -> TennaRecord:
    record = _get_record(db, record_id)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(record, key, value)
    db.commit()
    db.refresh(record)
    return record


@router.delete("/tenna/{record_id}", status_code=status.HTTP_204_NO_CONTENT, summary="删除入网记录")
def delete_tenna(record_id: int, db: Session = Depends(get_db)) -> None:
    record = _get_record(db, record_id)
    db.delete(record)
    db.commit()
