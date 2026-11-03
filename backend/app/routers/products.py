"""商品 / 价格记录 / 本月政策价 / 国补计算接口。"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, select
from sqlalchemy.orm import Session

from ..core.deps import get_current_user, get_db
from ..models import PolicyPrice, PriceRecord, PriceType, Product
from ..schemas import (
    PolicyPriceCreate,
    PolicyPriceOut,
    PriceRecordCreate,
    PriceRecordOut,
    ProductCreate,
    ProductOut,
    ProductUpdate,
)

router = APIRouter(dependencies=[Depends(get_current_user)])

# 国补规则：官网价上限 6000 元；补贴 = min(官网价 x 15%, 500)
SUBSIDY_PRICE_CAP = 6000.0
SUBSIDY_RATE = 0.15
SUBSIDY_MAX = 500.0


def _get_product(db: Session, product_id: int) -> Product:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "商品不存在")
    return product


@router.get("", response_model=list[ProductOut], summary="商品列表（停产自动沉底）")
def list_products(db: Session = Depends(get_db)) -> list[Product]:
    # 在售排前面、停产沉底；同状态按 id 倒序（新的在前）
    # 注意：不能直接按 status 字母序排（discontinued < on_sale），用 case 显式指定
    stmt = select(Product).order_by(
        case((Product.status == "discontinued", 1), else_=0),
        Product.id.desc(),
    )
    return list(db.scalars(stmt).all())


@router.post("", response_model=ProductOut, status_code=status.HTTP_201_CREATED, summary="新增商品")
def create_product(body: ProductCreate, db: Session = Depends(get_db)) -> Product:
    product = Product(
        brand=body.brand,
        model=body.model,
        intro=body.intro,
        selling_points=body.selling_points,
        status=body.status,
        variants=[v.model_dump() for v in body.variants],
        colors=body.colors,
        virtual_price=body.virtual_price,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.get("/{product_id}", response_model=ProductOut, summary="商品详情")
def get_product(product_id: int, db: Session = Depends(get_db)) -> Product:
    return _get_product(db, product_id)


@router.put("/{product_id}", response_model=ProductOut, summary="更新商品（停产改 status）")
def update_product(
    product_id: int, body: ProductUpdate, db: Session = Depends(get_db)
) -> Product:
    product = _get_product(db, product_id)
    data = body.model_dump(exclude_unset=True)
    if "variants" in data and data["variants"] is not None:
        data["variants"] = [v if isinstance(v, dict) else v for v in data["variants"]]
    for key, value in data.items():
        setattr(product, key, value)
    db.commit()
    db.refresh(product)
    return product


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT, summary="删除商品")
def delete_product(product_id: int, db: Session = Depends(get_db)) -> None:
    product = _get_product(db, product_id)
    db.delete(product)
    db.commit()


# ---------------- 价格记录（只追加不覆盖） ----------------


@router.get("/{product_id}/prices", response_model=list[PriceRecordOut], summary="价格记录列表")
def list_prices(product_id: int, db: Session = Depends(get_db)) -> list[PriceRecord]:
    _get_product(db, product_id)
    stmt = (
        select(PriceRecord)
        .where(PriceRecord.product_id == product_id)
        .order_by(PriceRecord.date.desc(), PriceRecord.id.desc())
    )
    return list(db.scalars(stmt).all())


@router.post(
    "/{product_id}/prices",
    response_model=PriceRecordOut,
    status_code=status.HTTP_201_CREATED,
    summary="追加一条价格记录",
)
def add_price(
    product_id: int, body: PriceRecordCreate, db: Session = Depends(get_db)
) -> PriceRecord:
    _get_product(db, product_id)
    valid_types = {t.value for t in PriceType}
    if body.type not in valid_types:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"类型必须是 {sorted(valid_types)} 之一",
        )
    record = PriceRecord(
        product_id=product_id,
        variant=body.variant,
        type=body.type,
        price=body.price,
        date=body.date or date.today(),
        note=body.note,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


# ---------------- 本月政策价 ----------------


@router.get("/{product_id}/policy", response_model=list[PolicyPriceOut], summary="政策价列表")
def list_policies(product_id: int, db: Session = Depends(get_db)) -> list[PolicyPrice]:
    _get_product(db, product_id)
    stmt = (
        select(PolicyPrice)
        .where(PolicyPrice.product_id == product_id)
        .order_by(PolicyPrice.month.desc())
    )
    return list(db.scalars(stmt).all())


@router.post(
    "/{product_id}/policy",
    response_model=PolicyPriceOut,
    status_code=status.HTTP_201_CREATED,
    summary="新增/更新本月政策价",
)
def upsert_policy(
    product_id: int, body: PolicyPriceCreate, db: Session = Depends(get_db)
) -> PolicyPrice:
    """同一商品同一月份只保留一条：存在则更新，不存在则新增。"""
    _get_product(db, product_id)
    stmt = select(PolicyPrice).where(
        PolicyPrice.product_id == product_id, PolicyPrice.month == body.month
    )
    policy = db.scalars(stmt).first()
    if policy is None:
        policy = PolicyPrice(
            product_id=product_id,
            month=body.month,
            final_price=body.final_price,
            explanation=body.explanation,
        )
        db.add(policy)
    else:
        policy.final_price = body.final_price
        policy.explanation = body.explanation
    db.commit()
    db.refresh(policy)
    return policy


# ---------------- 国补计算 ----------------


@router.get("/{product_id}/subsidy", summary="国补计算")
def calc_subsidy(
    product_id: int,
    official_price: float = Query(description="官网价（元）"),
    db: Session = Depends(get_db),
) -> dict:
    """国补规则：
    1. 官网价 > 6000 元：不可做国补；
    2. 否则补贴 = min(官网价 x 15%, 500)，国补价 = 官网价 - 补贴。
    """
    _get_product(db, product_id)
    if official_price > SUBSIDY_PRICE_CAP:
        return {
            "eligible": False,
            "official_price": official_price,
            "reason": f"官网价超过 {SUBSIDY_PRICE_CAP:.0f} 元，不可做国补",
        }
    raw_subsidy = round(official_price * SUBSIDY_RATE, 2)
    subsidy = min(raw_subsidy, SUBSIDY_MAX)
    capped = raw_subsidy > SUBSIDY_MAX
    return {
        "eligible": True,
        "official_price": official_price,
        # 公式明细：前端直接展示
        "formula": f"min(官网价 x 15%, 500) = min({official_price} x 15%, 500)",
        "raw_subsidy": raw_subsidy,
        "subsidy": subsidy,
        "capped": capped,
        "capped_note": "已按 500 元封顶" if capped else "",
        "final_price": round(official_price - subsidy, 2),
    }
