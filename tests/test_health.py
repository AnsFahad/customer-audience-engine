from fastapi.testclient import TestClient
from fastapi import status
from unittest.mock import MagicMock
from src.main import app
from src.core.database import get_db


def test_health_check_success(client: TestClient):
    """Verifies that the /health endpoint returns 200 OK and connected database status."""
    response = client.get("/api/v1/health")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"
    assert "app_name" in data
    assert "environment" in data


def test_health_check_database_failure():
    """Verifies that /health returns 503 SERVICE UNAVAILABLE when database ping fails."""
    # Mock a broken database session
    mock_session = MagicMock()
    mock_session.execute.side_effect = Exception("Simulated DB connection timeout")

    def broken_get_db():
        try:
            yield mock_session
        finally:
            pass

    app.dependency_overrides[get_db] = broken_get_db

    with TestClient(app) as client:
        response = client.get("/api/v1/health")
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        data = response.json()
        assert data["detail"]["status"] == "degraded"
        assert data["detail"]["database"] == "unreachable"

    app.dependency_overrides.clear()
