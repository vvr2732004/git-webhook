# Commands Reference

This file is the quick command sheet for running the GitHub webhook POC locally.

Project root:

```bash
cd /home/think41/vishnu/roi/git-webhook
```

## 1. Start the FastAPI app

```bash
cd /home/think41/vishnu/roi/git-webhook
. .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 2. Start ngrok

```bash
cd /home/think41/vishnu/roi/git-webhook
ngrok http 8000
```

Use the HTTPS forwarding URL from ngrok and configure GitHub webhook as:

```text
https://YOUR-NGROK-URL/webhooks/github
```

## 3. Health check

```bash
curl http://127.0.0.1:8000/health
```

## 4. Show stored events

```bash
curl -s http://127.0.0.1:8000/events | python3 -m json.tool
```

## 5. Show summary metrics

```bash
curl -s http://127.0.0.1:8000/metrics/summary | python3 -m json.tool
```

## 6. Save fresh re  Amet odio vitae magna leo vulputate sapien amet pulvinar blandit 
    lorem id tempus quis quis. Maecenas id id sapien in sit id tincidunt
     amet amet. Tellus quam diam quam vulputate nec sem bibendumport files

```bash
cd /home/think41/vishnu/roi/git-webhook
mkdir -p reports
curl -s http://127.0.0.1:8000/events | python3 -m json.tool > reports/events.json
curl -s http://127.0.0.1:8000/metrics/summary | python3 -m json.tool > reports/summary.json
```

## 7. Start the dashboard server

```bash
cd /home/think41/vishnu/roi/git-webhook
python3 -m http.server 8080
```

Open in browser:

```text
http://127.0.0.1:8080/reports/dashboard.html
```

## 8. Refresh dashboard source data

```bash
cd /home/think41/vishnu/roi/git-webhook
mkdir -p reports
curl -s http://127.0.0.1:8000/events | python3 -m json.tool > reports/events.json
curl -s http://127.0.0.1:8000/metrics/summary | python3 -m json.tool > reports/summary.json
```

## 9. Open SQLite directly

```bash
cd /home/think41/vishnu/roi/git-webhook
sqlite3 github_webhooks.db
```

Useful query:

```sql
SELECT id, delivery_id, event_type, action, repository_full_name, actor_login, occurred_at, received_at
FROM github_events
ORDER BY id DESC;
```

Exit:

```sql
.quit
```

## 10. Run tests

```bash
cd /home/think41/vishnu/roi/git-webhook
. .venv/bin/activate
pytest
```

## 11. Minimal 4-terminal setup

### Terminal 1: FastAPI app

```bash
cd /home/think41/vishnu/roi/git-webhook
. .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Terminal 2: ngrok

```bash
cd /home/think41/vishnu/roi/git-webhook
ngrok http 8000
```

### Terminal 3: inspect API output

```bash
cd /home/think41/vishnu/roi/git-webhook
curl http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/events | python3 -m json.tool
curl -s http://127.0.0.1:8000/metrics/summary | python3 -m json.tool
```

### Terminal 4: dashboard

```bash
cd /home/think41/vishnu/roi/git-webhook
python3 -m http.server 8080
```

## 12. Optional: save report snapshots after new GitHub activity

```bash
cd /home/think41/vishnu/roi/git-webhook
mkdir -p reports
curl -s http://127.0.0.1:8000/events | python3 -m json.tool > reports/events.json
curl -s http://127.0.0.1:8000/metrics/summary | python3 -m json.tool > reports/summary.json
```
