from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os
from urllib.parse import urlparse

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer


@dataclass(frozen=True)
class SessionConfig:
    secret_key: str
    max_age_seconds: int
    cookie_name: str
    secure_cookies: bool
    same_site: str


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_max_age_seconds() -> int:
    value = os.getenv("SESSION_MAX_AGE_DAYS", "30")
    try:
        days = int(value)
    except ValueError as exc:
        raise ValueError("SESSION_MAX_AGE_DAYS must be an integer") from exc
    if days <= 0:
        raise ValueError("SESSION_MAX_AGE_DAYS must be a positive integer")
    return days * 24 * 60 * 60


@lru_cache(maxsize=1)
def get_session_config() -> SessionConfig:
    secret_key = os.getenv("TOGETHER_SECRET_KEY")
    if not secret_key:
        raise RuntimeError(
            "TOGETHER_SECRET_KEY is required. Generate one with: "
            'python -c "import secrets; print(secrets.token_hex(32))"'
        )
    if len(secret_key) < 32:
        raise RuntimeError("TOGETHER_SECRET_KEY must be at least 32 characters")

    return SessionConfig(
        secret_key=secret_key,
        max_age_seconds=_get_max_age_seconds(),
        cookie_name="session",
        secure_cookies=_parse_bool(os.getenv("TOGETHER_SECURE_COOKIES"), True),
        same_site="lax",
    )


def _get_serializer(config: SessionConfig) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(config.secret_key, salt="together.session")


def create_session_cookie(user_id: int, config: SessionConfig) -> str:
    serializer = _get_serializer(config)
    return serializer.dumps({"user_id": user_id})


def parse_session_cookie(cookie: str, config: SessionConfig) -> int | None:
    serializer = _get_serializer(config)
    try:
        data = serializer.loads(cookie, max_age=config.max_age_seconds)
    except BadSignature, SignatureExpired:
        return None
    user_id = data.get("user_id")
    if not isinstance(user_id, int):
        return None
    return user_id


def is_safe_redirect(url: str | None) -> bool:
    """Allow only same-site relative redirects rooted at `/`."""
    if not url:
        return False
    parsed = urlparse(url)
    return not parsed.scheme and not parsed.netloc and parsed.path.startswith("/")


def normalize_next_url(url: str | None) -> str:
    """Return a validated post-login redirect target, defaulting to `/`."""
    if is_safe_redirect(url):
        return url
    return "/"
