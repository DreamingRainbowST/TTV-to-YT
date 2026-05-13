import logging
from contextlib import asynccontextmanager
from urllib.parse import urlencode

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.auth import google as google_auth
from app.auth import twitch as twitch_auth
from app.auth.state import consume_state
from app.config import get_settings
from app.database import get_db, init_db
from app.schemas import AuthStatusOut, HealthOut, TwitchVodOut, UploadJobOut, UploadJobsCreate
from app.services import job_service, twitch_service
from app.services.downloader_service import TwitchPublicFetchError, fetch_public_vods
from app.services.oauth_token_service import get_token
from app.worker import JobWorker

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
settings = get_settings()
worker: JobWorker | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global worker
    init_db()
    if not settings.disable_worker:
        worker = JobWorker(settings)
        worker.start()
    yield
    if worker is not None:
        worker.stop()


app = FastAPI(title="Twitch VOD to YouTube Uploader", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_base_url],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


def _redirect_with_status(provider: str, status: str, message: str | None = None) -> RedirectResponse:
    query = {"provider": provider, "status": status}
    if message:
        query["message"] = message[:300]
    return RedirectResponse(f"{settings.frontend_base_url}/?{urlencode(query)}")


@app.get("/health", response_model=HealthOut)
def health() -> HealthOut:
    return HealthOut(status="ok")


@app.get("/auth/twitch/login")
def twitch_login() -> RedirectResponse:
    try:
        return RedirectResponse(twitch_auth.build_login_url(settings))
    except twitch_auth.TwitchAuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/auth/twitch/callback")
def twitch_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    if error:
        return _redirect_with_status("twitch", "error", error)
    if not code or not consume_state(state, "twitch"):
        return _redirect_with_status("twitch", "error", "Invalid or expired Twitch OAuth state.")

    try:
        twitch_auth.exchange_code(db, settings, code)
    except twitch_auth.TwitchAuthError as exc:
        return _redirect_with_status("twitch", "error", str(exc))
    return _redirect_with_status("twitch", "connected")


@app.get("/auth/google/login")
def google_login() -> RedirectResponse:
    try:
        return RedirectResponse(google_auth.build_login_url(settings))
    except google_auth.GoogleAuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/auth/google/callback")
def google_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    if error:
        return _redirect_with_status("google", "error", error)
    if not code or not consume_state(state, "google"):
        return _redirect_with_status("google", "error", "Invalid or expired Google OAuth state.")

    try:
        google_auth.exchange_code(db, settings, code)
    except google_auth.GoogleAuthError as exc:
        return _redirect_with_status("google", "error", str(exc))
    return _redirect_with_status("google", "connected")


@app.get("/api/auth/status", response_model=AuthStatusOut)
def auth_status(db: Session = Depends(get_db)) -> AuthStatusOut:
    return AuthStatusOut(twitch=get_token(db, "twitch") is not None, google=get_token(db, "google") is not None)


@app.get("/api/vods", response_model=list[TwitchVodOut])
def get_vods(
    channel: str | None = Query(default=None, min_length=3, max_length=25),
    db: Session = Depends(get_db),
) -> list[TwitchVodOut]:
    if channel:
        try:
            return fetch_public_vods(channel, limit=20)
        except TwitchPublicFetchError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    try:
        return twitch_service.fetch_latest_vods(db, settings, limit=20)
    except twitch_auth.TwitchAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except twitch_service.TwitchServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/jobs", response_model=list[UploadJobOut])
def create_jobs(payload: UploadJobsCreate, db: Session = Depends(get_db)) -> list[UploadJobOut]:
    return job_service.create_jobs(db, payload)


@app.get("/api/jobs", response_model=list[UploadJobOut])
def list_jobs(db: Session = Depends(get_db)) -> list[UploadJobOut]:
    return job_service.list_jobs(db)


@app.get("/api/jobs/{job_id}", response_model=UploadJobOut)
def get_job(job_id: int, db: Session = Depends(get_db)) -> UploadJobOut:
    job = job_service.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job


@app.post("/api/jobs/{job_id}/retry", response_model=UploadJobOut)
def retry_job(job_id: int, db: Session = Depends(get_db)) -> UploadJobOut:
    job = job_service.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job.status != "failed":
        raise HTTPException(status_code=409, detail="Only failed jobs can be retried.")
    return job_service.retry_job(db, job)


@app.post("/api/jobs/{job_id}/cancel", response_model=UploadJobOut)
def cancel_job(job_id: int, db: Session = Depends(get_db)) -> UploadJobOut:
    job = job_service.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job.status != "queued":
        raise HTTPException(status_code=409, detail="Only queued jobs can be cancelled in the MVP.")
    return job_service.cancel_job(db, job)
