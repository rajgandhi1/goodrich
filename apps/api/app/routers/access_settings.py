from fastapi import APIRouter, Depends, HTTPException, status

from app.db import repo
from app.deps import CurrentUser, can_manage_users, get_current_user
from app.schemas.access_settings import AccessSettings, AccessSettingsPatch

router = APIRouter(prefix="/api/v1", tags=["access-settings"])


def _require_admin(user: CurrentUser) -> None:
    if not can_manage_users(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admin users can manage access settings")


@router.get("/access-settings", response_model=AccessSettings)
def get_access_settings(user: CurrentUser = Depends(get_current_user)) -> AccessSettings:
    return repo.get_access_settings(user.org_id)


@router.put("/access-settings", response_model=AccessSettings)
def update_access_settings(payload: AccessSettingsPatch, user: CurrentUser = Depends(get_current_user)) -> AccessSettings:
    _require_admin(user)
    current = repo.get_access_settings(user.org_id)
    return repo.update_access_settings(user.org_id, payload.as_settings(current))
