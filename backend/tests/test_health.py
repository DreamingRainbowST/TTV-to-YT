import os

os.environ["DISABLE_WORKER"] = "true"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


def test_health() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_job_validation_and_persistence() -> None:
    payload = {
        "jobs": [
            {
                "twitch_vod_id": "123",
                "twitch_url": "https://www.twitch.tv/videos/123",
                "twitch_title": "Source VOD",
                "youtube_title": "YouTube title",
                "youtube_description": "Uploaded from local tool",
                "privacy_status": "private",
            }
        ]
    }
    with TestClient(app) as client:
        response = client.post("/api/jobs", json=payload)
        jobs_response = client.get("/api/jobs")

    assert response.status_code == 200
    assert response.json()[0]["status"] == "queued"
    assert jobs_response.status_code == 200
    assert jobs_response.json()[0]["youtube_title"] == "YouTube title"
