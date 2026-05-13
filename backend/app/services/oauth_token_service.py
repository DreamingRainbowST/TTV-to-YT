from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models import OAuthToken


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def get_token(db: Session, provider: str) -> OAuthToken | None:
    return db.query(OAuthToken).filter(OAuthToken.provider == provider).one_or_none()


def token_is_expiring(token: OAuthToken, leeway_seconds: int = 90) -> bool:
    if not token.expires_at:
        return False

    expires_at = token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= utcnow() + timedelta(seconds=leeway_seconds)


def upsert_token(db: Session, provider: str, payload: dict[str, Any], scope: str | None = None) -> OAuthToken:
    token = get_token(db, provider)
    now = utcnow()
    expires_in = payload.get("expires_in")
    expires_at = now + timedelta(seconds=int(expires_in)) if expires_in else None

    if token is None:
        token = OAuthToken(provider=provider, access_token=payload["access_token"], created_at=now)
        db.add(token)

    token.access_token = payload["access_token"]
    token.refresh_token = payload.get("refresh_token") or token.refresh_token
    token.token_type = payload.get("token_type") or token.token_type
    token.scope = payload.get("scope") or scope or token.scope
    token.expires_at = expires_at
    token.updated_at = now
    db.commit()
    db.refresh(token)
    return token

