from fastapi.testclient import TestClient

from app.main import app


def test_root_serves_single_page_frontend():
    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "手机报价档案系统" in response.text
    assert 'id="login-form"' in response.text
