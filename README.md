# GitHub Webhook Testing Service

Small FastAPI service for receiving GitHub webhooks, verifying signatures, normalizing metadata-only developer activity events, and exposing inspection and summary endpoints for a Developer Intelligence Platform POC.

## Privacy

This service is intentionally metadata-only.

- It does not store code content.
- It does not store commit diff content.
- It does not store pull request body text.
- It does not store review/comment body text.
- It does not store commit messages.

Only event metadata needed for behavior and workflow metrics is normalized and stored.

## Setup

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

Set `GITHUB_WEBHOOK_SECRET` in `.env`.

## Environment Variables

- `GITHUB_WEBHOOK_SECRET`: Secret used to verify `X-Hub-Signature-256`
- `DATABASE_URL`: SQLAlchemy database URL. Default is local SQLite.
- `STORE_RAW_PAYLOAD`: `true` or `false`. Defaults to `false`.
- `LOG_LEVEL`: Logging level. Defaults to `INFO`.

## Running Locally

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

## Testing with ngrok

Start the app locally, then expose it:

```bash
ngrok http 8000
```

Use the HTTPS forwarding URL from ngrok and append `/webhooks/github`.

Example:

```text
https://abc123.ngrok-free.app/webhooks/github
```

## GitHub Webhook Setup

In your GitHub repository:

1. Go to `Settings` -> `Webhooks` -> `Add webhook`
2. Payload URL: your ngrok URL with `/webhooks/github`
3. Content type: `application/json`
4. Secret: same value as `GITHUB_WEBHOOK_SECRET`
5. Select individual events:
   - `Pushes`
   - `Pull requests`
   - `Pull request reviews`
   - `Pull request review comments`
   - `Workflow runs`
   - `Deployments`
   - `Deployment statuses`
6. Save webhook

GitHub will also send a `ping` event when the webhook is created.

## Sample curl Test with Generated Signature

```bash
payload='{"zen":"Keep it logically awesome.","repository":{"id":1,"name":"demo","full_name":"org/demo","private":false},"sender":{"id":123,"login":"octocat","type":"User"}}'
secret='replace-with-a-strong-secret'
signature=$(printf "%s" "$payload" | openssl dgst -sha256 -hmac "$secret" | sed 's/^.* //')

curl -X POST http://127.0.0.1:8000/webhooks/github \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: ping" \
  -H "X-GitHub-Delivery: test-delivery-1" \
  -H "X-Hub-Signature-256: sha256=$signature" \
  -d "$payload"
```

## Supported Events

- `ping`
- `push`
- `pull_request`
- `pull_request_review`
- `pull_request_review_comment`
- `workflow_run`
- `deployment`
- `deployment_status`

## API Endpoints

- `POST /webhooks/github`
- `GET /health`
- `GET /events`
- `GET /events/{delivery_id}`
- `GET /metrics/summary`

## Running Tests

```bash
pytest
```

## Local Test Flow

You can trigger useful event sequences by:

1. Pushing a branch to generate `push`
2. Opening a PR to generate `pull_request`
3. Requesting review and submitting review to generate `pull_request_review`
4. Commenting inline on a PR to generate `pull_request_review_comment`
5. Running a GitHub Actions workflow to generate `workflow_run`
6. Creating a deployment if your repo uses deployment environments

## What Event Data Is Useful Later for AI Attribution Metrics

This service stores only metadata, but it is enough to support downstream metrics such as:

- commit throughput by repository, branch, and actor
- bot vs human activity split
- PR creation, merge, and review cycle patterns
- review participation and review latency trends
- workflow run completion patterns and CI friction indicators
- deployment and deployment-status timing signals
- potential AI-assist proxies such as increased PR throughput, review frequency, branch churn, or bot-heavy automation interactions

The service deliberately avoids storing code, diffs, PR text, and comment text, which reduces privacy and IP exposure while still preserving operational signals.

## Validation Note

This repository is used to generate safe webhook test traffic for the GitHub connector POC.

For a second Jira sync test, this branch adds a minimal documentation-only change under `SCRUM-123`.
