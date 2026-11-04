from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.deps import get_current_user, require_admin
from app.db.session import get_db
from app.models.product import Product
from app.models.user import User
from app.schemas.product import ProductCreate, ProductOut
router = APIRouter()
@router.get('', response_model=list[ProductOut])
def list_products(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    stmt = select(Product).where(Product.archived_at.is_(None)).order_by(Product.id.desc())
    return list(db.scalars(stmt).all())
@router.post('', response_model=ProductOut, status_code=201)
def create_product(body: ProductCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    product = Product(**body.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product
@router.patch('/{product_id}/archive')
def archive_product(product_id: int, reason: str, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    if len(reason.strip()) < 5:
        raise HTTPException(422, '停用原因至少 5 个字')
    product = db.get(Product, product_id)
    if not product or product.archived_at:
        raise HTTPException(404, '商品不存在或已停用')
    from datetime import datetime, timezone
    product.status = 'discontinued'
    product.archived_at = datetime.now(timezone.utc)
    product.archived_by = admin.id
    product.archive_reason = reason.strip()
    db.commit()
    return {'id': product.id, 'status': product.status}
