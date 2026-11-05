from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.models.user import User


def test_product_variants_are_admin_managed_and_member_readable():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    sessions = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = sessions()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with sessions() as db:
        db.add_all([
            User(username="variant_admin", password_hash=hash_password("admin-password-123"), role="admin"),
            User(username="variant_member", password_hash=hash_password("member-password-123"), role="member"),
        ])
        product = Product(brand="华为", model="配置测试机")
        db.add(product)
        db.commit()
        product_id = product.id

    def login(client, username, password):
        response = client.post("/api/auth/login", json={"username": username, "password": password})
        assert response.status_code == 200, response.text
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    try:
        with TestClient(app) as client:
            admin = login(client, "variant_admin", "admin-password-123")
            member = login(client, "variant_member", "member-password-123")

            created = client.post(
                f"/api/products/{product_id}/variants",
                headers=admin,
                json={"display_name": "12GB + 256GB", "ram": "12GB", "storage": "256GB"},
            )
            assert created.status_code == 201, created.text
            assert created.json()["display_name"] == "12GB + 256GB"

            listed = client.get(f"/api/products/{product_id}/variants", headers=member)
            assert listed.status_code == 200
            assert [row["display_name"] for row in listed.json()] == ["12GB + 256GB"]

            denied = client.post(
                f"/api/products/{product_id}/variants",
                headers=member,
                json={"display_name": "16GB + 512GB"},
            )
            assert denied.status_code == 403

            duplicate = client.post(
                f"/api/products/{product_id}/variants",
                headers=admin,
                json={"display_name": "12GB + 256GB"},
            )
            assert duplicate.status_code == 409

        with sessions() as db:
            rows = list(db.scalars(select(ProductVariant).where(ProductVariant.product_id == product_id)).all())
            assert len(rows) == 1
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
