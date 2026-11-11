import pytest
from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.audit_log import AuditLog
from app.models.policy_price import PolicyEvidence, PolicyPrice
from app.models.price_record import PriceRecord
from app.models.product import Product
from app.models.st_rebate import STRebate
from app.models.user import User


@pytest.fixture()
def delete_client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "policy_evidence_dir", str(tmp_path / "evidence"))
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
        admin = User(username="del_admin", password_hash=hash_password("admin-password-123"), role="admin")
        member = User(username="del_member", password_hash=hash_password("member-password-123"), role="member")
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


def _seed_product(client, admin_headers, with_policy=False):
    created = client.post("/api/products", headers=admin_headers, json={"brand": "华为", "model": "测试机型"})
    product_id = created.json()["id"]
    client.post(f"/api/products/{product_id}/variants", headers=admin_headers,
                json={"display_name": "8GB+128GB", "ram": "8GB", "storage": "128GB"})
    today = date.today().isoformat()
    client.post(f"/api/products/{product_id}/prices", headers=admin_headers,
                json={"variant": "8GB+128GB", "price_type": "基础价格", "price": "1333.00", "effective_date": today})
    client.post(f"/api/products/{product_id}/st-rebates", headers=admin_headers,
                json={"variant": "8GB+128GB", "amount": "100.00", "effective_date": today})
    policy = client.post("/api/policies", headers=admin_headers, json={
        "product_id": product_id, "variant": "8GB+128GB", "effective_date": today,
        "policy_price": "60.00", "interpretation": "本月渠道政策返利说明",
    })
    assert policy.status_code == 201, policy.text
    policy_id = policy.json()["id"]
    if with_policy:
        files = {"file": ("evidence.jpg", b"\xff\xd8\xff\x00testbytes", "image/jpeg")}
        uploaded = client.post(f"/api/policies/{policy_id}/evidence", headers=admin_headers, files=files)
        assert uploaded.status_code == 201, uploaded.text
    return product_id, policy_id


def test_member_cannot_delete_price(delete_client):
    client, Session = delete_client
    admin = _login(client, "del_admin", "admin-password-123")
    member = _login(client, "del_member", "member-password-123")
    _seed_product(client, admin)
    with Session() as db:
        record_id = int(db.scalar(select(PriceRecord.id).limit(1)))
    response = client.delete(f"/api/prices/{record_id}", headers=member)
    assert response.status_code == 403, response.text
    with Session() as db:
        assert db.get(PriceRecord, record_id) is not None


def test_admin_delete_price_writes_audit(delete_client):
    client, Session = delete_client
    admin = _login(client, "del_admin", "admin-password-123")
    _seed_product(client, admin)
    with Session() as db:
        record_id = int(db.scalar(select(PriceRecord.id).limit(1)))
    response = client.delete(f"/api/prices/{record_id}", headers=admin)
    assert response.status_code == 200, response.text
    assert response.json()["deleted"] is True
    with Session() as db:
        assert db.get(PriceRecord, record_id) is None
        actions = list(db.scalars(select(AuditLog.action)).all())
        assert "price.deleted" in actions


def test_admin_delete_st_rebate(delete_client):
    client, Session = delete_client
    admin = _login(client, "del_admin", "admin-password-123")
    _seed_product(client, admin)
    with Session() as db:
        record_id = int(db.scalar(select(STRebate.id).limit(1)))
    response = client.delete(f"/api/st-rebates/{record_id}", headers=admin)
    assert response.status_code == 200, response.text
    with Session() as db:
        assert db.get(STRebate, record_id) is None


def test_admin_delete_product_cascades(delete_client):
    client, Session = delete_client
    admin = _login(client, "del_admin", "admin-password-123")
    product_id, _ = _seed_product(client, admin)
    response = client.delete(f"/api/products/{product_id}", headers=admin)
    assert response.status_code == 200, response.text
    removed = response.json()["removed"]
    assert removed["price_records"] == 1
    assert removed["st_rebates"] == 1
    assert removed["policy_prices"] == 1
    with Session() as db:
        assert db.get(Product, product_id) is None
        assert db.scalar(select(PriceRecord).where(PriceRecord.product_id == product_id)) is None
        assert db.scalar(select(STRebate).where(STRebate.product_id == product_id)) is None
        assert db.scalar(select(PolicyPrice).where(PolicyPrice.product_id == product_id)) is None


def test_member_cannot_delete_product(delete_client):
    client, Session = delete_client
    admin = _login(client, "del_admin", "admin-password-123")
    member = _login(client, "del_member", "member-password-123")
    product_id, _ = _seed_product(client, admin)
    response = client.delete(f"/api/products/{product_id}", headers=member)
    assert response.status_code == 403, response.text
    with Session() as db:
        assert db.get(Product, product_id) is not None


