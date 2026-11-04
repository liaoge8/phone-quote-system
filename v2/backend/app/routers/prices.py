from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.deps import get_current_user, require_admin
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.price_record import PriceRecord
from app.models.product import Product
from app.models.user import User
from app.schemas.price_record import PriceRecordCreate, PriceRecordOut
router = APIRouter()
@router.post('/products/{product_id}/prices', response_model=PriceRecordOut, status_code=201)
def add_price(product_id: int, body: PriceRecordCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    product = db.get(Product, product_id)
    if not product or product.archived_at:
        raise HTTPException(404, '商品不存在或已停用')
    record = PriceRecord(product_id=product_id, recorded_by=user.id, **body.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    db.add(AuditLog(actor_id=user.id, action='price.created', target_type='price_record', target_id=str(record.id)))
    db.commit()
    return record
@router.get('/products/{product_id}/prices', response_model=list[PriceRecordOut])
def list_prices(product_id: int, start: date | None = None, end: date | None = None, as_of: date | None = None, include_voided: bool = False, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if start and end and start > end:
        raise HTTPException(422, '开始日期不能晚于结束日期')
    stmt = select(PriceRecord).where(PriceRecord.product_id == product_id)
    if not include_voided:
        stmt = stmt.where(PriceRecord.voided_at.is_(None))
    if as_of:
        stmt = stmt.where(PriceRecord.effective_date <= as_of)
    else:
        if start: stmt = stmt.where(PriceRecord.effective_date >= start)
        if end: stmt = stmt.where(PriceRecord.effective_date <= end)
    return list(db.scalars(stmt.order_by(PriceRecord.effective_date.desc(), PriceRecord.id.desc())).all())
@router.patch('/prices/{record_id}/void')
def void_price(record_id: int, reason: str, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    if len(reason.strip()) < 5:
        raise HTTPException(422, '作废原因至少 5 个字')
    record = db.get(PriceRecord, record_id)
    if not record or record.voided_at:
        raise HTTPException(404, '价格记录不存在或已作废')
    from datetime import datetime, timezone
    record.voided_at = datetime.now(timezone.utc)
    record.voided_by = admin.id
    record.void_reason = reason.strip()
    db.add(AuditLog(actor_id=admin.id, action='price.voided', target_type='price_record', target_id=str(record.id), detail={'reason': reason.strip(), 'original_price': str(record.price)}))
    db.commit()
    return {'id': record.id, 'voided': True}
