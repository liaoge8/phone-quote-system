from pathlib import Path


def test_root_serves_single_page_frontend(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "手机报价档案系统" in response.text
    assert 'id="login-form"' in response.text
