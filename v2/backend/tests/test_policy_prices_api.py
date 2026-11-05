from datetime import date, timedelta
import hashlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.product import Product
from app.models.user import User
from app.routers.policies import current_business_month


@pytest.fixture()
def policy_client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestingSession() as db:
        admin = User(username="policy_admin", password_hash=hash_password("admin-password-123"), role="admin")
        member = User(username="policy_member", password_hash=hash_password("member-password-123"), role="member")
        product = Product(brand="华为", model="政策价测试机")
        db.add_all([admin, member, product])
        db.commit()
        ids = (product.id, admin.id, member.id)

    with TestClient(app) as client:
        yield client, *ids, TestingSession

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def auth(client, username, password):
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def create_policy(client, headers, product_id, effective_date, **overrides):
    payload = {
        "product_id": product_id,
        "variant": "12+256G",
        "effective_date": effective_date.isoformat(),
        "policy_price": "3699.00",
        "interpretation": "本次政策明确该配置按新政策价格执行，适用本渠道",
        "note": "渠道政策通知",
    }
    payload.update(overrides)
    return client.post("/api/policies", headers=headers, json=payload)


def test_member_can_create_policy_and_recorder_is_injected(policy_client):
    client, product_id, _admin_id, member_id, _session = policy_client
    headers = auth(client, "policy_member", "member-password-123")
    effective = current_business_month().replace(day=3)
    response = create_policy(client, headers, product_id, effective)
    assert response.status_code == 201, response.text
    assert response.json()["recorded_by"] == member_id
    assert response.json()["effective_date"] == effective.isoformat()
    assert response.json()["policy_price"] == "3699.00"


def test_multiple_policy_changes_in_same_month_are_allowed(policy_client):
    client, product_id, _admin_id, _member_id, _session = policy_client
    headers = auth(client, "policy_member", "member-password-123")
    first = current_business_month().replace(day=1)
    second = first.replace(day=16)
    one = create_policy(client, headers, product_id, first, policy_price="3699.00")
    two = create_policy(client, headers, product_id, second, policy_price="3599.00",
                        interpretation="自本月下半月起执行的新政策，替代此前阶段价格")
    assert one.status_code == 201, one.text
    assert two.status_code == 201, two.text
    rows = client.get("/api/policies", headers=headers, params={"month": first.isoformat()})
    assert rows.status_code == 200
    assert len(rows.json()) == 2
    assert {row["effective_date"] for row in rows.json()} == {first.isoformat(), second.isoformat()}


def test_policy_requires_interpretation_and_effective_date(policy_client):
    client, product_id, _admin_id, _member_id, _session = policy_client
    headers = auth(client, "policy_member", "member-password-123")
    bad = client.post("/api/policies", headers=headers, json={
        "product_id": product_id, "variant": "12+256G", "effective_date": "2026-11-16",
        "policy_price": "3699.00",
    })
    assert bad.status_code == 422


def test_admin_can_edit_current_month_but_member_cannot(policy_client):
    client, product_id, _admin_id, _member_id, _session = policy_client
    month = current_business_month()
    effective = month.replace(day=5)
    admin_headers = auth(client, "policy_admin", "admin-password-123")
    member_headers = auth(client, "policy_member", "member-password-123")
    created = create_policy(client, member_headers, product_id, effective)
    record_id = created.json()["id"]

    denied = client.patch(f"/api/policies/{record_id}", headers=member_headers, json={
        "policy_price": "3500.00", "interpretation": "管理员才可以调整当前月份政策内容"
    })
    assert denied.status_code == 403
    updated = client.patch(f"/api/policies/{record_id}", headers=admin_headers, json={
        "policy_price": "3500.00", "interpretation": "当前月份经核实后的政策解释与价格调整"
    })
    assert updated.status_code == 200, updated.text
    assert updated.json()["policy_price"] == "3500.00"


