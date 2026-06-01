import json

from app.integrations.github.bot_detection import is_bot_actor


def _post_github_event(client, payload: dict, event_type: str, delivery_id: str, signature: str):
    return client.post(
        "/webhooks/github",
        headers={
            "X-GitHub-Event": event_type,
            "X-GitHub-Delivery": delivery_id,
            "X-Hub-Signature-256": signature,
            "Content-Type": "application/json",
        },
        content=json.dumps(payload),
    )


def test_valid_signature_accepted(client, make_signature):
    payload = {"repository": {"id": 1, "name": "repo", "full_name": "org/repo", "private": False}, "sender": {"id": 1, "login": "octocat", "type": "User"}}
    response = _post_github_event(client, payload, "ping", "delivery-valid", make_signature("test-secret", payload))
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"


def test_invalid_signature_rejected(client):
    payload = {"repository": {"id": 1, "name": "repo", "full_name": "org/repo", "private": False}, "sender": {"id": 1, "login": "octocat", "type": "User"}}
    response = _post_github_event(client, payload, "ping", "delivery-invalid", "sha256=bad")
    assert response.status_code == 401


def test_ping_event_works(client, make_signature):
    payload = {
        "zen": "Keep it logically awesome.",
        "repository": {"id": 1, "name": "repo", "full_name": "org/repo", "private": False},
        "sender": {"id": 1, "login": "octocat", "type": "User"},
    }
    response = _post_github_event(client, payload, "ping", "delivery-ping", make_signature("test-secret", payload))
    assert response.status_code == 200

    stored = client.get("/events/delivery-ping")
    assert stored.status_code == 200
    assert stored.json()["normalized_payload"]["event_type"] == "ping"


def test_push_event_normalized_without_commit_messages(client, make_signature):
    payload = {
        "ref": "refs/heads/main",
        "repository": {"id": 1, "name": "repo", "full_name": "org/repo", "private": False},
        "sender": {"id": 1, "login": "octocat", "type": "User"},
        "pusher": {"name": "Octo Cat", "email": "octo@example.com"},
        "head_commit": {"id": "abc123", "timestamp": "2026-05-21T10:00:00Z", "message": "should not persist"},
        "commits": [
            {"id": "abc123", "distinct": True, "message": "secret msg", "author": {"name": "Octo Cat", "email": "octo@example.com"}},
            {"id": "def456", "distinct": False, "message": "another msg", "author": {"name": "Bot", "email": "bot@example.com"}},
        ],
    }
    response = _post_github_event(client, payload, "push", "delivery-push", make_signature("test-secret", payload))
    assert response.status_code == 200

    stored = client.get("/events/delivery-push").json()["normalized_payload"]
    metadata = stored["metadata"]
    serialized = json.dumps(stored)
    assert metadata["branch"] == "main"
    assert metadata["commit_count"] == 2
    assert metadata["distinct_commit_count"] == 1
    assert "message" not in serialized
    assert "secret msg" not in serialized


def test_pull_request_event_normalized_without_pr_body(client, make_signature):
    payload = {
        "action": "opened",
        "number": 12,
        "repository": {"id": 1, "name": "repo", "full_name": "org/repo", "private": False},
        "sender": {"id": 1, "login": "octocat", "type": "User"},
        "pull_request": {
            "id": 1001,
            "number": 12,
            "state": "open",
            "body": "do not store this body",
            "user": {"login": "octocat"},
            "created_at": "2026-05-21T10:00:00Z",
            "updated_at": "2026-05-21T11:00:00Z",
            "closed_at": None,
            "merged_at": None,
            "merged": False,
            "additions": 10,
            "deletions": 4,
            "changed_files": 3,
            "commits": 2,
            "base": {"ref": "main"},
            "head": {"ref": "feature/test"},
            "requested_reviewers": [{"login": "reviewer1"}, {"login": "reviewer2"}],
        },
    }
    response = _post_github_event(client, payload, "pull_request", "delivery-pr", make_signature("test-secret", payload))
    assert response.status_code == 200

    stored = client.get("/events/delivery-pr").json()["normalized_payload"]
    metadata = stored["metadata"]
    serialized = json.dumps(stored)
    assert metadata["pr_number"] == 12
    assert metadata["requested_reviewers_count"] == 2
    assert "body" not in serialized
    assert "do not store this body" not in serialized


def test_bot_detection_works():
    assert is_bot_actor("dependabot", "User") is True
    assert is_bot_actor("renovate", "User") is True
    assert is_bot_actor("github-actions[bot]", "User") is True
    assert is_bot_actor("custom[bot]", "User") is True
    assert is_bot_actor("octocat", "Bot") is True
    assert is_bot_actor("octocat", "User") is False


def test_duplicate_delivery_id_does_not_create_duplicate_rows(client, make_signature):
    payload = {
        "repository": {"id": 1, "name": "repo", "full_name": "org/repo", "private": False},
        "sender": {"id": 1, "login": "octocat", "type": "User"},
    }
    signature = make_signature("test-secret", payload)

    first = _post_github_event(client, payload, "ping", "delivery-dup", signature)
    second = _post_github_event(client, payload, "ping", "delivery-dup", signature)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["status"] == "duplicate"

    events = client.get("/events").json()
    assert len(events) == 1


def test_jira_issue_created_event_is_accepted(client, monkeypatch):
    monkeypatch.setenv("JIRA_WEBHOOK_TOKEN", "jira-secret")
    from app.core.config import get_settings
    get_settings.cache_clear()

    payload = {
        "timestamp": "2026-05-25T10:00:00Z",
        "webhookEvent": "jira:issue_created",
        "user": {"accountId": "jira-user-1", "displayName": "Jira User"},
        "issue": {
            "id": "10001",
            "key": "PROJ-1",
            "fields": {
                "created": "2026-05-25T10:00:00Z",
                "updated": "2026-05-25T10:05:00Z",
                "project": {"id": "200", "key": "PROJ", "name": "Project"},
                "issuetype": {"name": "Task"},
                "status": {"name": "To Do"},
                "priority": {"name": "Medium"},
            },
        },
    }
    response = client.post(
        "/webhooks/jira?token=jira-secret",
        headers={"Content-Type": "application/json"},
        content=json.dumps(payload),
    )
    assert response.status_code == 200

    events = client.get("/events").json()
    assert len(events) == 1
    assert events[0]["event_type"] == "jira:issue_created"
    assert events[0]["repository_full_name"] == "jira/PROJ"
    assert events[0]["actor_login"] == "jira-user-1"
    assert events[0]["normalized_payload"]["source"] == "jira"


def test_jira_token_mismatch_is_rejected(client, monkeypatch):
    monkeypatch.setenv("JIRA_WEBHOOK_TOKEN", "jira-secret")
    from app.core.config import get_settings
    get_settings.cache_clear()

    response = client.post(
        "/webhooks/jira?token=wrong",
        headers={"Content-Type": "application/json"},
        content=json.dumps({"webhookEvent": "jira:issue_created"}),
    )
    assert response.status_code == 401
