from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_admin
from app.core.time import utc_now
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.models.st_rebate import STRebate
from app.models.user import User
from app.schemas.st_rebate import STRebateCreate, STRebateOut

router = APIRouter()


@router.post("/products/{product_id}/st-rebates", response_model=STRebateOut, status_code=201)
def create_st_rebate(product_id: int, body: STRebateCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    product = db.get(Product, product_id)
    if not product or product.archived_at or product.status != "on_sale":
        raise HTTPException(404, "商品不存在或已停用")
    variant = db.scalar(select(ProductVariant).where(
        ProductVariant.product_id == product_id,
        ProductVariant.display_name == body.variant,
        ProductVariant.is_active.is_(True),
    ))
    if not variant:
        raise HTTPException(422, "请先在商品档案中登记该配置")
    record = STRebate(product_id=product_id, variant_id=variant.id, recorded_by=user.id, **body.model_dump())
    db.add(record)
    db.flush()
    db.add(AuditLog(actor_id=user.id, action="st_rebate.created", target_type="st_rebate", target_id=str(record.id)))
    db.commit()
    db.refresh(record)
    return record


@router.get("/products/{product_id}/st-rebates", response_model=list[STRebateOut])
def list_st_rebates(product_id: int, as_of: date | None = None, include_voided: bool = False, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not db.get(Product, product_id):
        raise HTTPException(404, "商品不存在")
    if include_voided and user.role != "admin":
        db.add(AuditLog(actor_id=user.id, action="denied", target_type="st_rebate", target_id=str(product_id), detail={"operation": "include_voided"}))
        db.commit()
        raise HTTPException(403, "无权查看作废记录")
    stmt = select(STRebate).where(STRebate.product_id == product_id)
    if not include_voided:
        stmt = stmt.where(STRebate.voided_at.is_(None))
    if as_of:
        stmt = stmt.where(STRebate.effective_date <= as_of)
    return list(db.scalars(stmt.order_by(STRebate.effective_date.desc(), STRebate.id.desc())).all())


@router.patch("/st-rebates/{record_id}/void")
def void_st_rebate(record_id: int, reason: str, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    if len(reason.strip()) < 5:
        raise HTTPException(422, "作废原因至少 5 个字")
    record = db.get(STRebate, record_id)
    if not record or record.voided_at:
        raise HTTPException(404, "ST返利记录不存在或已作废")
    record.voided_at = utc_now()
    record.voided_by = admin.id
    record.void_reason = reason.strip()
    db.add(AuditLog(actor_id=admin.id, action="st_rebate.voided", target_type="st_rebate", target_id=str(record.id), detail={"reason": reason.strip(), "original_amount": str(record.amount)}))
    db.commit()
    return {"id": record.id, "voided": True}


@router.delete("/st-rebates/{record_id}")
def delete_st_rebate(record_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    record = db.get(STRebate, record_id)
    if not record:
        raise HTTPException(404, "ST返利记录不存在")
    db.add(AuditLog(actor_id=admin.id, action="st_rebate.deleted", target_type="st_rebate", target_id=str(record.id), detail={
        "product_id": record.product_id,
        "variant_id": record.variant_id,
        "amount": str(record.amount),
        "effective_date": record.effective_date.isoformat(),
        "voided": record.voided_at is not None,
    }))
    db.delete(record)
    db.commit()
    return {"id": record_id, "deleted": True}
