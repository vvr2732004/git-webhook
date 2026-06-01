from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def _parse_dt(value: str | int | float | None) -> datetime | None:
    if value is None:
        return None

    try:
        # Jira sometimes sends timestamp as milliseconds
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value / 1000, UTC)

        # Jira date strings usually look like: 2026-05-25T07:16:53.000+0000
        if isinstance(value, str):
            candidate = value.replace("Z", "+00:00")

            # Convert +0000 to +00:00 if needed
            if len(candidate) >= 5 and candidate[-5] in ["+", "-"] and candidate[-3] != ":":
                candidate = candidate[:-2] + ":" + candidate[-2:]

            return datetime.fromisoformat(candidate).astimezone(UTC)

    except (ValueError, TypeError, OSError):
        return None

    return None


def _isoformat_utc(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _best_timestamp(event_type: str, payload: dict[str, Any]) -> str | None:
    issue_fields = (payload.get("issue") or {}).get("fields") or {}
    comment = payload.get("comment") or {}
    worklog = payload.get("worklog") or {}

    candidates: list[str | int | float | None] = []

    if event_type in {"jira:issue_created", "jira:issue_updated", "jira:issue_deleted"}:
        candidates = [
            issue_fields.get("updated"),
            issue_fields.get("created"),
            payload.get("timestamp"),
        ]
    elif event_type in {"comment_created", "comment_updated", "comment_deleted"}:
        candidates = [
            comment.get("updated"),
            comment.get("created"),
            issue_fields.get("updated"),
            payload.get("timestamp"),
        ]
    elif event_type in {"worklog_created", "worklog_updated", "worklog_deleted"}:
        candidates = [
            worklog.get("updated"),
            worklog.get("created"),
            issue_fields.get("updated"),
            payload.get("timestamp"),
        ]
    else:
        candidates = [
            payload.get("timestamp"),
            issue_fields.get("updated"),
            issue_fields.get("created"),
        ]

    for candidate in candidates:
        parsed = _parse_dt(candidate)
        if parsed:
            return _isoformat_utc(parsed)

    return _isoformat_utc(datetime.now(UTC))


def _repository(payload: dict[str, Any]) -> dict[str, Any]:
    issue_fields = (payload.get("issue") or {}).get("fields") or {}
    project = issue_fields.get("project") or payload.get("project") or {}

    key = project.get("key")
    name = project.get("name")

    return {
        "id": project.get("id"),
        "name": key or name,
        "full_name": f"jira/{key}" if key else f"jira/{name}" if name else "jira/unknown",
        "private": None,
    }


def _actor(payload: dict[str, Any]) -> dict[str, Any]:
    user = payload.get("user") or {}

    login = (
        user.get("accountId")
        or user.get("emailAddress")
        or user.get("displayName")
    )

    return {
        "id": user.get("accountId"),
        "login": login,
        "type": "User",
    }


def _issue_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    issue = payload.get("issue") or {}
    fields = issue.get("fields") or {}

    project = fields.get("project") or payload.get("project") or {}
    assignee = fields.get("assignee") or {}
    reporter = fields.get("reporter") or {}
    priority = fields.get("priority") or {}
    status = fields.get("status") or {}
    issue_type = fields.get("issuetype") or {}

    return {
        "issue_id": issue.get("id"),
        "issue_key": issue.get("key"),
        "project_id": project.get("id"),
        "project_key": project.get("key"),
        "project_name": project.get("name"),
        "issue_type": issue_type.get("name"),
        "status": status.get("name"),
        "priority": priority.get("name"),
        "assignee": assignee.get("accountId") or assignee.get("displayName"),
        "reporter": reporter.get("accountId") or reporter.get("displayName"),
        "created_at": fields.get("created"),
        "updated_at": fields.get("updated"),
    }


def _comment_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    comment = payload.get("comment") or {}
    author = comment.get("author") or {}

    base = _issue_metadata(payload)

    base.update(
        {
            "comment_id": comment.get("id"),
            "comment_author": author.get("accountId") or author.get("displayName"),
            "created_at": comment.get("created"),
            "updated_at": comment.get("updated"),
        }
    )

    return base


def _worklog_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    worklog = payload.get("worklog") or {}
    author = worklog.get("author") or {}
    update_author = worklog.get("updateAuthor") or {}

    base = _issue_metadata(payload)

    base.update(
        {
            "worklog_id": worklog.get("id"),
            "worklog_author": author.get("accountId") or author.get("displayName"),
            "worklog_update_author": update_author.get("accountId")
            or update_author.get("displayName"),
            "time_spent_seconds": worklog.get("timeSpentSeconds"),
            "started_at": worklog.get("started"),
            "created_at": worklog.get("created"),
            "updated_at": worklog.get("updated"),
        }
    )

    return base


def _user_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    user = payload.get("user") or {}

    return {
        "user_id": user.get("accountId"),
        "display_name": user.get("displayName"),
        "active": user.get("active"),
        "time_zone": user.get("timeZone"),
        "account_type": user.get("accountType"),
        "self": user.get("self"),
    }


def normalize_jira_event(
    delivery_id: str,
    event_type: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    if event_type in {"jira:issue_created", "jira:issue_updated", "jira:issue_deleted"}:
        metadata = _issue_metadata(payload)
    elif event_type in {"comment_created", "comment_updated", "comment_deleted"}:
        metadata = _comment_metadata(payload)
    elif event_type in {"worklog_created", "worklog_updated", "worklog_deleted"}:
        metadata = _worklog_metadata(payload)
    elif event_type in {"user_created", "user_updated", "user_deleted"}:
        metadata = _user_metadata(payload)
    else:
        metadata = _issue_metadata(payload)

    return {
        "id": delivery_id,
        "source": "jira",
        "event_type": event_type,
        "action": payload.get("webhookEvent"),
        "repository": _repository(payload),
        "actor": _actor(payload),
        "occurred_at": _best_timestamp(event_type, payload),
        "metadata": metadata,
    }