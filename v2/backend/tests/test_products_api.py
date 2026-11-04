import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.audit_log import AuditLog
from app.models.price_record import PriceRecord
from app.models.product import Product
from app.models.user import User


@pytest.fixture()
def product_client():
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
        admin = User(username="product_admin", password_hash=hash_password("admin-password-123"), role="admin")
        member = User(username="product_member", password_hash=hash_password("member-password-123"), role="member")
        db.add_all([admin, member])
        db.commit()

    with TestClient(app) as test_client:
        yield test_client, TestingSession

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def _login(client, username, password):
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_member_can_create_and_list_product(product_client):
    client, _ = product_client
    headers = _login(client, "product_member", "member-password-123")

    created = client.post(
        "/api/products",
        headers=headers,
        json={"brand": "华为", "model": "Mate X", "intro": "折叠屏"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["brand"] == "华为"
    listed = client.get("/api/products", headers=headers)
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [created.json()["id"]]


def test_admin_archive_preserves_price_history_and_restore(product_client):
    client, sessions = product_client
    admin_headers = _login(client, "product_admin", "admin-password-123")
    member_headers = _login(client, "product_member", "member-password-123")

    created = client.post(
        "/api/products",
        headers=member_headers,
        json={"brand": "华为", "model": "Pura Test"},
    )
    product_id = created.json()["id"]

    with sessions() as db:
        member = db.scalar(select(User).where(User.username == "product_member"))
        db.add(PriceRecord(
            product_id=product_id,
            variant="12+256",
            price_type="批发价",
            price="3999.00",
            effective_date="2026-11-04",
            recorded_by=member.id,
        ))
        db.commit()

    archived = client.patch(
        f"/api/products/{product_id}/archive",
        headers=admin_headers,
        json={"reason": "产品停止销售"},
    )
    assert archived.status_code == 200, archived.text
    assert archived.json()["price_history_count"] == 1
    assert client.get("/api/products", headers=member_headers).json() == []

    restored = client.post(f"/api/products/{product_id}/restore", headers=admin_headers)
    assert restored.status_code == 200
    assert restored.json()["restored"] is True
    assert len(client.get("/api/products", headers=member_headers).json()) == 1

    with sessions() as db:
        assert db.scalar(select(PriceRecord).where(PriceRecord.product_id == product_id)) is not None
        actions = list(db.scalars(select(AuditLog.action).where(AuditLog.target_id == str(product_id))).all())
        assert "product.archived" in actions
        assert "product.restored" in actions


def test_member_archive_is_forbidden_and_audited(product_client):
    client, sessions = product_client
    member_headers = _login(client, "product_member", "member-password-123")
    created = client.post(
        "/api/products",
        headers=member_headers,
        json={"brand": "荣耀", "model": "Magic Test"},
    )
    product_id = created.json()["id"]

    response = client.patch(
        f"/api/products/{product_id}/archive",
        headers=member_headers,
        json={"reason": "不再销售"},
    )
    assert response.status_code == 403
    with sessions() as db:
        denied = db.scalar(select(AuditLog).where(
            AuditLog.action == "denied",
            AuditLog.target_id == f"/api/products/{product_id}/archive",
        ))
        assert denied is not None


@pytest.mark.parametrize("reason", ["     ", "太短"])
def test_archive_rejects_blank_or_short_reason(product_client, reason):
    client, _ = product_client
    admin_headers = _login(client, "product_admin", "admin-password-123")
    created = client.post(
        "/api/products",
        headers=admin_headers,
        json={"brand": "小米", "model": "Test"},
    )
    response = client.patch(
        f"/api/products/{created.json()['id']}/archive",
        headers=admin_headers,
        json={"reason": reason},
    )
    assert response.status_code == 422
