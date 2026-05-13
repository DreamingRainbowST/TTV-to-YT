import os

os.environ["DISABLE_WORKER"] = "true"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from fastapi.testclient import TestClient  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import UploadJob, utcnow  # noqa: E402
from app.services.job_service import recover_interrupted_jobs  # noqa: E402


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
                "youtube_playlist_id": "PL123",
                "youtube_playlist_title": "Stream archive",
            }
        ]
    }
    with TestClient(app) as client:
        response = client.post("/api/jobs", json=payload)
        jobs_response = client.get("/api/jobs")

    assert response.status_code == 200
    assert response.json()[0]["status"] == "queued"
    assert response.json()[0]["youtube_playlist_id"] == "PL123"
    assert jobs_response.status_code == 200
    assert jobs_response.json()[0]["youtube_title"] == "YouTube title"


def test_recovers_interrupted_job_without_download(tmp_path) -> None:
    with TestClient(app):
        db = SessionLocal()
        try:
            job = UploadJob(
                twitch_vod_id="recover-1",
                twitch_url="https://www.twitch.tv/videos/456",
                twitch_title="Recover source",
                youtube_title="Recover target",
                youtube_description="",
                privacy_status="private",
                status="uploading",
                progress=81.0,
                youtube_upload_url="https://upload.example/session",
                created_at=utcnow(),
                updated_at=utcnow(),
            )
            db.add(job)
            db.commit()

            recovered = recover_interrupted_jobs(db, str(tmp_path))
            db.refresh(job)

            assert recovered >= 1
            assert job.status == "queued"
            assert job.progress == 0.0
            assert job.youtube_upload_url is None
        finally:
            db.close()