def test_admin_delete_policy_removes_evidence_files(delete_client):
    client, Session = delete_client
    admin = _login(client, "del_admin", "admin-password-123")
    product_id, policy_id = _seed_product(client, admin, with_policy=True)
    response = client.delete(f"/api/policies/{policy_id}", headers=admin)
    assert response.status_code == 200, response.text
    assert response.json()["evidence_files_removed"] == 1
    with Session() as db:
        assert db.get(PolicyPrice, policy_id) is None
        assert db.scalar(select(PolicyEvidence)) is None
        evidence_dir = db.scalar(select(AuditLog.id).limit(1))
        assert evidence_dir is not None


def test_delete_missing_price_returns_404(delete_client):
    client, Session = delete_client
    admin = _login(client, "del_admin", "admin-password-123")
    response = client.delete("/api/prices/99999", headers=admin)
    assert response.status_code == 404


def test_product_list_shows_net_from(delete_client):
    client, Session = delete_client
    admin = _login(client, "del_admin", "admin-password-123")
    _seed_product(client, admin)
    rows = client.get("/api/products", headers=admin)
    assert rows.status_code == 200, rows.text
    row = rows.json()[0]
    assert float(row["net_from"]) == 1173.00
    assert float(row["current_policy_from"]) == 60.00



def test_admin_updates_product_info(delete_client):
    client, Session = delete_client
    admin = _login(client, "del_admin", "admin-password-123")
    product_id, _ = _seed_product(client, admin)
    response = client.patch(f"/api/products/{product_id}", headers=admin, json={
        "brand": "华为", "model": "测试机型 Pro", "tagline": "轻薄长续航",
        "intro": "官方直供", "selling_points": ["大电池", "快充"]})
    assert response.status_code == 200, response.text
    assert response.json()["model"] == "测试机型 Pro"
    assert response.json()["selling_points"] == ["大电池", "快充"]
    with Session() as db:
        assert "product.updated" in list(db.scalars(select(AuditLog.action)).all())


def test_member_cannot_edit_product(delete_client):
    client, Session = delete_client
    admin = _login(client, "del_admin", "admin-password-123")
    member = _login(client, "del_member", "member-password-123")
    product_id, _ = _seed_product(client, admin)
    response = client.patch(f"/api/products/{product_id}", headers=member, json={"model": "改"})
    assert response.status_code == 403, response.text


def test_admin_deactivates_variant(delete_client):
    client, Session = delete_client
    admin = _login(client, "del_admin", "admin-password-123")
    product_id, _ = _seed_product(client, admin)
    variant = client.get(f"/api/products/{product_id}/variants", headers=admin).json()[0]
    response = client.delete(f"/api/products/{product_id}/variants/{variant['id']}", headers=admin)
    assert response.status_code == 200, response.text
    remaining = client.get(f"/api/products/{product_id}/variants", headers=admin).json()
    assert all(v["id"] != variant["id"] for v in remaining)
    again = client.delete(f"/api/products/{product_id}/variants/{variant['id']}", headers=admin)
    assert again.status_code == 404
    recreate = client.post(f"/api/products/{product_id}/variants", headers=admin,
                           json={"display_name": variant["display_name"]})
    assert recreate.status_code == 201, recreate.text
    assert recreate.json()["is_active"] is True


def test_admin_deletes_color(delete_client):
    client, Session = delete_client
    admin = _login(client, "del_admin", "admin-password-123")
    product_id, _ = _seed_product(client, admin)
    color = client.post(f"/api/products/{product_id}/colors", headers=admin, json={"color_name": "星空黑"}).json()
    response = client.delete(f"/api/products/{product_id}/colors/{color['id']}", headers=admin)
    assert response.status_code == 200, response.text
    remaining = client.get(f"/api/products/{product_id}/colors", headers=admin).json()
    assert all(c["id"] != color["id"] for c in remaining)



def test_admin_sets_official_price(delete_client):
    client, Session = delete_client
    admin = _login(client, "del_admin", "admin-password-123")
    product_id, _ = _seed_product(client, admin)
    response = client.patch(f"/api/products/{product_id}", headers=admin, json={
        "official_price": "5999.00", "official_url": "https://www.vmall.com/product/100860.html"})
    assert response.status_code == 200, response.text
    assert float(response.json()["official_price"]) == 5999.00
    assert response.json()["official_price_updated_at"] is not None
    cleared = client.patch(f"/api/products/{product_id}", headers=admin, json={"official_price": None})
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["official_price"] is None


def test_create_product_with_official_price(delete_client):
    client, Session = delete_client
    member = _login(client, "del_member", "member-password-123")
    created = client.post("/api/products", headers=member, json={
        "brand": "华为", "model": "官网价机型", "official_price": "5999.00"})
    assert created.status_code == 201, created.text
    assert float(created.json()["official_price"]) == 5999.00
