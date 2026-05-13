from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

JobStatus = Literal["queued", "downloading", "downloaded", "uploading", "uploaded", "failed", "cancelled"]
PrivacyStatus = Literal["private", "unlisted", "public"]


class HealthOut(BaseModel):
    status: str


class AuthStatusOut(BaseModel):
    twitch: bool
    google: bool


class TwitchVodOut(BaseModel):
    id: str
    title: str
    url: str
    thumbnail_url: str | None = None
    created_at: str | None = None
    duration: str | None = None
    view_count: int | None = None
    uploader: str | None = None
    uploader_id: str | None = None
    game_name: str | None = None


class UploadJobCreate(BaseModel):
    twitch_vod_id: str = Field(min_length=1, max_length=128)
    twitch_url: str = Field(min_length=1)
    twitch_title: str = Field(min_length=1)
    youtube_title: str = Field(min_length=1, max_length=100)
    youtube_description: str = ""
    privacy_status: PrivacyStatus = "private"

    @field_validator("youtube_title", "twitch_title")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be blank")
        return value

    @field_validator("youtube_description")
    @classmethod
    def normalize_description(cls, value: str) -> str:
        return value.strip()


class UploadJobsCreate(BaseModel):
    jobs: list[UploadJobCreate] = Field(min_length=1, max_length=20)


class UploadJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    twitch_vod_id: str
    twitch_url: str
    twitch_title: str
    youtube_title: str
    youtube_description: str | None
    privacy_status: PrivacyStatus
    status: JobStatus
    progress: float
    local_file_path: str | None
    youtube_video_id: str | None
    youtube_url: str | None
    error_message: str | None
    retry_count: int
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
