from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session
from app.core.config import get_settings
from app.integrations.jira.service import process_jira_webhook

router = APIRouter(prefix="/webhooks", tags=["jira-webhooks"])


@router.post("/jira")
async def receive_jira_webhook(request: Request, db: Session = Depends(get_db_session)) -> dict:
    settings = get_settings()
    configured_token = settings.jira_webhook_token
    provided_token = request.query_params.get("token") or request.headers.get("X-Webhook-Token")
    if configured_token and provided_token != configured_token:
        raise HTTPException(status_code=401, detail="Invalid Jira webhook token")

    raw_body = await request.body()
    event_type = request.headers.get("X-Atlassian-Webhook-Identifier") or request.headers.get("X-Atlassian-Webhook-Event")
    if not event_type:
        event_type = request.headers.get("X-Event-Key") or request.headers.get("X-Atlassian-Webhook") or "jira:unknown"

    delivery_id = request.headers.get("X-Atlassian-Webhook-Trace") or request.headers.get("X-Request-Id")
    payload_event = None
    try:
        payload_event = (await request.json()).get("webhookEvent")
    except Exception:
        payload_event = None

    return process_jira_webhook(
        raw_body=raw_body,
        event_type=payload_event or event_type,
        delivery_id=delivery_id,
        db=db,
    )
