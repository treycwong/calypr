from calypr_api.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_health_ok():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["service"] == "calypr-api"


def test_readyz_responds():
    # 200 when the DB is reachable, 503 when not — both valid (DB-less CI unit runs).
    r = client.get("/readyz")
    assert r.status_code in (200, 503)
    assert "status" in r.json()
