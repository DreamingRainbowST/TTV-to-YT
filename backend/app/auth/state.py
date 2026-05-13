from datetime import datetime, timedelta, timezone
from secrets import token_urlsafe

_STATE_TTL = timedelta(minutes=10)
# Local MVP only: in production this should live in a signed/encrypted server-side
# session store instead of process memory.
_states: dict[str, tuple[str, datetime]] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_state(provider: str) -> str:
    cleanup_states()
    state = token_urlsafe(32)
    _states[state] = (provider, _now() + _STATE_TTL)
    return state


def consume_state(state: str | None, provider: str) -> bool:
    if not state:
        return False

    cleanup_states()
    stored = _states.pop(state, None)
    if not stored:
        return False

    stored_provider, expires_at = stored
    return stored_provider == provider and expires_at > _now()


def cleanup_states() -> None:
    now = _now()
    expired = [state for state, (_, expires_at) in _states.items() if expires_at <= now]
    for state in expired:
        _states.pop(state, None)
