from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_endpoint_returns_service_status() -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "personal-media-ops-api",
        "version": "0.1.0",
    }


def test_cors_does_not_allow_unspecified_origins() -> None:
    response = client.get(
        "/api/health",
        headers={"Origin": "https://unconfigured.example.com"},
    )

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
