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


@pytest.fixture()
def client():
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
        admin = User(username="st_admin", password_hash=hash_password("admin-password-123"), role="admin")
        member = User(username="st_member", password_hash=hash_password("member-password-123"), role="member")
        db.add_all([admin, member])
        db.flush()
        product = Product(brand="华为", model="ST测试机")
        db.add(product)
        db.commit()
        ids = (product.id, admin.id, member.id)
    with TestClient(app) as test_client:
        yield test_client, *ids
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def auth(client, username, password):
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def test_optional_st_rebate_can_be_absent_and_added_when_needed(client):
    client, product_id, _admin_id, member_id = client
    headers = auth(client, "st_member", "member-password-123")
    assert client.get(f"/api/products/{product_id}/st-rebates", headers=headers).json() == []
    response = client.post(f"/api/products/{product_id}/st-rebates", headers=headers, json={
        "variant": "12+256G", "amount": "300.00", "effective_date": "2026-11-01", "note": "长期ST返利"
    })
    assert response.status_code == 201, response.text
    assert response.json()["amount"] == "300.00"
    assert response.json()["recorded_by"] == member_id


def test_st_rebate_history_appends_and_admin_can_void(client):
    client, product_id, admin_id, _member_id = client
    member_headers = auth(client, "st_member", "member-password-123")
    admin_headers = auth(client, "st_admin", "admin-password-123")
    first = client.post(f"/api/products/{product_id}/st-rebates", headers=member_headers, json={
        "variant": "12+256G", "amount": "300.00", "effective_date": "2026-11-01"
    })
    second = client.post(f"/api/products/{product_id}/st-rebates", headers=member_headers, json={
        "variant": "12+256G", "amount": "250.00", "effective_date": "2026-12-01"
    })
    assert first.status_code == second.status_code == 201
    rows = client.get(f"/api/products/{product_id}/st-rebates", headers=member_headers).json()
    assert [r["amount"] for r in rows] == ["250.00", "300.00"]
    assert client.patch(f"/api/st-rebates/{second.json()['id']}/void", headers=admin_headers, params={"reason": "返利政策录入错误"}).status_code == 200
    assert client.get(f"/api/products/{product_id}/st-rebates", headers=member_headers).json()[0]["amount"] == "300.00"
    assert admin_id > 0
