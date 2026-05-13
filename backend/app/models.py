from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class OAuthToken(Base):
    __tablename__ = "oauth_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    provider: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    # Local-only MVP storage. Production use should encrypt these values at rest.
    access_token: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    token_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    scope: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class TwitchVod(Base):
    __tablename__ = "twitch_vods"
    __table_args__ = (UniqueConstraint("twitch_id", name="uq_twitch_vods_twitch_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    twitch_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    thumbnail_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duration: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    vod_created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class UploadJob(Base):
    __tablename__ = "upload_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    twitch_vod_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    twitch_url: Mapped[str] = mapped_column(Text, nullable=False)
    twitch_title: Mapped[str] = mapped_column(Text, nullable=False)
    youtube_title: Mapped[str] = mapped_column(Text, nullable=False)
    youtube_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    privacy_status: Mapped[str] = mapped_column(String(16), nullable=False, default="private")
    status: Mapped[str] = mapped_column(String(32), index=True, nullable=False, default="queued")
    progress: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    local_file_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    youtube_upload_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    youtube_video_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    youtube_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    youtube_playlist_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    youtube_playlist_title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    youtube_playlist_item_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
