from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .observability import configure_observability
from .routers import access_settings, auth, chat, converter, dashboard, docs, extraction, health, outlook, quotes, users


settings = get_settings()
if settings.environment.lower() in {"prod", "production"} and settings.auth_secret == "dev-only-change-me":
    raise RuntimeError("AUTH_SECRET must be set in production")
configure_observability(settings)

app = FastAPI(
    title=settings.app_name,
    version=settings.api_version,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(extraction.router)
app.include_router(quotes.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(access_settings.router)
app.include_router(dashboard.router)
app.include_router(chat.router)
app.include_router(docs.router)
app.include_router(converter.router)
app.include_router(outlook.router)
