import mimetypes
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.auth import google as google_auth
from app.config import Settings
from app.models import UploadJob

UPLOAD_SESSION_URL = "https://www.googleapis.com/upload/youtube/v3/videos"
TRANSIENT_STATUS_CODES = {500, 502, 503, 504}
CHUNK_SIZE = 8 * 1024 * 1024


class YouTubeUploadError(RuntimeError):
    pass


def _response_excerpt(response: httpx.Response) -> str:
    return response.text[:1000] if response.text else response.reason_phrase


def _upload_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def _start_upload_session(
    client: httpx.Client,
    access_token: str,
    job: UploadJob,
    file_path: Path,
    content_type: str,
) -> str:
    metadata = {
        "snippet": {
            "title": job.youtube_title,
            "description": job.youtube_description or "",
            "categoryId": "22",
        },
        "status": {"privacyStatus": job.privacy_status},
    }
    response = client.post(
        UPLOAD_SESSION_URL,
        params={"uploadType": "resumable", "part": "snippet,status"},
        headers={
            **_upload_headers(access_token),
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Length": str(file_path.stat().st_size),
            "X-Upload-Content-Type": content_type,
        },
        json=metadata,
    )
    if response.status_code >= 400:
        raise YouTubeUploadError(f"YouTube upload session failed: {_response_excerpt(response)}")

    location = response.headers.get("Location")
    if not location:
        raise YouTubeUploadError("YouTube upload session did not return a Location header.")
    return location


def _put_chunk_with_retries(
    client: httpx.Client,
    upload_url: str,
    access_token: str,
    chunk: bytes,
    start: int,
    end: int,
    total_size: int,
) -> httpx.Response:
    headers = {
        **_upload_headers(access_token),
        "Content-Length": str(len(chunk)),
        "Content-Range": f"bytes {start}-{end}/{total_size}",
    }

    last_response: httpx.Response | None = None
    for attempt in range(4):
        response = client.put(upload_url, headers=headers, content=chunk)
        last_response = response
        if response.status_code not in TRANSIENT_STATUS_CODES:
            return response
        time.sleep(2**attempt)

    assert last_response is not None
    return last_response


def upload_video(
    db: Session,
    settings: Settings,
    job: UploadJob,
    progress_callback: Callable[[float], None] | None = None,
) -> tuple[str, str]:
    token = google_auth.get_valid_token(db, settings)
    file_path = Path(job.local_file_path or "")
    if not file_path.is_file():
        raise YouTubeUploadError("Downloaded video file is missing; retry the job to download it again.")

    total_size = file_path.stat().st_size
    content_type = mimetypes.guess_type(file_path.name)[0] or "video/*"
    timeout = httpx.Timeout(60.0, connect=30.0, read=None, write=None)

    with httpx.Client(timeout=timeout) as client:
        upload_url = _start_upload_session(client, token.access_token, job, file_path, content_type)

        uploaded = 0
        final_payload: dict[str, Any] | None = None
        with file_path.open("rb") as video_file:
            while uploaded < total_size:
                chunk = video_file.read(CHUNK_SIZE)
                if not chunk:
                    break
                start = uploaded
                end = uploaded + len(chunk) - 1
                response = _put_chunk_with_retries(
                    client,
                    upload_url,
                    token.access_token,
                    chunk,
                    start,
                    end,
                    total_size,
                )

                if response.status_code == 308:
                    uploaded = end + 1
                    if progress_callback:
                        progress_callback(uploaded / total_size * 100)
                    continue

                if response.status_code in (200, 201):
                    uploaded = total_size
                    final_payload = response.json()
                    if progress_callback:
                        progress_callback(100.0)
                    break

                raise YouTubeUploadError(f"YouTube upload failed: {_response_excerpt(response)}")

    if not final_payload or not final_payload.get("id"):
        raise YouTubeUploadError("YouTube upload completed without a video id in the response.")

    video_id = final_payload["id"]
    return video_id, f"https://www.youtube.com/watch?v={video_id}"

