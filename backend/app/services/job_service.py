from datetime import timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import UploadJob, utcnow
from app.schemas import UploadJobsCreate


def create_jobs(db: Session, payload: UploadJobsCreate) -> list[UploadJob]:
    jobs: list[UploadJob] = []
    now = utcnow()
    for item in payload.jobs:
        job = UploadJob(
            twitch_vod_id=item.twitch_vod_id,
            twitch_url=item.twitch_url,
            twitch_title=item.twitch_title,
            youtube_title=item.youtube_title,
            youtube_description=item.youtube_description,
            privacy_status=item.privacy_status,
            status="queued",
            progress=0.0,
            created_at=now,
            updated_at=now,
        )
        db.add(job)
        jobs.append(job)

    db.commit()
    for job in jobs:
        db.refresh(job)
    return jobs


def list_jobs(db: Session) -> list[UploadJob]:
    return db.query(UploadJob).order_by(UploadJob.created_at.desc()).all()


def get_job(db: Session, job_id: int) -> UploadJob | None:
    return db.get(UploadJob, job_id)


def retry_job(db: Session, job: UploadJob) -> UploadJob:
    job.status = "queued"
    job.progress = 0.0
    job.error_message = None
    job.youtube_video_id = None
    job.youtube_url = None
    job.started_at = None
    job.finished_at = None
    job.updated_at = utcnow()
    db.commit()
    db.refresh(job)
    return job


def cancel_job(db: Session, job: UploadJob) -> UploadJob:
    job.status = "cancelled"
    job.progress = 0.0
    job.finished_at = utcnow()
    job.updated_at = utcnow()
    db.commit()
    db.refresh(job)
    return job


def safe_delete_download(file_path: str | None, download_dir: str) -> None:
    if not file_path:
        return

    target = Path(file_path).resolve()
    allowed_root = Path(download_dir).resolve()
    if allowed_root not in target.parents and target != allowed_root:
        return
    if target.is_file():
        target.unlink()


def serialize_datetime(value):
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value

