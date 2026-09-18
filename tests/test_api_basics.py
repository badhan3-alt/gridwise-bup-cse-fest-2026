from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_bad_request_is_controlled():
    response = client.post("/optimize-energy", json={"scenario_id": "bad"})
    assert response.status_code == 400
    body = response.json()
    assert body["detail"] == "Invalid request structure"
