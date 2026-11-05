from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.policy_price import PolicyPrice
from app.models.price_record import PriceRecord
from app.models.product import Product
from app.models.st_rebate import STRebate
from app.models.user import User

router = APIRouter()


@router.get("/price-overview")
def price_overview(as_of: date | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    cutoff = as_of or date.today()
    products = list(db.scalars(
        select(Product).where(Product.archived_at.is_(None), Product.status == "on_sale").order_by(Product.brand, Product.model)
    ).all())
    product_ids = [p.id for p in products]
    if not product_ids:
        return {"as_of": cutoff, "items": []}

    bases = db.scalars(
        select(PriceRecord).where(
            PriceRecord.product_id.in_(product_ids),
            PriceRecord.price_type == "基础价格",
            PriceRecord.effective_date <= cutoff,
            PriceRecord.voided_at.is_(None),
        ).order_by(PriceRecord.effective_date.desc(), PriceRecord.id.desc())
    ).all()
    rebates = db.scalars(
        select(STRebate).where(
            STRebate.product_id.in_(product_ids),
            STRebate.effective_date <= cutoff,
            STRebate.voided_at.is_(None),
        ).order_by(STRebate.effective_date.desc(), STRebate.id.desc())
    ).all()
    policies = db.scalars(
        select(PolicyPrice).where(
            PolicyPrice.product_id.in_(product_ids),
            PolicyPrice.effective_date <= cutoff,
            PolicyPrice.voided_at.is_(None),
        ).order_by(PolicyPrice.effective_date.desc(), PolicyPrice.id.desc())
    ).all()

    product_map = {p.id: p for p in products}
    selected = {}
    for record in bases:
        selected.setdefault((record.product_id, record.variant), {"base": record})
    for record in rebates:
        selected.setdefault((record.product_id, record.variant), {}) .setdefault("rebate", record)
    for record in policies:
        selected.setdefault((record.product_id, record.variant), {}) .setdefault("policy", record)

    items = []
    for (product_id, variant), values in selected.items():
        product = product_map[product_id]
        base = values.get("base")
        rebate = values.get("rebate")
        policy = values.get("policy")
        items.append({
            "product_id": product_id,
            "brand": product.brand,
            "model": product.model,
            "variant": variant,
            "base_price": base.price if base else None,
            "base_effective_date": base.effective_date if base else None,
            "st_rebate": rebate.amount if rebate else None,
            "st_rebate_effective_date": rebate.effective_date if rebate else None,
            "policy_price": policy.policy_price if policy else None,
            "policy_effective_date": policy.effective_date if policy else None,
        })
    items.sort(key=lambda x: (x["brand"], x["model"], x["variant"]))
    return {"as_of": cutoff, "items": items}
