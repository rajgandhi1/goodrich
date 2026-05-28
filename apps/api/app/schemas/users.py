from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


UserRole = Literal[
    "admin",
    "management",
    "approver",
    "sales",
    "estimation",
    "technical",
    "planning",
    "material_planner",
    "purchase",
    "viewer",
]


class AppUserBase(BaseModel):
    name: str = ""
    designation: str = ""
    contact: str = ""
    email: str
    role: UserRole = "sales"
    active: bool = True


class AppUserCreate(AppUserBase):
    user_id: str | None = None
    password: str | None = None


class AppUserPatch(BaseModel):
    name: str | None = None
    designation: str | None = None
    contact: str | None = None
    email: str | None = None
    password: str | None = None
    role: UserRole | None = None
    active: bool | None = None


class AppUserRead(AppUserBase):
    id: str
    org_id: str
    created_at: datetime
    updated_at: datetime


class AppUserLogin(BaseModel):
    username: str
    password: str
