from __future__ import annotations

from dataclasses import dataclass

from fastapi import Header, HTTPException, Request, status

from app.auth_session import verify_session_token
from app.config import get_settings


@dataclass(frozen=True)
class CurrentUser:
    org_id: str
    user_id: str
    role: str = "sales"
    name: str = ""


def get_current_user(
    request: Request,
    x_org_id: str | None = Header(default=None, alias="X-Org-Id"),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    x_user_name: str | None = Header(default=None, alias="X-User-Name"),
) -> CurrentUser:
    settings = get_settings()
    claims = verify_session_token(request.cookies.get(settings.auth_cookie_name))
    header_fallback_allowed = settings.environment.lower() not in {"prod", "production"}
    if claims:
        org_id = claims.org_id
        user_id = claims.user_id
    elif header_fallback_allowed:
        org_id = (x_org_id or "local-org").strip() or "local-org"
        user_id = (x_user_id or "local-user").strip() or "local-user"
    else:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    role = "sales"
    name = ""
    try:
        from app.db import repo

        user_key = user_id.lower()
        app_user = next(
            (
                row
                for row in repo.list_app_users(org_id)
                if row.active and (row.id.lower() == user_key or row.email.lower() == user_key)
            ),
            None,
        )
        if app_user:
            role = app_user.role
            name = app_user.name
        elif not header_fallback_allowed:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    except Exception:
        if not header_fallback_allowed:
            raise
        # Keep request handling available even if the user store is temporarily unavailable.
        role = "sales"
    return CurrentUser(
        org_id=org_id,
        user_id=user_id,
        role=role,
        name=name or (x_user_name or "").strip(),
    )


def can_approve(user: CurrentUser) -> bool:
    return user.role in {"admin", "approver"} or can_role(user, "approve_quotes")


def can_manage_users(user: CurrentUser) -> bool:
    return user.role == "admin" or can_role(user, "manage_users")


def can_role(user: CurrentUser, capability: str) -> bool:
    if user.role == "admin":
        return True
    try:
        from app.db import repo

        settings = repo.get_access_settings(user.org_id)
        return bool(settings.role_permissions.get(user.role, {}).get(capability))
    except Exception:
        return False


def require_capability(user: CurrentUser, capability: str) -> None:
    if not can_role(user, capability):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission for this action")
