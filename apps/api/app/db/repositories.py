from __future__ import annotations

import base64
import json
import mimetypes
import threading
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Integer,
    LargeBinary,
    MetaData,
    Numeric,
    String,
    Table,
    Text,
    create_engine,
    delete,
    insert,
    select,
    text,
    update,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from app.config import get_settings
from app.schemas.common import StageHistoryEntry
from app.schemas.jobs import JobRead
from app.schemas.quotes import QuoteCreate, QuotePatch, QuoteRead


metadata = MetaData()
json_type = JSON().with_variant(JSONB, "postgresql")
uuid_type = PGUUID(as_uuid=True).with_variant(String(36), "sqlite")

quotes_table = Table(
    "quotes",
    metadata,
    Column("id", uuid_type, primary_key=True),
    Column("org_id", uuid_type, index=True),
    Column("created_by", uuid_type),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("quote_no", Text, nullable=False, default=""),
    Column("customer", Text, nullable=False, default=""),
    Column("project_ref", Text, nullable=False, default=""),
    Column("custom_label", Text, nullable=False, default=""),
    Column("timestamp", Text, nullable=False, default=""),
    Column("n_items", Integer, nullable=False, default=0),
    Column("n_ready", Integer, nullable=False, default=0),
    Column("n_check", Integer, nullable=False, default=0),
    Column("n_missing", Integer, nullable=False, default=0),
    Column("n_regret", Integer, nullable=False, default=0),
    Column("items", json_type, nullable=False, default=list),
    Column("quote_data", json_type, nullable=False, default=dict),
    Column("quote_pdf_b64", Text, nullable=False, default=""),
    Column("quote_pdf_name", Text, nullable=False, default=""),
    Column("stage", Text, nullable=False, default="initial"),
    Column("stage_history", json_type, nullable=False, default=list),
    Column("stage_meta", json_type, nullable=False, default=dict),
    Column("version", Integer, nullable=False, default=1),
)

