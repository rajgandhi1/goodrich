from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Any

from app.config import get_settings


SESSION_TTL_SECONDS = 7 * 24 * 60 * 60


@dataclass(frozen=True)
class SessionClaims:
    org_id: str
    user_id: str
    exp: int


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + ("=" * (-len(value) % 4)))


def _sign(payload: str) -> str:
    secret = get_settings().auth_secret.encode("utf-8")
    return _b64encode(hmac.new(secret, payload.encode("ascii"), hashlib.sha256).digest())


def create_session_token(org_id: str, user_id: str, ttl_seconds: int = SESSION_TTL_SECONDS) -> str:
    claims = {
        "org_id": org_id,
        "user_id": user_id,
        "exp": int(time.time()) + ttl_seconds,
    }
    payload = _b64encode(json.dumps(claims, separators=(",", ":")).encode("utf-8"))
    return f"{payload}.{_sign(payload)}"


def verify_session_token(token: str | None) -> SessionClaims | None:
    if not token or "." not in token:
        return None
    payload, signature = token.split(".", 1)
    if not hmac.compare_digest(signature, _sign(payload)):
        return None
    try:
        data = json.loads(_b64decode(payload)) if payload else {}
    except (ValueError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    exp = int(data.get("exp") or 0)
    if exp < int(time.time()):
        return None
    org_id = str(data.get("org_id") or "").strip()
    user_id = str(data.get("user_id") or "").strip()
    if not org_id or not user_id:
        return None
    return SessionClaims(org_id=org_id, user_id=user_id, exp=exp)


def session_cookie_params() -> dict[str, Any]:
    secure = get_settings().environment.lower() in {"prod", "production"}
    return {
        "key": get_settings().auth_cookie_name,
        "httponly": True,
        "secure": secure,
        "samesite": "lax",
        "path": "/",
        "max_age": SESSION_TTL_SECONDS,
    }
