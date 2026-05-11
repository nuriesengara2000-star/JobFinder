from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_root_endpoint_returns_running_status():
    response = client.get("/")

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "JobFinder AI Agent"
    assert payload["status"] == "running"
    assert payload["health"] == "/health"
    assert payload["docs"] == "/docs"


def test_health_endpoint_returns_ok():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "job-ai-agent"}


def test_chat_rejects_too_short_resume():
    response = client.post("/chat", json={"resume_text": "short"})

    assert response.status_code == 422


def test_chat_rejects_empty_resume():
    response = client.post("/chat", json={"resume_text": ""})

    assert response.status_code == 422
