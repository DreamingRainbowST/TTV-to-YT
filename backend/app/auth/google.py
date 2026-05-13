from urllib.parse import urlencode

import httpx
from sqlalchemy.orm import Session

from app.auth.state import create_state
from app.config import Settings
from app.models import OAuthToken
from app.services.oauth_token_service import get_token, token_is_expiring, upsert_token

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]
YOUTUBE_SCOPE = " ".join(YOUTUBE_SCOPES)


class GoogleAuthError(RuntimeError):
    pass


def ensure_configured(settings: Settings) -> None:
    if not settings.google_client_id or not settings.google_client_secret:
        raise GoogleAuthError("Google OAuth credentials are missing. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.")


def build_login_url(settings: Settings) -> str:
    ensure_configured(settings)
    state = create_state("google")
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": YOUTUBE_SCOPE,
        "state": state,
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
    }
    return f"{AUTH_URL}?{urlencode(params)}"


def exchange_code(db: Session, settings: Settings, code: str) -> OAuthToken:
    ensure_configured(settings)
    with httpx.Client(timeout=20) as client:
        response = client.post(
            TOKEN_URL,
            data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": settings.google_redirect_uri,
            },
        )
    if response.status_code >= 400:
        raise GoogleAuthError(f"Google token exchange failed: {response.text[:500]}")
    return upsert_token(db, "google", response.json(), scope=YOUTUBE_SCOPE)


def refresh_token(db: Session, settings: Settings, token: OAuthToken) -> OAuthToken:
    ensure_configured(settings)
    if not token.refresh_token:
        raise GoogleAuthError("Google access token expired and no refresh token is available. Reconnect Google.")

    with httpx.Client(timeout=20) as client:
        response = client.post(
            TOKEN_URL,
            data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "grant_type": "refresh_token",
                "refresh_token": token.refresh_token,
            },
        )
    if response.status_code >= 400:
        raise GoogleAuthError("Google token refresh failed. Reconnect Google/YouTube.")
    return upsert_token(db, "google", response.json(), scope=YOUTUBE_SCOPE)


def get_valid_token(db: Session, settings: Settings) -> OAuthToken:
    token = get_token(db, "google")
    if token is None:
        raise GoogleAuthError("Google/YouTube is not connected. Start the Google OAuth flow first.")
    if token_is_expiring(token):
        token = refresh_token(db, settings, token)
    return token
