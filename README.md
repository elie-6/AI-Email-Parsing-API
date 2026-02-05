# AI Email Parsing API

An **AI-driven email ingestion + parsing pipeline** built with FastAPI.

This is a backend API — handles OAuth-authorized Gmail ingestion, stores raw emails immutably, runs AI parsing, and sends notifications. It's a practical, work-ready backend you can run locally, test, and extend.

---

## What This Is

A FastAPI service that:

- Accepts **OAuth-authorized Gmail accounts** and ingests raw emails
- Stores **immutable raw emails** and separates AI-derived outputs into their own table
- Exposes a small set of **authenticated endpoints** for clients (login/signup + dashboard actions)
- Provides a **trigger to fetch+store emails** and enqueue/perform AI parsing
- Sends **notifications** (email/webhook — pluggable)

This is useful as a demonstrable backend for:

- Correct system design / API implementation
- Running an ingestion + parsing pipeline locally
- Prototyping a SaaS workflow: collect emails → parse → notify

---

## Features

- **JWT-based auth** (simple; access token in memory recommended for clients)
- **OAuth integration** for Gmail accounts (store OAuth tokens securely)
- **Storing raw immutable emails** (keeps original data for re-processing)
- **Separate AI output table** (`EmailAIResult`) — allows re-parsing without touching raw emails
- **Parsing status flags** to avoid duplicate processing (`ai_parse_status`)
- **Idempotency** via unique `gmail_id` in emails
- **Background fetching and parsing triggers** (designed to be run via background tasks or a queue)
- **Simple notification model** for delivering parsed results

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/signup` | Create a client (expects JSON) |
| `POST` | `/login` | Returns a JWT access token |
| `GET` | `/dashboard/emails?limit=&offset=` | Returns parsed emails for authenticated user |
| `GET` | `/dashboard/email/{email_id}` | Single email (with parsed result) |
| `POST` | `/dashboard/parse` | Trigger fetch + parse for connected Gmail accounts |

---

## Data Model

### Key Models

**Client**
- `id`, `name` (unique), `password_hash`
- `notification_email`, `is_active`
- Relationships: `gmail_accounts`, `notifications`

**GmailAccount**
- `id`, `client_id`, `gmail_address`, `gmail_token` (JSON)
- `is_active`, `last_fetched_at`

**Email**
- `id`, `gmail_account_id`, `gmail_id` (unique), `thread_id`
- `from_email`, `subject`, `snippet`, `received_at`
- `ai_parse_status` (e.g., `pending`, `done`) and `ai_parse_version`
- Relationship: `ai_result` (one-to-one)

**EmailAIResult**
- `email_id` (unique), `category`, `intent`, `urgency`
- `extracted_entities` (JSON), `summary`, `confidence`, `model_version`

**Notification**
- `client_id`, `email_id`, `channel`, `status`, `sent_to`, `error_message`

### Design Notes

- **Raw data (`Email`) is immutable** — do not overwrite original content
- **Parsed outputs are in their own table** so you can re-run parsing (new model / new version) without losing previous results
- **`gmail_id` is unique** — protects against duplicate ingestion
- **Use `ai_parse_status` flags** to avoid double-parsing

---

## Design Decisions

**Separate raw vs derived**: Storing AI outputs separately makes reprocessing trivial and auditable.

**Status flags**: `ai_parse_status` avoids race conditions and duplicate work when the parser runs concurrently.

**Store OAuth token JSON**: Real OAuth tokens require storage of refresh tokens & metadata — keep them as JSON so the client code is simple.

**Indexing**: Index `received_at`, `ai_parse_status`, and `gmail_address` for fast dashboard queries.

**N+1 prevention**: Use `selectinload` or similar eager-loading to avoid N+1 when loading emails + results.

**Cursor pagination**: Offset-based pagination is fine for small loads, but use cursor pagination for large scale to avoid performance degradation.

**Use background workers**: The parse operation should be enqueued to a worker system (RQ / Celery / Just a background task during development).

**Idempotency & dedupe**: Enforce unique constraints (e.g. `gmail_id`) and use `last_fetched_at` to limit fetching scope.

---

## Local Setup

### Prerequisites

- Python 3.10+
- PostgreSQL

### Installation

1. **Create virtualenv and install dependencies**:
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
# if using psycopg2:
pip install psycopg2-binary
```

2. **Configure environment variables**:

Create a `.env` or `backend/config.py` (do not commit secrets):
```
EMAIL_FROM=    (email to send notifications from)
EMAIL_APP_PASSWORD=      (Gmail SMTP app password for email_from)
SMTP_PORT=      (choose port)  

DATABASE_URL=postgresql://user:pass@localhost:5432/dbname

SECRET_KEY=      (choose a string key, for access token)
ALGORITHM=    (encryption and decryption algorithm)
ACCESS_TOKEN_EXPIRE_MINUTES=60

OPENAI_API_KEY=     (get from openai)

```

3. **Create database & tables**:

**Quick (development)**:
```bash
python test/create_tables.py
```

4. **Start the server**:
```bash
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

5. **Access Swagger docs**: http://127.0.0.1:8000/docs

---


## API Examples

### Login (form-encoded)
```bash
curl -X POST http://127.0.0.1:8000/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=testuser&password=pass123"
```

### Get parsed emails
```bash
curl -X GET "http://127.0.0.1:8000/dashboard/emails?limit=10&offset=0" \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```

### Trigger parse
```bash
curl -X POST http://127.0.0.1:8000/dashboard/parse \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```

---

## Example SQL Snippets (Postgres)

### Make name unique
```sql
ALTER TABLE clients ADD CONSTRAINT unique_client_name UNIQUE (name);
```

### Add password_hash (nullable) if missing
```sql
ALTER TABLE clients ADD COLUMN password_hash VARCHAR;
```

### Make password_hash NOT NULL (only after populating values)
```sql
ALTER TABLE clients ALTER COLUMN password_hash SET NOT NULL;
```

### Delete client id 2
```sql
DELETE FROM clients WHERE id = 2;
```

---

## Scaling & Production Notes

- **Move background/CPU-heavy parsing to a worker queue** (Celery / RQ / Sidekiq). Keep FastAPI responsive.
- **Use connection pooling** (SQLAlchemy settings, PG pool)
- **Use batched writes and WAL batching** if you have high ingestion rates
- **Add monitoring**: queue length, parse latency, DB slow queries
- **Add rate limiting and request authentication** enforcement in front (e.g., API Gateway)
- **Add Alembic migrations** for schema changes — DO NOT rely on `Base.metadata.create_all` for production schema evolution

---

## Tests

There are simple test scripts and seed scripts under `test/` to populate a client, Gmail account, and fake parsed emails. Use them to see the dashboard return real data without calling Gmail or AI during development.

---

## Security & Privacy Reminders

- **Do not commit** `backend/config.py`, `.env`, `credentials.json`, token files, or any secrets
- If you accidentally pushed secrets, **rotate them immediately** and purge the repo history (use `git filter-repo` or `bfg` and force-push)
- **Limit OAuth scopes** to the least privileges required

---


## Final Note

This repo is practical and opinionated. It's not perfect. It deliberately favors explicit, maintainable patterns (separate raw vs derived, parse flags, idempotent constraints) over clever one-liners.

If you clone it, you'll get a real API you can run locally and extend. It shows concrete engineering decisions — which is the point.   


**This repository intentionally contains only the backend API. The frontend is developed separately and consumes this service as a client.**  

---
