from fastapi.testclient import TestClient


def test_root_health_no_db(api_client: TestClient):
    r = api_client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["service"] == "feedfoundry-api"
    assert "timestamp" in data


def test_ready_json_structure(api_client: TestClient):
    r = api_client.get("/ready")
    assert r.status_code in (200, 503)
    data = r.json()
    assert "ready" in data
    assert "checks" in data
    assert "database" in data["checks"]
    assert "r2" in data["checks"]
    assert "stripe" in data["checks"]


def test_version_endpoint(api_client: TestClient):
    r = api_client.get("/version")
    assert r.status_code == 200
    data = r.json()
    assert data["app_name"] == "feedfoundry"
    assert "app_env" in data
    assert "api_version" in data


def test_v1_health_still_available(api_client: TestClient):
    r = api_client.get("/v1/health")
    assert r.status_code == 200
    assert r.json()["service"] == "feedfoundry-api"
