import hashlib
import io
import tarfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.user import User
from app.routers import backups


@pytest.fixture()
def backup_client(tmp_path, monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(backups, "BACKUP_DIR", tmp_path)
    with testing_session() as db:
        admin = User(username="backup_admin", password_hash=hash_password("admin-password-123"), role="admin")
        member = User(username="backup_member", password_hash=hash_password("member-password-123"), role="member")
        db.add_all([admin, member])
        db.commit()

    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def headers_for(client, username, password):
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def make_backup_package():
    payloads = {
        "database.dump": b"test-database-dump",
        "policy-evidence.tar.gz": b"test-evidence-archive",
        "manifest.txt": b"format=phone-quote-backup-v1\ncreated_at_utc=20261105T010000Z\n",
    }
    sums = "".join(f"{hashlib.sha256(data).hexdigest()}  {name}\n" for name, data in payloads.items())
    payloads["SHA256SUMS"] = sums.encode()
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w:gz") as archive:
        for name, data in payloads.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    return stream.getvalue()


def test_backup_management_is_admin_only(backup_client):
    member = headers_for(backup_client, "backup_member", "member-password-123")
    assert backup_client.get("/api/backups", headers=member).status_code == 403
    assert backup_client.post("/api/backups/upload", headers=member,
                              files={"file": ("backup.tar.gz", make_backup_package(), "application/gzip")}).status_code == 403


def test_admin_can_upload_validate_list_and_download_backup(backup_client):
    admin = headers_for(backup_client, "backup_admin", "admin-password-123")
    response = backup_client.post("/api/backups/upload", headers=admin,
                                  files={"file": ("backup.tar.gz", make_backup_package(), "application/gzip")})
    assert response.status_code == 201, response.text
    item = response.json()
    assert item["filename"].startswith("phone-quote-upload-")
    assert item["created_at"] == "20261105T010000Z"
    rows = backup_client.get("/api/backups", headers=admin)
    assert rows.status_code == 200
    assert len(rows.json()) == 1
    downloaded = backup_client.get(f"/api/backups/{item['filename']}/download", headers=admin)
    assert downloaded.status_code == 200
    assert downloaded.content.startswith(b"\x1f\x8b")


def test_admin_upload_rejects_invalid_backup(backup_client):
    admin = headers_for(backup_client, "backup_admin", "admin-password-123")
    response = backup_client.post("/api/backups/upload", headers=admin,
                                  files={"file": ("bad.tar.gz", b"not a gzip archive", "application/gzip")})
    assert response.status_code == 422
