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


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
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
        admin = User(username="price_admin", password_hash=hash_password("admin-password-123"), role="admin")
        member = User(username="price_member", password_hash=hash_password("member-password-123"), role="member")
        db.add_all([admin, member])
        db.flush()
        product = Product(brand="华为", model="测试机")
        db.add(product)
        db.commit()
        product_id = product.id
        admin_id = admin.id
        member_id = member.id

    with TestClient(app) as test_client:
        yield test_client, product_id, admin_id, member_id, TestingSession

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def login(client, username, password):
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_price(client, headers, product_id, **overrides):
    payload = {
        "variant": "12+256G",
        "price_type": "purchase",
        "price": "3999.00",
        "effective_date": "2026-11-01",
        "note": "测试价格",
    }
    payload.update(overrides)
    return client.post(f"/api/products/{product_id}/prices", headers=headers, json=payload)


def test_member_can_create_price_and_recorder_is_injected(client):
    client, product_id, _admin_id, member_id, _TestingSession = client
    headers = login(client, "price_member", "member-password-123")
    response = create_price(client, headers, product_id)
    assert response.status_code == 201, response.text
    assert response.json()["recorded_by"] == member_id
    assert response.json()["price"] == "3999.00"


def test_client_cannot_supply_recorded_by(client):
    client, product_id, _admin_id, _member_id, _TestingSession = client
    headers = login(client, "price_member", "member-password-123")
    response = create_price(client, headers, product_id, recorded_by=999)
    assert response.status_code == 422


def test_price_value_has_no_update_or_delete_endpoint(client):
    client, product_id, _admin_id, _member_id, _TestingSession = client
    headers = login(client, "price_member", "member-password-123")
    created = create_price(client, headers, product_id)
    record_id = created.json()["id"]
    assert client.put(f"/api/prices/{record_id}", headers=headers, json={"price": "1.00"}).status_code == 405
    assert client.patch(f"/api/prices/{record_id}", headers=headers, json={"price": "1.00"}).status_code == 405
    assert client.delete(f"/api/prices/{record_id}", headers=headers).status_code == 405


def test_member_cannot_include_voided_records_and_attempt_is_audited(client):
    client, product_id, _admin_id, member_id, TestingSession = client
    headers = login(client, "price_member", "member-password-123")
    response = client.get(
        f"/api/products/{product_id}/prices",
        headers=headers,
        params={"include_voided": "true"},
    )
    assert response.status_code == 403
    # The route commits the denial audit before returning 403.
    with TestingSession() as db:
        denied = db.query(AuditLog).filter_by(actor_id=member_id, action="denied").all()
        assert len(denied) == 1
        assert denied[0].detail == {"operation": "include_voided"}


def test_admin_void_requires_reason_and_preserves_original_record(client):
    client, product_id, admin_id, _member_id, _TestingSession = client
    admin_headers = login(client, "price_admin", "admin-password-123")
    created = create_price(client, admin_headers, product_id)
    record_id = created.json()["id"]

    short_reason = client.patch(
        f"/api/prices/{record_id}/void",
        headers=admin_headers,
        params={"reason": "错误"},
    )
    assert short_reason.status_code == 422

    voided = client.patch(
        f"/api/prices/{record_id}/void",
        headers=admin_headers,
        params={"reason": "录入价格错误，按流程作废"},
    )
    assert voided.status_code == 200

    # The default query excludes voided records; admin can explicitly inspect them.
    assert client.get(f"/api/products/{product_id}/prices", headers=admin_headers).json() == []
    all_records = client.get(
        f"/api/products/{product_id}/prices",
        headers=admin_headers,
        params={"include_voided": "true"},
    )
    assert all_records.status_code == 200
    assert len(all_records.json()) == 1
    record = all_records.json()[0]
    assert record["price"] == "3999.00"
    assert record["voided_by"] == admin_id
    assert record["voided_at"] is not None
    assert record["void_reason"] == "录入价格错误，按流程作废"


def test_date_range_and_as_of_filters(client):
    client, product_id, _admin_id, _member_id, _TestingSession = client
    headers = login(client, "price_member", "member-password-123")
    first = create_price(client, headers, product_id, effective_date="2026-10-31", price="3800.00")
    second = create_price(client, headers, product_id, effective_date="2026-11-02", price="3900.00")
    assert first.status_code == 201
    assert second.status_code == 201

    ranged = client.get(
        f"/api/products/{product_id}/prices",
        headers=headers,
        params={"start": "2026-11-01", "end": "2026-11-30"},
    )
    assert [item["price"] for item in ranged.json()] == ["3900.00"]

    as_of = client.get(
        f"/api/products/{product_id}/prices",
        headers=headers,
        params={"as_of": "2026-10-31"},
    )
    assert [item["price"] for item in as_of.json()] == ["3800.00"]
