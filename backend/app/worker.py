import logging
import threading
import time
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import Settings
from app.database import SessionLocal
from app.models import UploadJob, utcnow
from app.services.downloader_service import download_vod
from app.services.job_service import safe_delete_download
from app.services.youtube_service import YouTubePlaylistError, add_video_to_playlist, upload_video

logger = logging.getLogger(__name__)


class JobWorker:
    def __init__(self, settings: Settings, poll_seconds: float = 3.0) -> None:
        self.settings = settings
        self.poll_seconds = poll_seconds
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, name="job-worker", daemon=True)

    def start(self) -> None:
        if not self._thread.is_alive():
            self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread.is_alive():
            self._thread.join(timeout=10)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                processed = self._process_next_job()
                if not processed:
                    self._stop_event.wait(self.poll_seconds)
            except Exception:
                logger.exception("Unexpected worker error")
                self._stop_event.wait(self.poll_seconds)

    def _process_next_job(self) -> bool:
        db = SessionLocal()
        try:
            job = (
                db.query(UploadJob)
                .filter(UploadJob.status == "queued")
                .order_by(UploadJob.created_at.asc())
                .first()
            )
            if job is None:
                return False

            self._process_job(db, job)
            return True
        finally:
            db.close()

    def _set_progress(self, db: Session, job: UploadJob, status: str, progress: float) -> None:
        job.status = status
        job.progress = max(0.0, min(100.0, progress))
        job.updated_at = utcnow()
        db.commit()

    def _process_job(self, db: Session, job: UploadJob) -> None:
        logger.info("Processing upload job %s", job.id)
        job.started_at = utcnow()
        job.finished_at = None
        job.error_message = None
        job.updated_at = utcnow()
        db.commit()

        try:
            local_file = Path(job.local_file_path) if job.local_file_path else None
            if not local_file or not local_file.is_file():
                self._set_progress(db, job, "downloading", 5.0)

                def download_progress(percent: float) -> None:
                    self._set_progress(db, job, "downloading", 5.0 + percent * 0.65)

                downloaded_path = download_vod(
                    job.id,
                    job.twitch_url,
                    self.settings.download_dir,
                    progress_callback=download_progress,
                )
                job.local_file_path = downloaded_path

            if job.youtube_video_id:
                video_id = job.youtube_video_id
                video_url = job.youtube_url or f"https://www.youtube.com/watch?v={video_id}"
                self._set_progress(db, job, "uploading", 99.0)
            else:
                self._set_progress(db, job, "downloaded", 72.0)
                self._set_progress(db, job, "uploading", 75.0)

                def upload_progress(percent: float) -> None:
                    self._set_progress(db, job, "uploading", 75.0 + percent * 0.24)

                video_id, video_url = upload_video(db, self.settings, job, progress_callback=upload_progress)
                job.youtube_video_id = video_id
                job.youtube_url = video_url

            playlist_warning: str | None = None
            if job.youtube_playlist_id and not job.youtube_playlist_item_id:
                try:
                    job.youtube_playlist_item_id = add_video_to_playlist(
                        db,
                        self.settings,
                        job.youtube_playlist_id,
                        video_id,
                    )
                except YouTubePlaylistError as playlist_error:
                    playlist_name = job.youtube_playlist_title or job.youtube_playlist_id
                    playlist_warning = f"Upload succeeded, but adding to playlist {playlist_name} failed: {playlist_error}"

            job.status = "uploaded"
            job.progress = 100.0
            job.error_message = playlist_warning
            job.finished_at = utcnow()
            job.updated_at = utcnow()
            db.commit()
            if job.local_file_path:
                try:
                    safe_delete_download(job.local_file_path, self.settings.download_dir)
                    job.local_file_path = None
                    job.updated_at = utcnow()
                    db.commit()
                except Exception as cleanup_error:
                    logger.warning("Upload job %s completed but cleanup failed: %s", job.id, cleanup_error)
                    cleanup_warning = f"Upload succeeded, but cleanup failed: {cleanup_error}"
                    job.error_message = f"{playlist_warning}\n{cleanup_warning}" if playlist_warning else cleanup_warning
                    job.updated_at = utcnow()
                    db.commit()
            logger.info("Upload job %s completed with YouTube video %s", job.id, video_id)
        except Exception as exc:
            logger.exception("Upload job %s failed", job.id)
            job.status = "failed"
            job.error_message = str(exc)[:4000]
            job.retry_count += 1
            job.finished_at = utcnow()
            job.updated_at = utcnow()
            db.commit()
