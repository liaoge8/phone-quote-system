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
from app.models.product_color import ProductColor
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

            color = client.post(
                f"/api/products/{product_id}/colors",
                headers=admin,
                json={"color_name": "曜金黑"},
            )
            assert color.status_code == 201, color.text
            color_list = client.get(f"/api/products/{product_id}/colors", headers=member)
            assert [row["color_name"] for row in color_list.json()] == ["曜金黑"]
            duplicate_color = client.post(
                f"/api/products/{product_id}/colors",
                headers=admin,
                json={"color_name": "曜金黑"},
            )
            assert duplicate_color.status_code == 409

            product_card = client.get("/api/products", headers=member)
            assert product_card.status_code == 200
            assert product_card.json()[0]["variants_count"] == 1
            assert product_card.json()[0]["colors_count"] == 1
            variant_id = created.json()["id"]

            base_price = client.post(
                f"/api/products/{product_id}/prices",
                headers=member,
                json={"variant": "12GB + 256GB", "price_type": "基础价格", "price": "2999.00", "effective_date": "2026-11-05"},
            )
            assert base_price.status_code == 201, base_price.text
            assert base_price.json()["variant_id"] == variant_id

            rebate = client.post(
                f"/api/products/{product_id}/st-rebates",
                headers=member,
                json={"variant": "12GB + 256GB", "amount": "100.00", "effective_date": "2026-11-05"},
            )
            assert rebate.status_code == 201, rebate.text
            assert rebate.json()["variant_id"] == variant_id

            policy = client.post(
                "/api/policies",
                headers=member,
                json={"product_id": product_id, "variant": "12GB + 256GB", "effective_date": "2026-11-05", "policy_price": "2799.00", "interpretation": "测试政策内容和适用范围"},
            )
            assert policy.status_code == 201, policy.text
            assert policy.json()["variant_id"] == variant_id

            listed = client.get(f"/api/products/{product_id}/variants", headers=member)
            assert listed.status_code == 200
            assert [row["display_name"] for row in listed.json()] == ["12GB + 256GB"]

            unknown_price = client.post(
                f"/api/products/{product_id}/prices",
                headers=member,
                json={"variant": "16GB + 512GB", "price_type": "基础价格", "price": "3999.00", "effective_date": "2026-11-05"},
            )
            assert unknown_price.status_code == 422

            unknown_rebate = client.post(
                f"/api/products/{product_id}/st-rebates",
                headers=member,
                json={"variant": "16GB + 512GB", "amount": "100.00", "effective_date": "2026-11-05"},
            )
            assert unknown_rebate.status_code == 422

            unknown_policy = client.post(
                "/api/policies",
                headers=member,
                json={"product_id": product_id, "variant": "16GB + 512GB", "effective_date": "2026-11-05", "policy_price": "2799.00", "interpretation": "测试政策内容和适用范围"},
            )
            assert unknown_policy.status_code == 422

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
