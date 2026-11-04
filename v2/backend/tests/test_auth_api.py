import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.core.security import hash_password
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
        db.add_all([
            User(username="admin_user", password_hash=hash_password("admin-password-123"), role="admin"),
            User(username="member_user", password_hash=hash_password("member-password-123"), role="member"),
        ])
        db.commit()

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def login(client, username, password):
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_member_can_change_own_password_and_old_token_is_revoked(client):
    old_headers = login(client, "member_user", "member-password-123")
    changed = client.post(
        "/api/auth/password",
        headers=old_headers,
        json={"old_password": "member-password-123", "new_password": "member-password-456"},
    )
    assert changed.status_code == 200
    assert client.get("/api/auth/me", headers=old_headers).status_code == 401
    new_headers = login(client, "member_user", "member-password-456")
    assert client.get("/api/auth/me", headers=new_headers).status_code == 200


def test_admin_can_create_reset_disable_and_enable_member(client):
    admin_headers = login(client, "admin_user", "admin-password-123")
    created = client.post(
        "/api/auth/users",
        headers=admin_headers,
        json={"username": "new_member", "password": "initial-password-123", "role": "member"},
    )
    assert created.status_code == 201, created.text
    user_id = created.json()["id"]
    old_member_headers = login(client, "new_member", "initial-password-123")

    reset = client.post(
        f"/api/auth/users/{user_id}/reset-password",
        headers=admin_headers,
        json={"new_password": "reset-password-123"},
    )
    assert reset.status_code == 200
    assert client.get("/api/auth/me", headers=old_member_headers).status_code == 401
    new_member_headers = login(client, "new_member", "reset-password-123")

    disabled = client.patch(
        f"/api/auth/users/{user_id}/status",
        headers=admin_headers,
        json={"is_active": False},
    )
    assert disabled.status_code == 200
    assert client.get("/api/auth/me", headers=new_member_headers).status_code == 401
    assert client.post(
        "/api/auth/login",
        json={"username": "new_member", "password": "reset-password-123"},
    ).status_code == 401

    enabled = client.patch(
        f"/api/auth/users/{user_id}/status",
        headers=admin_headers,
        json={"is_active": True},
    )
    assert enabled.status_code == 200
    assert client.post(
        "/api/auth/login",
        json={"username": "new_member", "password": "reset-password-123"},
    ).status_code == 200


def test_member_cannot_access_admin_user_management(client):
    member_headers = login(client, "member_user", "member-password-123")
    assert client.get("/api/auth/users", headers=member_headers).status_code == 403


def test_admin_cannot_disable_own_account(client):
    admin_headers = login(client, "admin_user", "admin-password-123")
    response = client.patch(
        "/api/auth/users/1/status",
        headers=admin_headers,
        json={"is_active": False},
    )
    assert response.status_code == 400
    assert "当前登录" in response.json()["detail"]


def test_user_creation_rejects_unknown_role_and_extra_fields(client):
    admin_headers = login(client, "admin_user", "admin-password-123")
    invalid_role = client.post(
        "/api/auth/users",
        headers=admin_headers,
        json={"username": "bad_role", "password": "initial-password-123", "role": "superuser"},
    )
    assert invalid_role.status_code == 422

    extra_field = client.post(
        "/api/auth/users",
        headers=admin_headers,
        json={"username": "extra_field", "password": "initial-password-123", "role": "member", "is_active": False},
    )
    assert extra_field.status_code == 422


def test_member_cannot_submit_extra_auth_fields(client):
    response = client.post(
        "/api/auth/login",
        json={"username": "member_user", "password": "member-password-123", "role": "admin"},
    )
    assert response.status_code == 422


def test_member_denial_is_audited_and_audit_endpoint_is_admin_only(client):
    member_headers = login(client, "member_user", "member-password-123")
    denied = client.get("/api/auth/users", headers=member_headers)
    assert denied.status_code == 403

    member_audit = client.get("/api/auth/audit-logs", headers=member_headers)
    assert member_audit.status_code == 403

    admin_headers = login(client, "admin_user", "admin-password-123")
    logs = client.get("/api/auth/audit-logs?limit=10&offset=0", headers=admin_headers)
    assert logs.status_code == 200
    denied_entries = [item for item in logs.json() if item["action"] == "denied"]
    assert any(item["target_type"] == "http" and item["target_id"] == "/api/auth/users" for item in denied_entries)


def test_audit_log_pagination_validation(client):
    admin_headers = login(client, "admin_user", "admin-password-123")
    assert client.get("/api/auth/audit-logs?limit=0", headers=admin_headers).status_code == 422
    assert client.get("/api/auth/audit-logs?limit=501", headers=admin_headers).status_code == 422
    assert client.get("/api/auth/audit-logs?offset=-1", headers=admin_headers).status_code == 422


def test_member_list_does_not_expose_password_hash(client):
    admin_headers = login(client, "admin_user", "admin-password-123")
    response = client.get("/api/auth/users", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()
    assert all("password_hash" not in user for user in response.json())
