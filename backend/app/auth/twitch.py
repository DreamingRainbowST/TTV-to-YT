from typing import Any
from urllib.parse import urlencode

import httpx
from sqlalchemy.orm import Session

from app.auth.state import create_state
from app.config import Settings
from app.models import OAuthToken
from app.services.oauth_token_service import get_token, token_is_expiring, upsert_token

AUTH_URL = "https://id.twitch.tv/oauth2/authorize"
TOKEN_URL = "https://id.twitch.tv/oauth2/token"
VALIDATE_URL = "https://id.twitch.tv/oauth2/validate"


class TwitchAuthError(RuntimeError):
    pass


def ensure_configured(settings: Settings) -> None:
    if not settings.twitch_client_id or not settings.twitch_client_secret:
        raise TwitchAuthError("Twitch OAuth credentials are missing. Set TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET.")


def build_login_url(settings: Settings) -> str:
    ensure_configured(settings)
    state = create_state("twitch")
    params = {
        "client_id": settings.twitch_client_id,
        "redirect_uri": settings.twitch_redirect_uri,
        "response_type": "code",
        "state": state,
        "scope": "",
    }
    return f"{AUTH_URL}?{urlencode(params)}"


def exchange_code(db: Session, settings: Settings, code: str) -> OAuthToken:
    ensure_configured(settings)
    with httpx.Client(timeout=20) as client:
        response = client.post(
            TOKEN_URL,
            data={
                "client_id": settings.twitch_client_id,
                "client_secret": settings.twitch_client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": settings.twitch_redirect_uri,
            },
        )
    if response.status_code >= 400:
        raise TwitchAuthError(f"Twitch token exchange failed: {response.text[:500]}")
    return upsert_token(db, "twitch", response.json())


def refresh_token(db: Session, settings: Settings, token: OAuthToken) -> OAuthToken:
    ensure_configured(settings)
    if not token.refresh_token:
        raise TwitchAuthError("Twitch access token expired and no refresh token is available. Reconnect Twitch.")

    with httpx.Client(timeout=20) as client:
        response = client.post(
            TOKEN_URL,
            data={
                "client_id": settings.twitch_client_id,
                "client_secret": settings.twitch_client_secret,
                "grant_type": "refresh_token",
                "refresh_token": token.refresh_token,
            },
        )
    if response.status_code >= 400:
        raise TwitchAuthError("Twitch token refresh failed. Reconnect Twitch.")
    return upsert_token(db, "twitch", response.json())


def get_valid_token(db: Session, settings: Settings) -> OAuthToken:
    token = get_token(db, "twitch")
    if token is None:
        raise TwitchAuthError("Twitch is not connected. Start the Twitch OAuth flow first.")
    if token_is_expiring(token):
        token = refresh_token(db, settings, token)
    return token


def validate_token(access_token: str) -> dict[str, Any]:
    with httpx.Client(timeout=20) as client:
        response = client.get(VALIDATE_URL, headers={"Authorization": f"OAuth {access_token}"})
    if response.status_code >= 400:
        raise TwitchAuthError("Twitch token validation failed. Reconnect Twitch.")
    return response.json()

