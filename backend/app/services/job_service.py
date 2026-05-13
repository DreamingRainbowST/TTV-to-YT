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
            youtube_playlist_id=item.youtube_playlist_id,
            youtube_playlist_title=item.youtube_playlist_title,
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


def _find_existing_download(job_id: int, download_dir: str) -> str | None:
    target_dir = Path(download_dir)
    if not target_dir.is_dir():
        return None

    candidates = [
        path
        for path in target_dir.glob(f"job-{job_id}-*")
        if path.is_file() and not path.name.endswith((".part", ".ytdl"))
    ]
    if not candidates:
        return None
    return str(max(candidates, key=lambda path: path.stat().st_mtime))


def recover_interrupted_jobs(db: Session, download_dir: str) -> int:
    jobs = (
        db.query(UploadJob)
        .filter(UploadJob.status.in_(("downloading", "downloaded", "uploading")))
        .order_by(UploadJob.created_at.asc())
        .all()
    )
    recovered = 0

    for job in jobs:
        local_file = Path(job.local_file_path) if job.local_file_path else None
        existing_download = (
            str(local_file)
            if local_file and local_file.is_file()
            else _find_existing_download(job.id, download_dir)
        )

        if existing_download:
            job.local_file_path = existing_download
            job.progress = max(job.progress, 75.0)
            job.error_message = None
        else:
            job.local_file_path = None
            job.youtube_upload_url = None
            job.progress = 0.0
            job.error_message = "Recovered after interruption; download will restart."

        job.status = "queued"
        job.started_at = None
        job.finished_at = None
        job.updated_at = utcnow()
        recovered += 1

    if recovered:
        db.commit()
    return recovered


def retry_job(db: Session, job: UploadJob) -> UploadJob:
    job.status = "queued"
    job.progress = 0.0
    job.error_message = None
    if not job.youtube_video_id:
        job.youtube_url = None
        local_file = Path(job.local_file_path) if job.local_file_path else None
        if not local_file or not local_file.is_file():
            job.youtube_upload_url = None
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
