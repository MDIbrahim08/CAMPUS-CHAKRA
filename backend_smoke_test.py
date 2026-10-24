from fastapi.testclient import TestClient
from pathlib import Path

from backend.app import app


with TestClient(app) as client:
    dataset_dir = Path(__file__).parent.parent / "P2P_DATASET"
    dashboard = client.get("/api/dashboard")
    assert dashboard.status_code == 200

    classification = client.post(
        "/api/classify",
        json={
            "weight_g": 180,
            "moisture_pct": 72,
            "metal_signal": 0.1,
            "transparency": 0.2,
            "acoustic_hardness": 0.3,
            "building_id": "B05",
            "timestamp": "2026-10-17T12:00:00",
        },
    )
    assert classification.status_code == 200
    assert classification.json()["predicted_class"]

    with (dataset_dir / "waste_events_test.xlsx").open("rb") as upload:
        waste_evaluation = client.post(
            "/api/evaluate/waste",
            files={"file": ("waste_events_test.xlsx", upload, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
    assert waste_evaluation.status_code == 200
    assert waste_evaluation.json()["rows"] == 1601

    with (dataset_dir / "hourly_streams.xlsx").open("rb") as upload:
        hourly_evaluation = client.post(
            "/api/evaluate/hourly",
            files={"file": ("hourly_streams.xlsx", upload, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
    assert hourly_evaluation.status_code == 200
    assert hourly_evaluation.json()["forecast"]

    with (dataset_dir / "manual_logs.xlsx").open("rb") as upload:
        manual_evaluation = client.post(
            "/api/evaluate/manual",
            files={"file": ("manual_logs.xlsx", upload, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
    assert manual_evaluation.status_code == 200
    assert manual_evaluation.json()["resolved_pct"] == 100.0

    packet = {
        "gateway_id": "smoke-gateway",
        "readings": [
            {
                "building_id": "B05",
                "timestamp": "2026-10-17T12:00:00",
                "seq": 1,
                "electricity_kwh": 12.5,
                "water_litres": 180,
            }
        ],
    }
    assert client.post("/api/gateway/sync", json=packet).status_code == 200
    duplicate = client.post("/api/gateway/sync", json=packet)
    assert duplicate.status_code == 200
    assert duplicate.json()["duplicates"] == 1

    llm_status = client.get("/api/llm/status")
    assert llm_status.status_code == 200

print("backend smoke test: passed")