def test_historical_month_policy_is_frozen_and_member_cannot_see_voided(policy_client):
    client, product_id, _admin_id, _member_id, _session = policy_client
    admin_headers = auth(client, "policy_admin", "admin-password-123")
    member_headers = auth(client, "policy_member", "member-password-123")
    previous = (current_business_month() - timedelta(days=1)).replace(day=1)
    created = create_policy(client, admin_headers, product_id, previous.replace(day=10))
    assert created.status_code == 201, created.text
    frozen = client.patch(f"/api/policies/{created.json()['id']}", headers=admin_headers, json={
        "policy_price": "3400.00", "interpretation": "历史政策更正测试，历史月份不允许直接编辑"
    })
    assert frozen.status_code == 409
    voided = client.patch(f"/api/policies/{created.json()['id']}/void", headers=admin_headers,
                          json={"reason": "原政策录入错误，保留后重新登记"})
    assert voided.status_code == 200
    denied = client.get("/api/policies", headers=member_headers,
                        params={"month": previous.isoformat(), "include_voided": True})
    assert denied.status_code == 403


def test_screenshot_evidence_upload_is_hashed_and_retrievable(policy_client, tmp_path, monkeypatch):
    from app.routers import policies
    monkeypatch.setattr(policies.settings, "policy_evidence_dir", str(tmp_path))
    client, product_id, _admin_id, _member_id, _session = policy_client
    headers = auth(client, "policy_member", "member-password-123")
    created = create_policy(client, headers, product_id, current_business_month().replace(day=16))
    assert created.status_code == 201, created.text
    image = b"\x89PNG\r\n\x1a\n" + b"test-image-content"
    upload = client.post(f"/api/policies/{created.json()['id']}/evidence",
                         headers=headers, files={"file": ("policy.png", image, "image/png")})
    assert upload.status_code == 201, upload.text
    evidence = upload.json()
    assert evidence["sha256"] == hashlib.sha256(image).hexdigest()
    listed = client.get(f"/api/policies/{created.json()['id']}/evidence", headers=headers)
    assert listed.status_code == 200 and len(listed.json()) == 1
    fetched = client.get(f"/api/policies/evidence/{evidence['id']}/file", headers=headers)
    assert fetched.status_code == 200
    assert fetched.content == image


def test_evidence_download_rejects_tampered_file(policy_client, tmp_path, monkeypatch):
    from app.routers import policies
    monkeypatch.setattr(policies.settings, "policy_evidence_dir", str(tmp_path))
    client, product_id, _admin_id, _member_id, _session = policy_client
    headers = auth(client, "policy_member", "member-password-123")
    created = create_policy(client, headers, product_id, current_business_month().replace(day=16))
    image = b"\\x89PNG\\r\\n\\x1a\\n" + b"original-image-content"
    upload = client.post(
        f"/api/policies/{created.json()['id']}/evidence",
        headers=headers,
        files={"file": ("policy.png", image, "image/png")},
    )
    assert upload.status_code == 201, upload.text
    evidence = upload.json()
    (tmp_path / evidence["storage_key"]).write_bytes(b"tampered")
    fetched = client.get(
        f"/api/policies/evidence/{evidence['id']}/file",
        headers=headers,
    )
    assert fetched.status_code == 500
    assert "完整性校验失败" in fetched.json()["detail"]


def test_evidence_upload_rejects_mismatched_image_signature(policy_client, tmp_path, monkeypatch):
    from app.routers import policies
    monkeypatch.setattr(policies.settings, "policy_evidence_dir", str(tmp_path))
    client, product_id, _admin_id, _member_id, _session = policy_client
    headers = auth(client, "policy_member", "member-password-123")
    created = create_policy(client, headers, product_id, current_business_month().replace(day=16))
    response = client.post(
        f"/api/policies/{created.json()['id']}/evidence",
        headers=headers,
        files={"file": ("fake.png", b"not-a-png-file", "image/png")},
    )
    assert response.status_code == 415
