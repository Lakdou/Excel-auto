import pytest
from fastapi.testclient import TestClient

from app import __version__, main


@pytest.fixture()
def client():
    return TestClient(main.app)


def test_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200 and res.json() == {"status": "ok", "version": __version__}


def test_config(client):
    cfg = client.get("/api/config").json()
    assert ".xlsm" in cfg["extensions"] and cfg["max_upload_mb"] == main.MAX_UPLOAD_MB


def test_index_and_assets_served(client):
    res = client.get("/")
    assert res.status_code == 200 and "Excel Auto" in res.text
    assert client.get("/app.js").status_code == 200
    assert client.get("/styles.css").status_code == 200


def test_security_headers(client):
    res = client.get("/")
    assert "frame-ancestors 'none'" in res.headers["content-security-policy"]
    assert res.headers["x-content-type-options"] == "nosniff"


def test_analyze_ok(client, complex_bytes):
    res = client.post("/api/analyze", files={"file": ("suivi.xlsm", complex_bytes, "application/octet-stream")})
    assert res.status_code == 200
    body = res.json()
    assert body["file"]["name"] == "suivi.xlsm"
    assert body["summary"]["sheets"] == 5


def test_path_in_filename_is_stripped(client, simple_bytes):
    res = client.post("/api/analyze", files={"file": ("../../etc/planning.xlsx", simple_bytes)})
    assert res.json()["file"]["name"] == "planning.xlsx"


def test_analyze_invalid_file(client):
    res = client.post("/api/analyze", files={"file": ("notes.txt", b"hello")})
    assert res.status_code == 422
    assert "non prise en charge" in res.json()["detail"]


def test_analyze_too_large(client, monkeypatch, simple_bytes):
    monkeypatch.setattr(main, "MAX_UPLOAD_BYTES", 100)
    res = client.post("/api/analyze", files={"file": ("planning.xlsx", simple_bytes)})
    assert res.status_code == 413


def test_unexpected_error_is_hidden(client, monkeypatch, simple_bytes):
    def boom(*_):
        raise RuntimeError("détail interne secret")

    monkeypatch.setattr(main, "analyze_bytes", boom)
    res = client.post("/api/analyze", files={"file": ("planning.xlsx", simple_bytes)})
    assert res.status_code == 500
    assert "secret" not in res.text


def test_missing_file(client):
    assert client.post("/api/analyze").status_code == 422


def test_docs_have_their_own_csp(client):
    res = client.get("/docs")
    assert res.status_code == 200
    assert "cdn.jsdelivr.net" in res.headers["content-security-policy"]
    # L'application garde la politique stricte, sans script inline.
    assert "unsafe-inline" not in client.get("/").headers["content-security-policy"]
