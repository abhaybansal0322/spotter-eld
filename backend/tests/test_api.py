"""API contract tests."""


def test_health(api_client):
    response = api_client.get("/api/health/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
