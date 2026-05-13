from datetime import datetime
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.auth import twitch as twitch_auth
from app.config import Settings
from app.models import TwitchVod, utcnow
from app.schemas import TwitchVodOut

HELIX_VIDEOS_URL = "https://api.twitch.tv/helix/videos"


class TwitchServiceError(RuntimeError):
    pass


def _parse_twitch_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _thumbnail_url(value: str | None) -> str | None:
    if not value:
        return None
    return value.replace("%{width}", "320").replace("%{height}", "180")


def _to_vod_out(raw: dict[str, Any]) -> TwitchVodOut:
    return TwitchVodOut(
        id=raw["id"],
        title=raw.get("title", ""),
        url=raw.get("url", ""),
        thumbnail_url=_thumbnail_url(raw.get("thumbnail_url")),
        created_at=raw.get("created_at"),
        duration=raw.get("duration"),
    )


def fetch_latest_vods(db: Session, settings: Settings, limit: int = 20) -> list[TwitchVodOut]:
    token = twitch_auth.get_valid_token(db, settings)

    try:
        validation = twitch_auth.validate_token(token.access_token)
    except twitch_auth.TwitchAuthError:
        token = twitch_auth.refresh_token(db, settings, token)
        validation = twitch_auth.validate_token(token.access_token)

    user_id = validation.get("user_id")
    if not user_id:
        raise TwitchServiceError("Could not resolve Twitch user id from OAuth token.")

    headers = {
        "Authorization": f"Bearer {token.access_token}",
        "Client-Id": settings.twitch_client_id,
    }
    params = {"user_id": user_id, "type": "archive", "first": min(limit, 20)}
    with httpx.Client(timeout=30) as client:
        response = client.get(HELIX_VIDEOS_URL, headers=headers, params=params)

    if response.status_code >= 400:
        raise TwitchServiceError(f"Twitch VOD fetch failed: {response.text[:500]}")

    vods: list[TwitchVodOut] = []
    for raw in response.json().get("data", []):
        vod_out = _to_vod_out(raw)
        vods.append(vod_out)
        existing = db.query(TwitchVod).filter(TwitchVod.twitch_id == vod_out.id).one_or_none()
        if existing is None:
            existing = TwitchVod(twitch_id=vod_out.id, title=vod_out.title, url=vod_out.url)
            db.add(existing)

        existing.title = vod_out.title
        existing.url = vod_out.url
        existing.thumbnail_url = vod_out.thumbnail_url
        existing.duration = vod_out.duration
        existing.vod_created_at = _parse_twitch_datetime(vod_out.created_at)
        existing.fetched_at = utcnow()

    db.commit()
    return vods

