from fastapi.testclient import TestClient

from backend.app import app


with TestClient(app) as client:
    status = client.get("/api/llm/status")
    assert status.status_code == 200
    assert status.json()["providers"], "No LLM provider keys are configured"

    response = client.post(
        "/api/copilot",
        json={"building_id": "B06", "question": "Summarise the highest-priority action using only the supplied evidence."},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["final"]
    assert payload["trace"]

    weather = client.get("/api/weather/live")
    assert weather.status_code == 200

print("live services test: passed")
