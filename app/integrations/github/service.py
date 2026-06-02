from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import GitHubEvent
from app.integrations.github.bot_detection import is_bot_actor
from app.integrations.github.normalizers import normalize_github_event


def _serialize_dt_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def serialize_github_event(model: GitHubEvent) -> dict[str, Any]:
    return {
        "id": model.id,
        "delivery_id": model.delivery_id,
        "event_type": model.event_type,
        "action": model.action,
        "repository_full_name": model.repository_full_name,
        "actor_login": model.actor_login,
        "actor_type": model.actor_type,
        "is_bot": model.is_bot,
        "occurred_at": _serialize_dt_utc(model.occurred_at),
        "received_at": _serialize_dt_utc(model.received_at),
        "normalized_payload": model.normalized_payload,
        "raw_payload": model.raw_payload,
    }


def process_github_webhook(raw_body: bytes, event_type: str, delivery_id: str, db: Session) -> dict[str, Any]:
    settings = get_settings()

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON payload") from exc

    normalized = normalize_github_event(delivery_id=delivery_id, event_type=event_type, payload=payload)
    actor = normalized.get("actor") or {}
    repository = normalized.get("repository") or {}
    occurred_at_raw = normalized.get("occurred_at")
    occurred_at = None
    if occurred_at_raw:
        occurred_at = datetime.fromisoformat(occurred_at_raw.replace("Z", "+00:00")).astimezone(UTC)

    event = GitHubEvent(
        delivery_id=delivery_id,
        event_type=event_type,
        action=normalized.get("action"),
        repository_full_name=repository.get("full_name"),
        actor_login=actor.get("login"),
        actor_type=actor.get("type"),
        is_bot=is_bot_actor(actor.get("login"), actor.get("type")),
        occurred_at=occurred_at,
        normalized_payload=normalized,
        raw_payload=payload if settings.store_raw_payload else None,
    )

    try:
        db.add(event)
        db.commit()
        db.refresh(event)
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(GitHubEvent).where(GitHubEvent.delivery_id == delivery_id))
        if existing is None:
            raise HTTPException(status_code=409, detail="Duplicate delivery ID could not be resolved")
        return {"status": "duplicate", "delivery_id": delivery_id, "event_type": existing.event_type}

    return {"status": "accepted", "delivery_id": delivery_id, "event_type": event_type}


def get_events_summary(db: Session) -> dict[str, Any]:
    total_events = db.scalar(select(func.count()).select_from(GitHubEvent)) or 0
    events_by_type_rows = db.execute(
        select(GitHubEvent.event_type, func.count()).group_by(GitHubEvent.event_type)
    ).all()
    events_by_repository_rows = db.execute(
        select(GitHubEvent.repository_full_name, func.count()).group_by(GitHubEvent.repository_full_name)
    ).all()
    bot_events = db.scalar(select(func.count()).select_from(GitHubEvent).where(GitHubEvent.is_bot.is_(True))) or 0
    human_events = db.scalar(select(func.count()).select_from(GitHubEvent).where(GitHubEvent.is_bot.is_(False))) or 0
    pull_requests_opened = db.scalar(
        select(func.count()).select_from(GitHubEvent).where(
            GitHubEvent.event_type == "pull_request",
            GitHubEvent.action == "opened",
        )
    ) or 0
    pull_requests_merged = db.scalar(
        select(func.count()).select_from(GitHubEvent).where(
            GitHubEvent.event_type == "pull_request",
            GitHubEvent.action == "closed",
            func.json_extract(GitHubEvent.normalized_payload, "$.metadata.merged") == 1,
        )
    ) or 0
    pushes = db.scalar(select(func.count()).select_from(GitHubEvent).where(GitHubEvent.event_type == "push")) or 0
    workflow_runs_completed = db.scalar(
        select(func.count()).select_from(GitHubEvent).where(
            GitHubEvent.event_type == "workflow_run",
            func.json_extract(GitHubEvent.normalized_payload, "$.metadata.conclusion").is_not(None),
        )
    ) or 0

    return {
        "total_events": total_events,
        "events_by_type": {row[0]: row[1] for row in events_by_type_rows if row[0] is not None},
        "events_by_repository": {row[0]: row[1] for row in events_by_repository_rows if row[0] is not None},
        "bot_events": bot_events,
        "human_events": human_events,
        "pull_requests_opened": pull_requests_opened,
        "pull_requests_merged": pull_requests_merged,
        "pushes": pushes,
        "workflow_runs_completed": workflow_runs_completed,
    }
