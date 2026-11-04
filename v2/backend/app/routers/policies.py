from datetime import date
from sqlalchemy import select
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_admin
from app.core.time import BUSINESS_TZ, utc_now
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.policy_price import PolicyPrice
from app.models.product import Product
from app.models.user import User
from app.schemas.policy_price import PolicyPriceCreate, PolicyPriceOut, PolicyPriceUpdate, PolicyPriceVoid

router = APIRouter()


def current_business_month() -> date:
    now = utc_now().astimezone(BUSINESS_TZ)
    return date(now.year, now.month, 1)


@router.get("", response_model=list[PolicyPriceOut])
def list_policy_prices(
    month: date,
    include_voided: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if month.day != 1:
        raise HTTPException(422, "month 必须为当月第一天，例如 2026-11-01")
    if include_voided and user.role != "admin":
        db.add(AuditLog(actor_id=user.id, action="denied", target_type="policy_price", target_id=month.isoformat(), detail={"operation": "include_voided"}))
        db.commit()
        raise HTTPException(403, "无权查看作废政策价")
    stmt = select(PolicyPrice).where(PolicyPrice.effective_month == month)
    if not include_voided:
        stmt = stmt.where(PolicyPrice.voided_at.is_(None))
    return list(db.scalars(stmt.order_by(PolicyPrice.product_id, PolicyPrice.variant, PolicyPrice.id.desc())).all())


@router.post("", response_model=PolicyPriceOut, status_code=201)
def create_policy_price(
    body: PolicyPriceCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    product = db.get(Product, body.product_id)
    if not product or product.archived_at or product.status != "on_sale":
        raise HTTPException(404, "商品不存在或已停用")
    duplicate = db.scalar(select(PolicyPrice.id).where(
        PolicyPrice.product_id == body.product_id,
        PolicyPrice.variant == body.variant,
        PolicyPrice.effective_month == body.effective_month,
        PolicyPrice.voided_at.is_(None),
    ))
    if duplicate:
        raise HTTPException(409, "该商品版本本月已有有效政策价；请先作废旧记录再重录")
    record = PolicyPrice(**body.model_dump(), recorded_by=user.id)
    db.add(record)
    db.flush()
    db.add(AuditLog(actor_id=user.id, action="policy_price.created", target_type="policy_price", target_id=str(record.id), detail={"month": record.effective_month.isoformat(), "price": str(record.policy_price)}))
    db.commit()
    db.refresh(record)
    return record


@router.patch("/{record_id}", response_model=PolicyPriceOut)
def update_current_month_policy_price(
    record_id: int,
    body: PolicyPriceUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    record = db.get(PolicyPrice, record_id)
    if not record or record.voided_at:
        raise HTTPException(404, "政策价记录不存在或已作废")
    if record.effective_month != current_business_month():
        raise HTTPException(409, "历史月份政策价已冻结；请作废后重新录入")
    old_price, old_note = str(record.policy_price), record.note
    record.policy_price = body.policy_price
    record.note = body.note
    record.updated_at = utc_now()
    db.add(AuditLog(actor_id=admin.id, action="policy_price.updated", target_type="policy_price", target_id=str(record.id), detail={"old_price": old_price, "new_price": str(record.policy_price), "old_note": old_note, "new_note": record.note}))
    db.commit()
    db.refresh(record)
    return record


@router.patch("/{record_id}/void")
def void_policy_price(
    record_id: int,
    body: PolicyPriceVoid,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    record = db.get(PolicyPrice, record_id)
    if not record or record.voided_at:
        raise HTTPException(404, "政策价记录不存在或已作废")
    record.voided_at = utc_now()
    record.voided_by = admin.id
    record.void_reason = body.reason.strip()
    db.add(AuditLog(actor_id=admin.id, action="policy_price.voided", target_type="policy_price", target_id=str(record.id), detail={"reason": record.void_reason, "original_price": str(record.policy_price), "month": record.effective_month.isoformat()}))
    db.commit()
    return {"id": record.id, "voided": True}
