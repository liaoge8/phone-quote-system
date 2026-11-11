from pathlib import Path

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from app.core.time import BUSINESS_TZ
from app.models.policy_price import PolicyPrice
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user, require_admin
from app.core.time import utc_now
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.price_record import PriceRecord
from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.models.product_color import ProductColor
from app.models.st_rebate import STRebate
from app.models.policy_price import PolicyEvidence
from app.models.st_rebate import STRebate
from app.models.user import User
from app.schemas.product import ProductArchiveIn, ProductCreate, ProductOut, ProductUpdate
from app.schemas.product_variant import ProductVariantCreate, ProductVariantOut
from app.schemas.product_color import ProductColorCreate, ProductColorOut

router = APIRouter()


@router.get("", response_model=list[ProductOut])
def list_products(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    variant_count = select(func.count(ProductVariant.id)).where(
        ProductVariant.product_id == Product.id,
        ProductVariant.is_active.is_(True),
    ).scalar_subquery()
    color_count = select(func.count(ProductColor.id)).where(
        ProductColor.product_id == Product.id,
    ).scalar_subquery()
    today = utc_now().astimezone(BUSINESS_TZ).date()
    month_start = today.replace(day=1)
    policy_from = select(func.max(PolicyPrice.policy_price)).where(
        PolicyPrice.product_id == Product.id,
        PolicyPrice.effective_month == month_start,
        PolicyPrice.effective_date <= today,
        PolicyPrice.voided_at.is_(None),
    ).scalar_subquery()
    stmt = (
        select(Product, variant_count.label("variants_count"), color_count.label("colors_count"), policy_from.label("current_policy_from"))
        .where(Product.archived_at.is_(None), Product.status == "on_sale")
        .order_by(Product.id.desc())
    )
    rows = db.execute(stmt).all()
    product_ids = [p.id for p, _v, _c, _pf in rows]
    net_from_map = {}
    if product_ids:
        next_month = date(today.year + (today.month == 12), today.month % 12 + 1, 1)
        base_map, st_map, pol_map = {}, {}, {}
        for pid, variant, price in db.execute(
            select(PriceRecord.product_id, PriceRecord.variant, PriceRecord.price)
            .where(PriceRecord.product_id.in_(product_ids), PriceRecord.price_type == "基础价格",
                   PriceRecord.effective_date <= today, PriceRecord.voided_at.is_(None))
            .order_by(PriceRecord.effective_date.desc(), PriceRecord.id.desc())
        ).all():
            base_map.setdefault((pid, variant), price)
        for pid, variant, amount in db.execute(
            select(STRebate.product_id, STRebate.variant, STRebate.amount)
            .where(STRebate.product_id.in_(product_ids), STRebate.effective_date >= month_start,
                   STRebate.effective_date <= today, STRebate.voided_at.is_(None))
            .order_by(STRebate.effective_date.desc(), STRebate.id.desc())
        ).all():
            st_map.setdefault((pid, variant), amount)
        for pid, variant, policy_price in db.execute(
            select(PolicyPrice.product_id, PolicyPrice.variant, PolicyPrice.policy_price)
            .where(PolicyPrice.product_id.in_(product_ids), PolicyPrice.effective_month == month_start,
                   PolicyPrice.effective_date <= today, PolicyPrice.voided_at.is_(None))
            .order_by(PolicyPrice.effective_date.desc(), PolicyPrice.id.desc())
        ).all():
            pol_map.setdefault((pid, variant), policy_price)
        nets = {}
        for key, base in base_map.items():
            st = st_map.get(key)
            pol = pol_map.get(key)
            nets.setdefault(key[0], []).append(base - (st if st is not None else Decimal("0")) - (pol if pol is not None else Decimal("0")))
        net_from_map = {pid: min(values) for pid, values in nets.items()}
    return [
        {"id": p.id, "brand": p.brand, "model": p.model, "intro": p.intro,
         "status": p.status, "tagline": p.tagline, "selling_points": p.selling_points or [],
         "variants_count": variants, "colors_count": colors, "current_policy_from": policy_price,
         "net_from": net_from_map.get(p.id)}
        for p, variants, colors, policy_price in rows
    ]


@router.get("/archived")
def list_archived_products(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    stmt = select(Product).where(
        Product.archived_at.is_not(None),
        Product.status == "discontinued",
    ).order_by(Product.archived_at.desc(), Product.id.desc())
    return [
        {
            "id": product.id,
            "brand": product.brand,
            "model": product.model,
            "archive_reason": product.archive_reason,
            "archived_at": product.archived_at,
        }
        for product in db.scalars(stmt).all()
    ]


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



@router.get("/{product_id}/variants", response_model=list[ProductVariantOut])
def list_product_variants(
    product_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    if not db.get(Product, product_id):
        raise HTTPException(404, "商品不存在")
    stmt = select(ProductVariant).where(
        ProductVariant.product_id == product_id,
        ProductVariant.is_active.is_(True),
    ).order_by(ProductVariant.id)
    return list(db.scalars(stmt).all())


@router.post("/{product_id}/variants", response_model=ProductVariantOut, status_code=201)
def create_product_variant(
    product_id: int,
    body: ProductVariantCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    product = db.get(Product, product_id)
    if not product or product.archived_at or product.status != "on_sale":
        raise HTTPException(404, "商品不存在或已停用")
    existing = db.scalar(select(ProductVariant).where(
        ProductVariant.product_id == product_id,
        ProductVariant.display_name == body.display_name,
    ))
    if existing and existing.is_active:
        raise HTTPException(409, "该商品配置已存在")
    if existing:
        existing.is_active = True
        existing.ram = body.ram
        existing.storage = body.storage
        variant = existing
        db.add(AuditLog(
            actor_id=admin.id,
            action="product_variant.restored",
            target_type="product_variant",
            target_id=str(variant.id),
            detail={"product_id": product_id, "display_name": variant.display_name},
        ))
    else:
        variant = ProductVariant(product_id=product_id, **body.model_dump())
        db.add(variant)
        db.flush()
        db.add(AuditLog(
            actor_id=admin.id,
            action="product_variant.created",
            target_type="product_variant",
            target_id=str(variant.id),
            detail={"product_id": product_id, "display_name": variant.display_name},
        ))
    db.commit()
    db.refresh(variant)
    return variant


@router.get("/{product_id}/colors", response_model=list[ProductColorOut])
def list_product_colors(
    product_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    if not db.get(Product, product_id):
        raise HTTPException(404, "商品不存在")
    return list(db.scalars(
        select(ProductColor).where(ProductColor.product_id == product_id).order_by(ProductColor.id)
    ).all())


@router.post("/{product_id}/colors", response_model=ProductColorOut, status_code=201)
def create_product_color(
    product_id: int,
    body: ProductColorCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    product = db.get(Product, product_id)
    if not product or product.archived_at or product.status != "on_sale":
        raise HTTPException(404, "商品不存在或已停用")
    existing = db.scalar(select(ProductColor).where(
        ProductColor.product_id == product_id,
        ProductColor.color_name == body.color_name,
    ))
    if existing:
        raise HTTPException(409, "该商品颜色已登记")
    color = ProductColor(product_id=product_id, color_name=body.color_name)
    db.add(color)
    db.flush()
    db.add(AuditLog(
        actor_id=admin.id,
        action="product_color.created",
        target_type="product_color",
        target_id=str(color.id),
        detail={"product_id": product_id, "color_name": color.color_name},
    ))
    db.commit()
    db.refresh(color)
    return color


@router.delete("/{product_id}")
def delete_product(product_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(404, "商品不存在")

    prices = list(db.scalars(select(PriceRecord).where(PriceRecord.product_id == product_id)).all())
    rebates = list(db.scalars(select(STRebate).where(STRebate.product_id == product_id)).all())
    policies = list(db.scalars(select(PolicyPrice).where(PolicyPrice.product_id == product_id)).all())
    policy_ids = [p.id for p in policies]
    evidences = list(db.scalars(select(PolicyEvidence).where(
        PolicyEvidence.policy_price_id.in_(policy_ids)
    )).all()) if policy_ids else []

    storage_dir = Path(settings.policy_evidence_dir)
    for evidence in evidences:
        (storage_dir / evidence.storage_key).unlink(missing_ok=True)

    colors = list(db.scalars(select(ProductColor).where(ProductColor.product_id == product_id)).all())
    variants = list(db.scalars(select(ProductVariant).where(ProductVariant.product_id == product_id)).all())

    db.add(AuditLog(
        actor_id=admin.id,
        action="product.deleted",
        target_type="product",
        target_id=str(product_id),
        detail={
            "brand": product.brand,
            "model": product.model,
            "price_records": len(prices),
            "st_rebates": len(rebates),
            "policy_prices": len(policies),
            "evidence_files": len(evidences),
            "variants": len(variants),
            "colors": len(colors),
        },
    ))
    for evidence in evidences:
        db.delete(evidence)
    for policy in policies:
        db.delete(policy)
    for record in prices:
        db.delete(record)
    for record in rebates:
        db.delete(record)
    for color in colors:
        db.delete(color)
    for variant in variants:
        db.delete(variant)
    db.delete(product)
    db.commit()
    return {
        "id": product_id,
        "deleted": True,
        "removed": {
            "price_records": len(prices),
            "st_rebates": len(rebates),
            "policy_prices": len(policies),
            "evidence_files": len(evidences),
        },
    }


@router.patch("/{product_id}")
def update_product(product_id: int, body: ProductUpdate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(404, "商品不存在")
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(422, "没有需要更新的字段")
    old = {}
    for key, value in changes.items():
        current = getattr(product, key)
        old[key] = list(current) if isinstance(current, list) else current
    for key, value in changes.items():
        setattr(product, key, value)
    db.add(AuditLog(
        actor_id=admin.id,
        action="product.updated",
        target_type="product",
        target_id=str(product.id),
        detail={"old": old, "new": {k: (list(v) if isinstance(v, list) else v) for k, v in changes.items()}},
    ))
    db.commit()
    return {"id": product.id, "brand": product.brand, "model": product.model, "intro": product.intro,
            "status": product.status, "tagline": product.tagline, "selling_points": product.selling_points or []}


@router.delete("/{product_id}/variants/{variant_id}")
def delete_product_variant(product_id: int, variant_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    if not db.get(Product, product_id):
        raise HTTPException(404, "商品不存在")
    variant = db.get(ProductVariant, variant_id)
    if not variant or variant.product_id != product_id:
        raise HTTPException(404, "配置不存在")
    if not variant.is_active:
        raise HTTPException(404, "配置已删除")
    variant.is_active = False
    db.add(AuditLog(
        actor_id=admin.id,
        action="product_variant.deleted",
        target_type="product_variant",
        target_id=str(variant.id),
        detail={"product_id": product_id, "display_name": variant.display_name},
    ))
    db.commit()
    return {"id": variant_id, "deleted": True, "display_name": variant.display_name}


@router.delete("/{product_id}/colors/{color_id}")
def delete_product_color(product_id: int, color_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    if not db.get(Product, product_id):
        raise HTTPException(404, "商品不存在")
    color = db.get(ProductColor, color_id)
    if not color or color.product_id != product_id:
        raise HTTPException(404, "颜色不存在")
    db.add(AuditLog(
        actor_id=admin.id,
        action="product_color.deleted",
        target_type="product_color",
        target_id=str(color.id),
        detail={"product_id": product_id, "color_name": color.color_name},
    ))
    db.delete(color)
    db.commit()
    return {"id": color_id, "deleted": True, "color_name": color.color_name}
