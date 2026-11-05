import hashlib
import uuid
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user, require_admin
from app.core.time import BUSINESS_TZ, utc_now
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.policy_price import PolicyEvidence, PolicyPrice
from app.models.product import Product
from app.models.user import User
from app.schemas.policy_price import (
    PolicyEvidenceOut, PolicyPriceCreate, PolicyPriceOut,
    PolicyPriceUpdate, PolicyPriceVoid,
)

router = APIRouter()
MAX_EVIDENCE_BYTES = 10 * 1024 * 1024
ALLOWED_EVIDENCE_TYPES = {"image/jpeg", "image/png", "image/webp"}


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
    return list(db.scalars(stmt.order_by(PolicyPrice.effective_date, PolicyPrice.product_id, PolicyPrice.variant, PolicyPrice.id)).all())


@router.post("", response_model=PolicyPriceOut, status_code=201)
def create_policy_price(
    body: PolicyPriceCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    product = db.get(Product, body.product_id)
    if not product or product.archived_at or product.status != "on_sale":
        raise HTTPException(404, "商品不存在或已停用")
    month = body.effective_date.replace(day=1)
    record = PolicyPrice(
        product_id=body.product_id,
        variant=body.variant,
        effective_month=month,
        effective_date=body.effective_date,
        policy_price=body.policy_price,
        interpretation=body.interpretation,
        note=body.note,
        recorded_by=user.id,
    )
    db.add(record)
    db.flush()
    db.add(AuditLog(actor_id=user.id, action="policy_price.created", target_type="policy_price", target_id=str(record.id), detail={
        "effective_date": record.effective_date.isoformat(),
        "price": str(record.policy_price),
        "interpretation": record.interpretation,
    }))
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
    old = {"price": str(record.policy_price), "interpretation": record.interpretation, "note": record.note}
    record.policy_price = body.policy_price
    record.interpretation = body.interpretation
    record.note = body.note
    record.updated_at = utc_now()
    db.add(AuditLog(actor_id=admin.id, action="policy_price.updated", target_type="policy_price", target_id=str(record.id), detail={
        "old": old,
        "new": {"price": str(record.policy_price), "interpretation": record.interpretation, "note": record.note},
    }))
    db.commit()
    db.refresh(record)
    return record


@router.post("/{record_id}/evidence", response_model=PolicyEvidenceOut, status_code=201)
async def upload_policy_evidence(
    record_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    record = db.get(PolicyPrice, record_id)
    if not record:
        raise HTTPException(404, "政策价记录不存在")
    if file.content_type not in ALLOWED_EVIDENCE_TYPES:
        raise HTTPException(415, "仅支持 JPG、PNG、WEBP 图片")
    content = await file.read(MAX_EVIDENCE_BYTES + 1)
    if not content or len(content) > MAX_EVIDENCE_BYTES:
        raise HTTPException(413, "截图不能为空且不能超过 10MB")
    signature_ok = (
        (file.content_type == "image/jpeg" and content.startswith(b"\xff\xd8\xff"))
        or (file.content_type == "image/png" and content.startswith(b"\x89PNG\r\n\x1a\n"))
        or (file.content_type == "image/webp" and content.startswith(b"RIFF") and content[8:12] == b"WEBP")
    )
    if not signature_ok:
        raise HTTPException(415, "图片内容与文件类型不匹配")
    storage_key = uuid.uuid4().hex
    storage_dir = Path(settings.policy_evidence_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)
    stored_path = storage_dir / storage_key
    stored_path.write_bytes(content)
    evidence = PolicyEvidence(
        policy_price_id=record.id,
        original_filename=Path((file.filename or "policy-evidence").replace("\\", "/")).name[:255],
        storage_key=storage_key,
        content_type=file.content_type,
        file_size=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        uploaded_by=user.id,
    )
    db.add(evidence)
    db.add(AuditLog(actor_id=user.id, action="policy_evidence.uploaded", target_type="policy_price", target_id=str(record.id), detail={
        "evidence_id": storage_key,
        "filename": evidence.original_filename,
        "sha256": evidence.sha256,
        "size": evidence.file_size,
    }))
    try:
        db.commit()
        db.refresh(evidence)
    except Exception:
        db.rollback()
        stored_path.unlink(missing_ok=True)
        raise
    return evidence


@router.get("/{record_id}/evidence", response_model=list[PolicyEvidenceOut])
def list_policy_evidence(
    record_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    if not db.get(PolicyPrice, record_id):
        raise HTTPException(404, "政策价记录不存在")
    return list(db.scalars(select(PolicyEvidence).where(
        PolicyEvidence.policy_price_id == record_id
    ).order_by(PolicyEvidence.id)).all())


@router.get("/evidence/{evidence_id}/file")
def get_policy_evidence_file(
    evidence_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    evidence = db.get(PolicyEvidence, evidence_id)
    if not evidence:
        raise HTTPException(404, "证据文件不存在")
    storage_dir = Path(settings.policy_evidence_dir).resolve()
    path = (storage_dir / evidence.storage_key).resolve()
    if path.parent != storage_dir:
        raise HTTPException(500, "证据文件存储路径异常")
    if not path.is_file():
        raise HTTPException(404, "证据文件缺失，请检查持久化存储")
    # Verify the persisted bytes against the upload-time digest before serving evidence.
    actual_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual_sha256 != evidence.sha256:
        raise HTTPException(500, "证据文件完整性校验失败，请从备份恢复")
    return FileResponse(path, media_type=evidence.content_type, filename=evidence.original_filename)


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
    db.add(AuditLog(actor_id=admin.id, action="policy_price.voided", target_type="policy_price", target_id=str(record.id), detail={
        "reason": record.void_reason,
        "original_price": str(record.policy_price),
        "effective_date": record.effective_date.isoformat(),
    }))
    db.commit()
    return {"id": record.id, "voided": True}
