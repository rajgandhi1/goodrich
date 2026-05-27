from typing import Any

from pydantic import BaseModel, Field


class AccessSettings(BaseModel):
    with_whom_options: list[str] = Field(default_factory=list)
    role_permissions: dict[str, dict[str, bool]] = Field(default_factory=dict)


class AccessSettingsPatch(BaseModel):
    with_whom_options: list[str] | None = None
    role_permissions: dict[str, dict[str, bool]] | None = None

    def as_settings(self, current: AccessSettings) -> AccessSettings:
        data: dict[str, Any] = current.model_dump()
        if self.with_whom_options is not None:
            data["with_whom_options"] = self.with_whom_options
        if self.role_permissions is not None:
            data["role_permissions"] = self.role_permissions
        return AccessSettings(**data)
