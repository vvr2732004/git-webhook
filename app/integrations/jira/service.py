from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import GitHubEvent
from app.integrations.github.bot_detection import is_bot_actor
from app.integrations.jira.normalizers import normalize_jira_event


def process_jira_webhook(raw_body: bytes, event_type: str, delivery_id: str | None, db: Session) -> dict[str, Any]:
    settings = get_settings()

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON payload") from exc

    resolved_delivery_id = delivery_id or str(uuid.uuid4())
    normalized = normalize_jira_event(
        delivery_id=resolved_delivery_id,
        event_type=event_type,
        payload=payload,
    )
    actor = normalized.get("actor") or {}
    repository = normalized.get("repository") or {}
    occurred_at_raw = normalized.get("occurred_at")
    occurred_at = None
    if occurred_at_raw:
        occurred_at = datetime.fromisoformat(occurred_at_raw.replace("Z", "+00:00")).astimezone(UTC)

    event = GitHubEvent(
        delivery_id=resolved_delivery_id,
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

    db.add(event)
    db.commit()
    db.refresh(event)
    return {"status": "accepted", "delivery_id": resolved_delivery_id, "event_type": event_type}
