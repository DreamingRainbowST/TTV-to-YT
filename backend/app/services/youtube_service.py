import mimetypes
import re
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.auth import google as google_auth
from app.config import Settings
from app.models import UploadJob
from app.schemas import YouTubePlaylistOut

UPLOAD_SESSION_URL = "https://www.googleapis.com/upload/youtube/v3/videos"
PLAYLISTS_URL = "https://www.googleapis.com/youtube/v3/playlists"
PLAYLIST_ITEMS_URL = "https://www.googleapis.com/youtube/v3/playlistItems"
TRANSIENT_STATUS_CODES = {500, 502, 503, 504}
CHUNK_SIZE = 8 * 1024 * 1024
RANGE_RE = re.compile(r"bytes=0-(\d+)")


class YouTubeUploadError(RuntimeError):
    pass


class YouTubePlaylistError(RuntimeError):
    pass


class UploadSessionExpired(RuntimeError):
    pass


def _response_excerpt(response: httpx.Response) -> str:
    return response.text[:1000] if response.text else response.reason_phrase


def _upload_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def _uploaded_bytes_from_range(range_header: str | None, fallback: int = 0) -> int:
    if not range_header:
        return fallback
    match = RANGE_RE.fullmatch(range_header.strip())
    if not match:
        return fallback
    return int(match.group(1)) + 1


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


def _query_upload_session(
    client: httpx.Client,
    upload_url: str,
    access_token: str,
    total_size: int,
) -> tuple[int, dict[str, Any] | None]:
    response = client.put(
        upload_url,
        headers={
            **_upload_headers(access_token),
            "Content-Length": "0",
            "Content-Range": f"bytes */{total_size}",
        },
        content=b"",
    )
    if response.status_code == 308:
        return _uploaded_bytes_from_range(response.headers.get("Range")), None
    if response.status_code in (200, 201):
        return total_size, response.json()
    if response.status_code == 404:
        raise UploadSessionExpired("YouTube resumable upload session expired.")
    raise YouTubeUploadError(f"YouTube upload status check failed: {_response_excerpt(response)}")


def _put_chunk_with_retries(
    client: httpx.Client,
    upload_url: str,
    access_token: str,
    content_type: str,
    chunk: bytes,
    start: int,
    end: int,
    total_size: int,
) -> httpx.Response:
    headers = {
        **_upload_headers(access_token),
        "Content-Length": str(len(chunk)),
        "Content-Type": content_type,
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


def list_playlists(db: Session, settings: Settings) -> list[YouTubePlaylistOut]:
    token = google_auth.get_valid_token(db, settings)
    playlists: list[YouTubePlaylistOut] = []
    page_token: str | None = None

    with httpx.Client(timeout=30) as client:
        while True:
            response = client.get(
                PLAYLISTS_URL,
                params={
                    "part": "snippet,contentDetails,status",
                    "mine": "true",
                    "maxResults": "50",
                    **({"pageToken": page_token} if page_token else {}),
                },
                headers=_upload_headers(token.access_token),
            )
            if response.status_code >= 400:
                raise YouTubePlaylistError(
                    "Could not load YouTube playlists. Reconnect Google to grant playlist access, "
                    f"then try again: {_response_excerpt(response)}"
                )

            payload = response.json()
            for item in payload.get("items", []):
                snippet = item.get("snippet") or {}
                status = item.get("status") or {}
                content_details = item.get("contentDetails") or {}
                playlist_id = item.get("id")
                title = snippet.get("title")
                if not playlist_id or not title:
                    continue
                playlists.append(
                    YouTubePlaylistOut(
                        id=playlist_id,
                        title=title,
                        description=snippet.get("description") or None,
                        privacy_status=status.get("privacyStatus"),
                        item_count=content_details.get("itemCount"),
                    )
                )

            page_token = payload.get("nextPageToken")
            if not page_token:
                return playlists


def add_video_to_playlist(db: Session, settings: Settings, playlist_id: str, video_id: str) -> str:
    token = google_auth.get_valid_token(db, settings)
    with httpx.Client(timeout=30) as client:
        response = client.post(
            PLAYLIST_ITEMS_URL,
            params={"part": "snippet"},
            headers={**_upload_headers(token.access_token), "Content-Type": "application/json; charset=UTF-8"},
            json={
                "snippet": {
                    "playlistId": playlist_id,
                    "resourceId": {"kind": "youtube#video", "videoId": video_id},
                }
            },
        )

    if response.status_code >= 400:
        raise YouTubePlaylistError(f"Could not add video to playlist: {_response_excerpt(response)}")

    playlist_item_id = response.json().get("id")
    if not playlist_item_id:
        raise YouTubePlaylistError("YouTube added the video to the playlist but returned no playlist item id.")
    return playlist_item_id


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
        upload_url = job.youtube_upload_url
        final_payload: dict[str, Any] | None = None

        for _ in range(2):
            uploaded = 0
            if upload_url:
                try:
                    uploaded, final_payload = _query_upload_session(
                        client,
                        upload_url,
                        token.access_token,
                        total_size,
                    )
                    if progress_callback:
                        progress_callback(uploaded / total_size * 100)
                    if final_payload:
                        break
                except UploadSessionExpired:
                    job.youtube_upload_url = None
                    db.commit()
                    upload_url = None

            if not upload_url:
                upload_url = _start_upload_session(client, token.access_token, job, file_path, content_type)
                job.youtube_upload_url = upload_url
                db.commit()

            try:
                with file_path.open("rb") as video_file:
                    video_file.seek(uploaded)
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
                            content_type,
                            chunk,
                            start,
                            end,
                            total_size,
                        )

                        if response.status_code == 308:
                            uploaded = _uploaded_bytes_from_range(response.headers.get("Range"), end + 1)
                            if progress_callback:
                                progress_callback(uploaded / total_size * 100)
                            continue

                        if response.status_code in (200, 201):
                            uploaded = total_size
                            final_payload = response.json()
                            if progress_callback:
                                progress_callback(100.0)
                            break

                        if response.status_code == 404:
                            raise UploadSessionExpired("YouTube resumable upload session expired.")

                        raise YouTubeUploadError(f"YouTube upload failed: {_response_excerpt(response)}")
            except UploadSessionExpired:
                job.youtube_upload_url = None
                db.commit()
                upload_url = None
                final_payload = None
                continue

            break

    if not final_payload or not final_payload.get("id"):
        raise YouTubeUploadError("YouTube upload completed without a video id in the response.")

    video_id = final_payload["id"]
    job.youtube_upload_url = None
    db.commit()
    return video_id, f"https://www.youtube.com/watch?v={video_id}"
