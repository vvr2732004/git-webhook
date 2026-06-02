from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session
from app.db.models import GitHubEvent
from app.integrations.github.service import get_events_summary, serialize_github_event

router = APIRouter(prefix="/reports", tags=["reports"])
IST = ZoneInfo("Asia/Kolkata")


def _reports_dir() -> Path:
    return Path("reports")


def _write_report(path: Path, payload: Any) -> bool:
    rendered = json.dumps(payload, indent=4, ensure_ascii=False) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == rendered:
        return False
    path.write_text(rendered, encoding="utf-8")
    return True


def _to_ist_string(value: str) -> str:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    return parsed.astimezone(IST).isoformat()


def _convert_timestamps_to_ist(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {key: _convert_timestamps_to_ist(value) for key, value in payload.items()}
    if isinstance(payload, list):
        return [_convert_timestamps_to_ist(item) for item in payload]
    if isinstance(payload, str):
        try:
            return _to_ist_string(payload)
        except ValueError:
            return payload
    return payload


@router.post("/refresh")
async def refresh_reports(db: Session = Depends(get_db_session)) -> dict[str, Any]:
    reports_dir = _reports_dir()
    reports_dir.mkdir(parents=True, exist_ok=True)

    events = db.scalars(select(GitHubEvent).order_by(GitHubEvent.received_at.desc())).all()
    events_payload = [_convert_timestamps_to_ist(serialize_github_event(event)) for event in events]
    summary_payload = get_events_summary(db)

    events_changed = _write_report(reports_dir / "events.json", events_payload)
    summary_changed = _write_report(reports_dir / "summary.json", summary_payload)

    return {
        "status": "refreshed",
        "events_written": len(events_payload),
        "events_changed": events_changed,
        "summary_changed": summary_changed,
    }
