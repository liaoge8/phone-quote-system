from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_admin
from app.core.time import utc_now
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.price_record import PriceRecord
from app.models.product import Product
from app.models.user import User
from app.schemas.product import ProductArchiveIn, ProductCreate, ProductOut

router = APIRouter()


@router.get("", response_model=list[ProductOut])
def list_products(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    stmt = (
        select(Product)
        .where(Product.archived_at.is_(None), Product.status == "on_sale")
        .order_by(Product.id.desc())
    )
    return list(db.scalars(stmt).all())


@router.post("", response_model=ProductOut, status_code=201)
def create_product(
    body: ProductCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    product = Product(**body.model_dump())
    db.add(product)
    db.flush()
    db.add(
        AuditLog(
            actor_id=user.id,
            action="product.created",
            target_type="product",
            target_id=str(product.id),
        )
    )
    db.commit()
    db.refresh(product)
    return product


@router.patch("/{product_id}/archive")
def archive_product(
    product_id: int,
    body: ProductArchiveIn,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    reason = body.reason.strip()
    if len(reason) < 5:
        raise HTTPException(422, "停用原因至少 5 个字")

    product = db.get(Product, product_id)
    if not product or product.archived_at or product.status != "on_sale":
        raise HTTPException(404, "商品不存在或已停用")

    history_count = db.scalar(
        select(func.count(PriceRecord.id)).where(PriceRecord.product_id == product_id)
    ) or 0

    product.status = "discontinued"
    product.archived_at = utc_now()
    product.archived_by = admin.id
    product.archive_reason = reason
    db.add(
        AuditLog(
            actor_id=admin.id,
            action="product.archived",
            target_type="product",
            target_id=str(product.id),
            detail={"reason": reason, "price_history_count": history_count},
        )
    )
    db.commit()
    return {
        "id": product.id,
        "status": product.status,
        "price_history_count": history_count,
        "message": f"商品已停用，保留 {history_count} 条价格历史；管理员可恢复。",
        "restorable": True,
    }


@router.post("/{product_id}/restore")
def restore_product(
    product_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    product = db.get(Product, product_id)
    if not product or not product.archived_at or product.status != "discontinued":
        raise HTTPException(404, "商品不存在或当前未停用")

    previous_reason = product.archive_reason
    product.status = "on_sale"
    product.archived_at = None
    product.archived_by = None
    product.archive_reason = None
    db.add(
        AuditLog(
            actor_id=admin.id,
            action="product.restored",
            target_type="product",
            target_id=str(product.id),
            detail={"previous_archive_reason": previous_reason},
        )
    )
    db.commit()
    return {"id": product.id, "status": product.status, "restored": True}