jobs_table = Table(
    "extraction_jobs",
    metadata,
    Column("id", uuid_type, primary_key=True),
    Column("org_id", uuid_type, index=True),
    Column("created_by", uuid_type),
    Column("quote_id", uuid_type),
    Column("status", Text, nullable=False, default="queued"),
    Column("source_type", Text, nullable=False, default="email"),
    Column("progress", Numeric, nullable=False, default=0),
    Column("message", Text, nullable=False, default=""),
    Column("items", json_type, nullable=False, default=list),
    Column("skipped_count", Integer, nullable=False, default=0),
    Column("error", Text),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

exports_table = Table(
    "generated_exports",
    metadata,
    Column("token", uuid_type, primary_key=True),
    Column("org_id", uuid_type, index=True),
    Column("quote_id", uuid_type, index=True),
    Column("export_type", Text, nullable=False, default=""),
    Column("filename", Text, nullable=False),
    Column("content_type", Text, nullable=False),
    Column("content", LargeBinary, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

doc_sessions_table = Table(
    "doc_sessions",
    metadata,
    Column("id", uuid_type, primary_key=True),
    Column("org_id", uuid_type, index=True),
    Column("documents", json_type, nullable=False, default=dict),
    Column("messages", json_type, nullable=False, default=list),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _quote_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"n_items": len(items), "n_ready": 0, "n_check": 0, "n_missing": 0, "n_regret": 0}
    for item in items:
        status = str(item.get("status") or "missing")
        key = f"n_{status}"
        if key in counts:
            counts[key] += 1
    return counts


def _tenant_uuid(value: str) -> uuid.UUID:
    text_value = (value or "local").strip() or "local"
    try:
        return uuid.UUID(text_value)
    except ValueError:
        return uuid.uuid5(uuid.NAMESPACE_URL, f"ggpl-gasket-quote/{text_value}")


def _uuid(value: str | uuid.UUID | None) -> uuid.UUID | None:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))


def _stage_history_json(entries: list[StageHistoryEntry] | list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for entry in entries:
        if isinstance(entry, StageHistoryEntry):
            result.append(entry.model_dump(mode="json"))
        else:
            result.append(StageHistoryEntry(**entry).model_dump(mode="json"))
    return result


def _json_datetime(value: datetime | str) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _parse_dt(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        return value
    if value.endswith("Z"):
        value = f"{value[:-1]}+00:00"
    return datetime.fromisoformat(value)


def _content_type(filename: str, content_type: str | None) -> str:
    return content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"


class LocalJsonRepository:
    """Persistent local fallback used when Postgres is unavailable."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.RLock()
        self._state = {
            "quotes": {},
            "jobs": {},
            "exports": {},
            "doc_sessions": {},
        }
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            self._state.update(json.loads(self._path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            self._state = {"quotes": {}, "jobs": {}, "exports": {}, "doc_sessions": {}}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._state, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(self._path)

    def _quote_from_data(self, data: dict[str, Any]) -> QuoteRead:
        row = dict(data)
        row["created_at"] = _parse_dt(row["created_at"])
        row["updated_at"] = _parse_dt(row["updated_at"])
        return QuoteRead(**row)

    def _job_from_data(self, data: dict[str, Any]) -> JobRead:
        row = dict(data)
        row["created_at"] = _parse_dt(row["created_at"])
        row["updated_at"] = _parse_dt(row["updated_at"])
        return JobRead(**row)

    def create_quote(self, org_id: str, user_id: str, payload: QuoteCreate) -> QuoteRead:
        now = _now()
        quote_id = str(uuid.uuid4())
        data = payload.model_dump()
        counts = _quote_counts(data["items"])
        quote = QuoteRead(
            id=quote_id,
            org_id=org_id,
            created_by=user_id,
            created_at=now,
            updated_at=now,
            version=1,
            stage_history=[StageHistoryEntry(stage=payload.stage, at=now, user_id=user_id)],
            **data,
            **counts,
        )
        stored = quote.model_dump(mode="json")
        with self._lock:
            self._state["quotes"][quote_id] = stored
            self._save()
        return deepcopy(quote)

    def list_quotes(self, org_id: str) -> list[QuoteRead]:
        with self._lock:
            rows = [
                self._quote_from_data(deepcopy(q))
                for q in self._state["quotes"].values()
                if q.get("org_id") == org_id
            ]
        return sorted(rows, key=lambda q: q.created_at, reverse=True)

    def get_quote(self, org_id: str, quote_id: str) -> QuoteRead | None:
        with self._lock:
            quote = self._state["quotes"].get(quote_id)
            if not quote or quote.get("org_id") != org_id:
                return None
            return self._quote_from_data(deepcopy(quote))

    def update_quote(self, org_id: str, quote_id: str, payload: QuotePatch) -> QuoteRead | None:
        with self._lock:
            quote = self._state["quotes"].get(quote_id)
            if not quote or quote.get("org_id") != org_id:
                return None
            data = self._quote_from_data(deepcopy(quote)).model_dump()
            for key, value in payload.model_dump(exclude_unset=True).items():
                if value is not None:
                    data[key] = value
            updated = QuoteRead(
                **{
                    **data,
                    **_quote_counts(data["items"]),
                    "updated_at": _now(),
                    "version": data["version"] + 1,
                }
            )
            self._state["quotes"][quote_id] = updated.model_dump(mode="json")
            self._save()
            return deepcopy(updated)

    def delete_quote(self, org_id: str, quote_id: str) -> bool:
        with self._lock:
            quote = self._state["quotes"].get(quote_id)
            if not quote or quote.get("org_id") != org_id:
                return False
            del self._state["quotes"][quote_id]
            self._save()
            return True

    def advance_stage(
        self,
        org_id: str,
        quote_id: str,
        stage: str,
        user_id: str,
        reason: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> QuoteRead | None:
        with self._lock:
            quote = self._state["quotes"].get(quote_id)
            if not quote or quote.get("org_id") != org_id:
                return None
            data = self._quote_from_data(deepcopy(quote)).model_dump()
            stage_meta = dict(data.get("stage_meta") or {})
            if metadata:
                stage_meta.update(metadata)
            data["stage"] = stage
            data["stage_meta"] = stage_meta
            data["stage_history"] = [
                *data.get("stage_history", []),
                StageHistoryEntry(stage=stage, reason=reason, metadata=metadata or {}, user_id=user_id),
            ]
            updated = QuoteRead(
                **{
                    **data,
                    **_quote_counts(data["items"]),
                    "updated_at": _now(),
                    "version": data["version"] + 1,
                }
            )
            self._state["quotes"][quote_id] = updated.model_dump(mode="json")
            self._save()
            return deepcopy(updated)

    def create_job(self, org_id: str, source_type: str, quote_id: str | None = None) -> JobRead:
        now = _now()
        job = JobRead(
            id=str(uuid.uuid4()),
            org_id=org_id,
            status="queued",
            source_type=source_type,
            quote_id=quote_id,
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            self._state["jobs"][job.id] = job.model_dump(mode="json")
            self._save()
        return deepcopy(job)

    def update_job(self, org_id: str, job_id: str, **changes: Any) -> JobRead | None:
        with self._lock:
            job = self._state["jobs"].get(job_id)
            if not job or job.get("org_id") != org_id:
                return None
            data = self._job_from_data(deepcopy(job)).model_dump()
            data.update(changes)
            data["updated_at"] = _now()
            updated = JobRead(**data)
            self._state["jobs"][job_id] = updated.model_dump(mode="json")
            self._save()
            return deepcopy(updated)

    def get_job(self, org_id: str, job_id: str) -> JobRead | None:
        with self._lock:
            job = self._state["jobs"].get(job_id)
            if not job or job.get("org_id") != org_id:
                return None
            return self._job_from_data(deepcopy(job))

    def save_export(
        self,
        org_id: str,
        content: bytes,
        filename: str,
        content_type: str,
        quote_id: str | None = None,
        export_type: str = "",
    ) -> str:
        token = str(uuid.uuid4())
        meta = {
            "token": token,
            "filename": filename,
            "content_type": _content_type(filename, content_type),
            "export_type": export_type,
            "created_at": _now().isoformat(),
        }
        with self._lock:
            self._state["exports"][token] = {
                **meta,
                "org_id": org_id,
                "quote_id": quote_id,
                "content": base64.b64encode(content).decode("ascii"),
            }
            if quote_id and quote_id in self._state["quotes"]:
                quote = self._state["quotes"][quote_id]
                stage_meta = dict(quote.get("stage_meta") or {})
                stage_meta["exports"] = [*(stage_meta.get("exports") or []), meta]
                quote["stage_meta"] = stage_meta
                quote["updated_at"] = _now().isoformat()
            self._save()
        return token

    def get_export(self, token: str) -> tuple[bytes, str, str] | None:
        with self._lock:
            row = self._state["exports"].get(token)
            if not row:
                return None
            content = base64.b64decode(row["content"])
            filename = row["filename"]
            return content, filename, _content_type(filename, row.get("content_type"))

    def create_doc_session(self, org_id: str, documents: dict[str, str]) -> dict[str, Any]:
        session = {"id": str(uuid.uuid4()), "org_id": org_id, "documents": dict(documents), "messages": []}
        with self._lock:
            self._state["doc_sessions"][session["id"]] = deepcopy(session)
            self._save()
        return deepcopy(session)

    def get_doc_session(self, org_id: str, session_id: str) -> dict[str, Any] | None:
        with self._lock:
            session = self._state["doc_sessions"].get(session_id)
            if not session or session.get("org_id") != org_id:
                return None
            return deepcopy(session)

    def append_doc_message(self, org_id: str, session_id: str, role: str, content: str) -> None:
        with self._lock:
            session = self._state["doc_sessions"].get(session_id)
            if session and session.get("org_id") == org_id:
                session.setdefault("messages", []).append({"role": role, "content": content})
                self._save()

    def update_doc_session(
        self,
        org_id: str,
        session_id: str,
        *,
        documents: dict[str, str] | None = None,
        messages: list[dict[str, str]] | None = None,
    ) -> dict[str, Any] | None:
        with self._lock:
            session = self._state["doc_sessions"].get(session_id)
            if not session or session.get("org_id") != org_id:
                return None
            if documents is not None:
                session["documents"] = dict(documents)
            if messages is not None:
                session["messages"] = list(messages)
            self._save()
            return deepcopy(session)


class PostgresRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        metadata.create_all(self._engine)
        with self._engine.begin() as conn:
            if self._engine.dialect.name == "postgresql":
                conn.execute(text("create extension if not exists pgcrypto"))
                conn.execute(text("alter table quotes add column if not exists updated_at timestamptz not null default now()"))
                conn.execute(text("alter table quotes add column if not exists org_id uuid"))
                conn.execute(text("alter table quotes add column if not exists created_by uuid"))
                conn.execute(text("alter table quotes add column if not exists version int not null default 1"))
                conn.execute(text("create index if not exists quotes_org_created_idx on quotes (org_id, created_at desc)"))
                conn.execute(text("create index if not exists generated_exports_org_created_idx on generated_exports (org_id, created_at desc)"))

    def _quote_from_row(self, row: Any) -> QuoteRead:
        data = dict(row._mapping if hasattr(row, "_mapping") else row)
        return QuoteRead(
            id=str(data["id"]),
            org_id=str(data["org_id"]),
            created_by=str(data["created_by"]),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            version=data["version"],
            quote_no=data["quote_no"] or "",
            customer=data["customer"] or "",
            project_ref=data["project_ref"] or "",
            custom_label=data["custom_label"] or "",
            items=data["items"] or [],
            quote_data=data["quote_data"] or {},
            stage=data["stage"] or "initial",
            stage_meta=data["stage_meta"] or {},
            stage_history=[StageHistoryEntry(**entry) for entry in (data["stage_history"] or [])],
            n_items=data["n_items"] or 0,
            n_ready=data["n_ready"] or 0,
            n_check=data["n_check"] or 0,
            n_missing=data["n_missing"] or 0,
            n_regret=data["n_regret"] or 0,
        )

    def _job_from_row(self, row: Any) -> JobRead:
        data = dict(row._mapping if hasattr(row, "_mapping") else row)
        return JobRead(
            id=str(data["id"]),
            org_id=str(data["org_id"]),
            status=data["status"],
            source_type=data["source_type"],
            quote_id=str(data["quote_id"]) if data.get("quote_id") else None,
            progress=float(data["progress"] or 0),
            message=data["message"] or "",
            items=data["items"] or [],
            skipped_count=data["skipped_count"] or 0,
            error=data["error"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
        )

    def create_quote(self, org_id: str, user_id: str, payload: QuoteCreate) -> QuoteRead:
        now = _now()
        quote_id = uuid.uuid4()
        org_uuid = _tenant_uuid(org_id)
        user_uuid = _tenant_uuid(user_id)
        data = payload.model_dump()
        counts = _quote_counts(data["items"])
        stage_history = [StageHistoryEntry(stage=payload.stage, at=now, user_id=user_id)]
        values = {
            "id": quote_id,
            "org_id": org_uuid,
            "created_by": user_uuid,
            "created_at": now,
            "updated_at": now,
            "version": 1,
            "stage_history": _stage_history_json(stage_history),
            **data,
            **counts,
        }
        with self._engine.begin() as conn:
            row = conn.execute(insert(quotes_table).values(**values).returning(quotes_table)).first()
        return self._quote_from_row(row)

    def list_quotes(self, org_id: str) -> list[QuoteRead]:
        org_uuid = _tenant_uuid(org_id)
        stmt = select(quotes_table).where(quotes_table.c.org_id == org_uuid).order_by(quotes_table.c.created_at.desc())
        with self._engine.begin() as conn:
            return [self._quote_from_row(row) for row in conn.execute(stmt)]

    def get_quote(self, org_id: str, quote_id: str) -> QuoteRead | None:
        org_uuid = _tenant_uuid(org_id)
        stmt = select(quotes_table).where(quotes_table.c.org_id == org_uuid, quotes_table.c.id == _uuid(quote_id))
        with self._engine.begin() as conn:
            row = conn.execute(stmt).first()
        return self._quote_from_row(row) if row else None

    def update_quote(self, org_id: str, quote_id: str, payload: QuotePatch) -> QuoteRead | None:
        current = self.get_quote(org_id, quote_id)
        if not current:
            return None
        data = current.model_dump()
        for key, value in payload.model_dump(exclude_unset=True).items():
            if value is not None:
                data[key] = value
        counts = _quote_counts(data["items"])
        values = {
            "quote_no": data["quote_no"],
            "customer": data["customer"],
            "project_ref": data["project_ref"],
            "custom_label": data["custom_label"],
            "items": data["items"],
            "quote_data": data["quote_data"],
            "stage": data["stage"],
            "stage_meta": data["stage_meta"],
            "stage_history": _stage_history_json(data["stage_history"]),
            "updated_at": _now(),
            "version": current.version + 1,
            **counts,
        }
        stmt = (
            update(quotes_table)
            .where(quotes_table.c.org_id == _tenant_uuid(org_id), quotes_table.c.id == _uuid(quote_id))
            .values(**values)
            .returning(quotes_table)
        )
        with self._engine.begin() as conn:
            row = conn.execute(stmt).first()
        return self._quote_from_row(row) if row else None

    def delete_quote(self, org_id: str, quote_id: str) -> bool:
        stmt = delete(quotes_table).where(quotes_table.c.org_id == _tenant_uuid(org_id), quotes_table.c.id == _uuid(quote_id))
        with self._engine.begin() as conn:
            result = conn.execute(stmt)
        return result.rowcount > 0

    def advance_stage(
        self,
        org_id: str,
        quote_id: str,
        stage: str,
        user_id: str,
        reason: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> QuoteRead | None:
        current = self.get_quote(org_id, quote_id)
        if not current:
            return None
        stage_meta = dict(current.stage_meta or {})
        if metadata:
            stage_meta.update(metadata)
        history = [
            *current.stage_history,
            StageHistoryEntry(stage=stage, reason=reason, metadata=metadata or {}, user_id=user_id),
        ]
        return self._advance_stage_direct(org_id, quote_id, stage, stage_meta, history, current.version)

    def _advance_stage_direct(
        self,
        org_id: str,
        quote_id: str,
        stage: str,
        stage_meta: dict[str, Any],
        history: list[StageHistoryEntry],
        version: int,
    ) -> QuoteRead | None:
        stmt = (
            update(quotes_table)
            .where(quotes_table.c.org_id == _tenant_uuid(org_id), quotes_table.c.id == _uuid(quote_id))
            .values(
                stage=stage,
                stage_meta=stage_meta,
                stage_history=_stage_history_json(history),
                updated_at=_now(),
                version=version + 1,
            )
            .returning(quotes_table)
        )
        with self._engine.begin() as conn:
            row = conn.execute(stmt).first()
        return self._quote_from_row(row) if row else None

    def create_job(self, org_id: str, source_type: str, quote_id: str | None = None) -> JobRead:
        now = _now()
        values = {
            "id": uuid.uuid4(),
            "org_id": _tenant_uuid(org_id),
            "quote_id": _uuid(quote_id) if quote_id else None,
            "status": "queued",
            "source_type": source_type,
            "created_at": now,
            "updated_at": now,
        }
        with self._engine.begin() as conn:
            row = conn.execute(insert(jobs_table).values(**values).returning(jobs_table)).first()
        return self._job_from_row(row)

    def update_job(self, org_id: str, job_id: str, **changes: Any) -> JobRead | None:
        values = dict(changes)
        values["updated_at"] = _now()
        stmt = (
            update(jobs_table)
            .where(jobs_table.c.org_id == _tenant_uuid(org_id), jobs_table.c.id == _uuid(job_id))
            .values(**values)
            .returning(jobs_table)
        )
        with self._engine.begin() as conn:
            row = conn.execute(stmt).first()
        return self._job_from_row(row) if row else None

    def get_job(self, org_id: str, job_id: str) -> JobRead | None:
        stmt = select(jobs_table).where(jobs_table.c.org_id == _tenant_uuid(org_id), jobs_table.c.id == _uuid(job_id))
        with self._engine.begin() as conn:
            row = conn.execute(stmt).first()
        return self._job_from_row(row) if row else None

    def save_export(
        self,
        org_id: str,
        content: bytes,
        filename: str,
        content_type: str,
        quote_id: str | None = None,
        export_type: str = "",
    ) -> str:
        token = uuid.uuid4()
        now = _now()
        meta = {
            "token": str(token),
            "filename": filename,
            "content_type": _content_type(filename, content_type),
            "export_type": export_type,
            "created_at": now.isoformat(),
        }
        with self._engine.begin() as conn:
            conn.execute(
                insert(exports_table).values(
                    token=token,
                    org_id=_tenant_uuid(org_id),
                    quote_id=_uuid(quote_id) if quote_id else None,
                    export_type=export_type,
                    filename=filename,
                    content_type=_content_type(filename, content_type),
                    content=content,
                    created_at=now,
                )
            )
            if quote_id:
                row = conn.execute(
                    select(quotes_table.c.stage_meta).where(
                        quotes_table.c.org_id == _tenant_uuid(org_id), quotes_table.c.id == _uuid(quote_id)
                    )
                ).first()
                if row:
                    stage_meta = dict(row.stage_meta or {})
                    stage_meta["exports"] = [*(stage_meta.get("exports") or []), meta]
                    conn.execute(
                        update(quotes_table)
                        .where(quotes_table.c.org_id == _tenant_uuid(org_id), quotes_table.c.id == _uuid(quote_id))
                        .values(stage_meta=stage_meta, updated_at=now)
                    )
        return str(token)

    def get_export(self, token: str) -> tuple[bytes, str, str] | None:
        stmt = select(exports_table).where(exports_table.c.token == _uuid(token))
        with self._engine.begin() as conn:
            row = conn.execute(stmt).first()
        if not row:
            return None
        data = row._mapping
        return bytes(data["content"]), data["filename"], _content_type(data["filename"], data["content_type"])

    def create_doc_session(self, org_id: str, documents: dict[str, str]) -> dict[str, Any]:
        now = _now()
        session_id = uuid.uuid4()
        values = {
            "id": session_id,
            "org_id": _tenant_uuid(org_id),
            "documents": dict(documents),
            "messages": [],
            "created_at": now,
            "updated_at": now,
        }
        with self._engine.begin() as conn:
            conn.execute(insert(doc_sessions_table).values(**values))
        return {"id": str(session_id), "org_id": org_id, "documents": dict(documents), "messages": []}

    def get_doc_session(self, org_id: str, session_id: str) -> dict[str, Any] | None:
        stmt = select(doc_sessions_table).where(
            doc_sessions_table.c.org_id == _tenant_uuid(org_id), doc_sessions_table.c.id == _uuid(session_id)
        )
        with self._engine.begin() as conn:
            row = conn.execute(stmt).first()
        if not row:
            return None
        data = row._mapping
        return {
            "id": str(data["id"]),
            "org_id": org_id,
            "documents": data["documents"] or {},
            "messages": data["messages"] or [],
        }

    def append_doc_message(self, org_id: str, session_id: str, role: str, content: str) -> None:
        session = self.get_doc_session(org_id, session_id)
        if not session:
            return
        messages = [*session["messages"], {"role": role, "content": content}]
        stmt = (
            update(doc_sessions_table)
            .where(doc_sessions_table.c.org_id == _tenant_uuid(org_id), doc_sessions_table.c.id == _uuid(session_id))
            .values(messages=messages, updated_at=_now())
        )
        with self._engine.begin() as conn:
            conn.execute(stmt)

    def update_doc_session(
        self,
        org_id: str,
        session_id: str,
        *,
        documents: dict[str, str] | None = None,
        messages: list[dict[str, str]] | None = None,
    ) -> dict[str, Any] | None:
        session = self.get_doc_session(org_id, session_id)
        if not session:
            return None
        values: dict[str, Any] = {"updated_at": _now()}
        if documents is not None:
            values["documents"] = dict(documents)
            session["documents"] = dict(documents)
        if messages is not None:
            values["messages"] = list(messages)
            session["messages"] = list(messages)
        stmt = (
            update(doc_sessions_table)
            .where(doc_sessions_table.c.org_id == _tenant_uuid(org_id), doc_sessions_table.c.id == _uuid(session_id))
            .values(**values)
        )
        with self._engine.begin() as conn:
            conn.execute(stmt)
        return session


def _sqlalchemy_database_url(database_url: str) -> str:
    if database_url.startswith("postgresql://"):
        return f"postgresql+psycopg://{database_url.removeprefix('postgresql://')}"
    if database_url.startswith("postgres://"):
        return f"postgresql+psycopg://{database_url.removeprefix('postgres://')}"
    return database_url


def _make_repo() -> PostgresRepository | LocalJsonRepository:
    settings = get_settings()
    fallback_path = Path(".local/api_repository.json")
    try:
        database_url = _sqlalchemy_database_url(settings.database_url)
        connect_args: dict[str, Any] = {}
        if database_url.startswith("postgresql"):
            connect_args["connect_timeout"] = 2
        engine = create_engine(database_url, pool_pre_ping=True, future=True, connect_args=connect_args)
        with engine.connect() as conn:
            conn.execute(text("select 1"))
        return PostgresRepository(engine)
    except (ModuleNotFoundError, ImportError, SQLAlchemyError, OSError) as exc:
        if settings.environment.lower() in {"prod", "production"}:
            raise RuntimeError("Postgres repository is required in production. Check DATABASE_URL and database access.") from exc
        return LocalJsonRepository(fallback_path)


repo = _make_repo()
