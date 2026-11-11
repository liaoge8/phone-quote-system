import csv
from datetime import date
from io import StringIO

from decimal import Decimal

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
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
def price_overview(as_of: date | None = None, export: bool = False, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    cutoff = as_of or date.today()
    month_start = cutoff.replace(day=1)
    next_month = date(cutoff.year + (cutoff.month == 12), cutoff.month % 12 + 1, 1)
    products = list(db.scalars(
        select(Product).where(Product.archived_at.is_(None), Product.status == "on_sale").order_by(Product.brand, Product.model)
    ).all())
    product_ids = [p.id for p in products]

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
            STRebate.effective_date >= month_start,
            STRebate.effective_date <= cutoff,
            STRebate.voided_at.is_(None),
        ).order_by(STRebate.effective_date.desc(), STRebate.id.desc())
    ).all()
    policies = db.scalars(
        select(PolicyPrice).where(
            PolicyPrice.product_id.in_(product_ids),
            PolicyPrice.effective_month == month_start,
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
            "net_price": (base.price - (rebate.amount if rebate is not None else Decimal("0")) - (policy.policy_price if policy is not None else Decimal("0"))) if base else None,
            "policy_interpretation": policy.interpretation if policy else None,
            "policy_effective_date": policy.effective_date if policy else None,
        })
    items.sort(key=lambda x: (x["brand"], x["model"], x["variant"]))
    if export:
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["品牌", "机型", "配置", "基础价格", "基础价格生效日期", "ST返利", "ST返利生效日期", "政策返利", "到手价", "政策解释", "政策返利生效日期"])
        for item in items:
            writer.writerow([
                item["brand"], item["model"], item["variant"],
                str(item["base_price"]) if item["base_price"] is not None else "",
                item["base_effective_date"] or "",
                str(item["st_rebate"]) if item["st_rebate"] is not None else "",
                item["st_rebate_effective_date"] or "",
                str(item["policy_price"]) if item["policy_price"] is not None else "",
                str(item["net_price"]) if item["net_price"] is not None else "",
                item["policy_interpretation"] or "",
                item["policy_effective_date"] or "",
            ])
        output.seek(0)
        filename = f"phone-price-overview-{cutoff.isoformat()}.csv"
        return StreamingResponse(
            iter([output.getvalue().encode("utf-8-sig")]),
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-Export-Row-Count": str(len(items)),
            },
        )
    return {"as_of": cutoff, "items": items}
