from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_base_url: str = "http://localhost:8000"
    frontend_base_url: str = "http://localhost:5173"
    database_url: str = "sqlite:///./app.db"
    download_dir: str = "/downloads"

    twitch_client_id: str = ""
    twitch_client_secret: str = ""
    twitch_redirect_uri: str = "http://localhost:8000/auth/twitch/callback"

    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/auth/google/callback"

    youtube_default_privacy_status: Literal["private", "unlisted", "public"] = "private"
    disable_worker: bool = Field(default=False, validation_alias="DISABLE_WORKER")


@lru_cache
def get_settings() -> Settings:
    return Settings()

