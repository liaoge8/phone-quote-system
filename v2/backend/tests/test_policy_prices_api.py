from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.audit_log import AuditLog
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


def previous_month(month: date) -> date:
    return (month.replace(day=1) - timedelta(days=1)).replace(day=1)


def create_policy(client, headers, product_id, month, **overrides):
    payload = {
        "product_id": product_id,
        "variant": "12+256G",
        "effective_month": month.isoformat(),
        "policy_price": "3699.00",
        "note": "月度政策价",
    }
    payload.update(overrides)
    return client.post("/api/policies", headers=headers, json=payload)


def test_member_can_create_policy_and_recorder_is_injected(policy_client):
    client, product_id, _admin_id, member_id, _session = policy_client
    headers = auth(client, "policy_member", "member-password-123")
    month = current_business_month()
    response = create_policy(client, headers, product_id, month)
    assert response.status_code == 201, response.text
    assert response.json()["recorded_by"] == member_id
    assert response.json()["policy_price"] == "3699.00"


def test_policy_month_must_be_first_day_and_client_cannot_set_recorder(policy_client):
    client, product_id, _admin_id, _member_id, _session = policy_client
    headers = auth(client, "policy_member", "member-password-123")
    bad_month = create_policy(client, headers, product_id, date(2026, 11, 2))
    assert bad_month.status_code == 422
    injected = create_policy(client, headers, product_id, current_business_month(), recorded_by=1)
    assert injected.status_code == 422


def test_duplicate_active_policy_rejected_but_void_and_rerecord_allowed(policy_client):
    client, product_id, admin_id, _member_id, _session = policy_client
    headers = auth(client, "policy_admin", "admin-password-123")
    month = current_business_month()
    first = create_policy(client, headers, product_id, month)
    assert first.status_code == 201
    duplicate = create_policy(client, headers, product_id, month)
    assert duplicate.status_code == 409
    voided = client.patch(
        f"/api/policies/{first.json()['id']}/void",
        headers=headers,
        json={"reason": "政策价录入错误，重新登记"},
    )
    assert voided.status_code == 200
    replacement = create_policy(client, headers, product_id, month, policy_price="3599.00")
    assert replacement.status_code == 201
    all_rows = client.get("/api/policies", headers=headers, params={"month": month.isoformat(), "include_voided": True})
    assert all_rows.status_code == 200
    assert len(all_rows.json()) == 2
    assert next(row for row in all_rows.json() if row["id"] == first.json()["id"])["voided_by"] == admin_id


def test_admin_can_edit_current_month_but_member_cannot(policy_client):
    client, product_id, _admin_id, _member_id, _session = policy_client
    month = current_business_month()
    admin_headers = auth(client, "policy_admin", "admin-password-123")
    member_headers = auth(client, "policy_member", "member-password-123")
    created = create_policy(client, member_headers, product_id, month)
    record_id = created.json()["id"]

    denied = client.patch(f"/api/policies/{record_id}", headers=member_headers, json={"policy_price": "3500.00", "note": "改价"})
    assert denied.status_code == 403
    updated = client.patch(f"/api/policies/{record_id}", headers=admin_headers, json={"policy_price": "3500.00", "note": "当月调整"})
    assert updated.status_code == 200, updated.text
    assert updated.json()["policy_price"] == "3500.00"


def test_historical_month_policy_is_frozen_and_member_cannot_see_voided(policy_client):
    client, product_id, _admin_id, _member_id, _session = policy_client
    admin_headers = auth(client, "policy_admin", "admin-password-123")
    member_headers = auth(client, "policy_member", "member-password-123")
    month = previous_month(current_business_month())
    created = create_policy(client, admin_headers, product_id, month)
    assert created.status_code == 201, created.text
    frozen = client.patch(f"/api/policies/{created.json()['id']}", headers=admin_headers, json={"policy_price": "3400.00"})
    assert frozen.status_code == 409
    denied = client.get("/api/policies", headers=member_headers, params={"month": month.isoformat(), "include_voided": True})
    assert denied.status_code == 403
