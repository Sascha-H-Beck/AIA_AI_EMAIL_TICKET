# AIA Technical Documentation

**Description:** Technical reference for the AIA AI-assisted support-ticket application, including its architecture, data flow, API, and documented Python classes and methods.  
**Author:** Sascha H Beck  
**Date:** 2026-10-15

## 1. System Overview

AIA is a FastAPI support-ticket application with a browser-based dashboard. It accepts support email text, uses an AI provider to extract structured ticket fields, checks the extracted customer ID against PostgreSQL, and persists the ticket and workflow status.

The system is divided into:

- **API and application:** `src/aia/api/app.py` serves the dashboard, health endpoint, and ticket router.
- **Ticket API:** `src/aia/api/tickets.py` defines request/response schemas and REST handlers.
- **Ticket processing and persistence:** `src/aia/main.py` coordinates AI analysis, customer verification, and PostgreSQL operations.
- **Dashboard:** `src/aia/web/` contains the HTML, JavaScript, and Tailwind CSS assets.
- **Database:** `src/aia/sql/init.sql` initializes new databases; `src/aia/sql/migrations/` contains changes for existing database volumes.
- **Container orchestration:** `docker-compose.yml` runs PostgreSQL, the API, Ollama, and the database migration/model initialization jobs.

## 2. Ticket Processing Lifecycle

1. A client submits `email_content` to `POST /api/tickets`.
2. `CreateTicketRequest` validates that the content is non-empty and no longer than 30,000 characters.
3. `post_ticket` calls `process_incoming_email`.
4. The processing function requests structured `customer_id`, `issue_summary`, and `urgency` values from Gemini when configured. Ollama is used if Gemini is not configured or fails.
5. The structured output is validated against `SupportTicketSchema`.
6. `verify_customer_in_db` checks that the extracted customer exists and is active.
7. A verified customer is marked `VERIFIED_EXISTING_CUSTOMER`. An unknown or inactive customer is marked `INVALID_OR_UNKNOWN_ID`, escalated for account-management review, and assigned high urgency.
8. `save_ticket_to_db` stores the extracted fields and original email text and returns the persisted public ticket fields.
9. The API returns HTTP 201. Processing failures are logged and surfaced as HTTP 503.

Ticket analysis and customer verification occur only as part of ticket creation. Listing, reading, status updates, health checks, and application startup do not analyze ticket text.

## 3. Python Classes and Enums

The following descriptions reflect the class and enum docstrings in the source.

### `UrgencyLevel`

String enum for the AI-assigned urgency value. Supported values are `Low`, `Medium`, and `High`.

### `TicketStatus`

String enum defining persisted ticket workflow states: `new`, `in_progress`, `done`, and `rejected`.

### `TicketProcessingError`

Runtime error representing an inability to analyze, verify, or persist a ticket. The API maps it to HTTP 503 during ticket creation.

### `TicketNotFoundError`

Lookup error representing a request to read or update a ticket that does not exist. The API maps it to HTTP 404.

### `SupportTicketSchema`

Pydantic model validating AI-extracted ticket fields:

| Field | Type | Purpose |
| --- | --- | --- |
| `customer_id` | `str` | Customer identifier extracted from the email; use `UNKNOWN` when unavailable. |
| `issue_summary` | `str` | Concise technical issue summary in German. |
| `urgency` | `UrgencyLevel` | Impact-based urgency classification. |

### `TicketResponse`

Pydantic response model for a ticket. Includes the identifier, customer ID, summary, urgency, verification result, action, status, and processing timestamp. It deliberately excludes the original email text.

### `CreateTicketRequest`

Pydantic request model for ticket creation. `email_content` must contain at least one character and at most 30,000 characters.

### `UpdateTicketStatusRequest`

Pydantic request model containing the new status as a `TicketStatus`.

### `TicketStatusResponse`

Pydantic response model containing the ticket ID and its updated status.

## 4. Python Methods and Functions

### `aia.main`

#### `get_db_connection()`

Opens a psycopg2 PostgreSQL connection using the required `DB_HOST`, `DB_NAME`, `DB_USER`, and `DB_PASSWORD` environment variables, plus `DB_PORT` (default `5432`). It raises `RuntimeError` listing any missing required setting names; it never falls back to an embedded database password. Callers use connection context managers to commit successful transactions or roll back failed ones.

#### `verify_customer_in_db(customer_id)`

Checks the `customers` table for an active record matching `customer_id`. Returns `True` if one exists and `False` otherwise.

#### `save_ticket_to_db(ticket_data, raw_content)`

Inserts one analyzed ticket into `ai_support_tickets`, including the original source email, then returns the generated ID, public ticket fields, status, and processing timestamp. The original email is not part of API read responses.

#### `update_ticket_status(ticket_id, status)`

Updates a ticket’s workflow state and returns its ID and new status. Raises `TicketNotFoundError` when the ID does not exist.

#### `list_tickets(date_from=None, date_to=None, limit=50, offset=0)`

Returns public ticket records ordered by processing time descending, optionally filtered by inclusive processing dates and paginated with `limit` and `offset`. Original email content is excluded.

#### `get_ticket_by_id(ticket_id)`

Returns one public ticket record without its original email. Raises `TicketNotFoundError` when the ticket is missing.

#### `generate_ticket_with_ollama(prompt)`

Sends a structured-output request to the configured local Ollama service and validates its response against `SupportTicketSchema`. It uses `OLLAMA_BASE_URL` and `OLLAMA_MODEL` and raises request or validation errors when generation fails.

#### `process_incoming_email(email_content)`

Runs AI extraction with Gemini and Ollama fallback, verifies the extracted customer ID, sets routing/escalation metadata, persists the ticket, and returns the created public ticket record. Raises `TicketProcessingError` when analysis, verification, or persistence cannot complete.

### `aia.api.tickets`

#### `get_tickets(date_from=None, date_to=None, limit=50, offset=0)`

Handles `GET /api/tickets`. Validates that `date_from` is not later than `date_to`, then returns the requested ticket page. An invalid date range returns HTTP 422.

#### `get_ticket(ticket_id)`

Handles `GET /api/tickets/{ticket_id}`. Returns one ticket or HTTP 404 if it does not exist.

#### `post_ticket(request)`

Handles `POST /api/tickets`. Runs ticket analysis and persistence and returns HTTP 201. A processing failure is logged and returned as HTTP 503.

#### `patch_ticket_status(ticket_id, request)`

Handles `PATCH /api/tickets/{ticket_id}/status`. Persists the requested workflow status and returns the ID and status, or HTTP 404 if the ticket does not exist.

### `aia.api.app`

#### `dashboard()`

Serves the static dashboard HTML at `/`.

#### `health()`

Serves `/health` and returns `{"status": "ok"}` when the API process is responding.

### `aia.main` package entry point

#### `main()`

Displays a short greeting when the `aia` package command is invoked. It is not the API server entry point.

## 5. REST API

All ticket responses omit `raw_email_content`.

| Method | Path | Purpose | Success |
| --- | --- | --- | --- |
| `GET` | `/` | Serve the web dashboard. | `200` |
| `GET` | `/health` | Check API process responsiveness. | `200` |
| `GET` | `/api/tickets` | List tickets with optional `date_from`, `date_to`, `limit`, and `offset`. | `200` |
| `GET` | `/api/tickets/{ticket_id}` | Retrieve a ticket by ID. | `200` |
| `POST` | `/api/tickets` | Analyze submitted `email_content` and create a ticket. | `201` |
| `PATCH` | `/api/tickets/{ticket_id}/status` | Update ticket workflow status. | `200` |

Important error responses include:

- `422` for invalid request data or a date range with `date_from` later than `date_to`.
- `404` when a ticket requested for retrieval or update does not exist.
- `503` when AI analysis or ticket processing cannot complete.

## 6. Database Schema

### `customers`

| Column | Type | Purpose |
| --- | --- | --- |
| `customer_id` | `VARCHAR(50)` | Primary key used for customer verification. |
| `company_name` | `VARCHAR(100)` | Customer organization name. |
| `is_active` | `BOOLEAN` | Whether the customer can be verified; defaults to `TRUE`. |

### `ai_support_tickets`

| Column | Type | Purpose |
| --- | --- | --- |
| `id` | `SERIAL` | Primary key. |
| `customer_id` | `VARCHAR(50)` | Extracted customer identifier. |
| `issue_summary` | `TEXT` | AI-generated issue summary. |
| `urgency` | `VARCHAR(10)` | Ticket urgency. |
| `database_status` | `VARCHAR(50)` | Customer verification result. |
| `action_required` | `VARCHAR(100)` | Routing or escalation action. |
| `raw_email_content` | `TEXT` | Original email retained internally. |
| `processed_at` | `TIMESTAMP` | Processing time; defaults to the current timestamp. |
| `status` | `VARCHAR(20)` | Workflow status; defaults to `new` and is constrained to supported values. |

New database initialization creates schema without inserting sample customers or tickets. The status migration adds the `status` column and constraint to existing databases.

## 7. AI Providers and Configuration

- **Gemini:** Enabled when `GEMINI_API_KEY` is configured. The implementation uses `gemini-3.8-flash`, requests JSON conforming to `SupportTicketSchema`, and limits each HTTP request to 30 seconds with at most one retry before falling back.
- **Ollama:** Local fallback, or the primary provider when Gemini is not configured. `OLLAMA_BASE_URL` defaults to `http://localhost:11434`; `OLLAMA_MODEL` defaults to `qwen2.5:3b`. Inference can take several minutes, particularly on first model load.
- **Database:** `DB_HOST`, `DB_NAME`, `DB_USER`, and `DB_PASSWORD` must be set. `DB_PORT` defaults to `5432`.
- **Web/API port:** `API_PORT` configures the host-side Compose port; the application listens on port 8000 inside the container.

Keep credentials in the ignored `.env` file or another secure environment-injection mechanism. The tracked `.envtemplate` leaves the database password blank; set a strong, unique value in `.env` before starting Compose. Never place actual credentials in source control, logs, or this document.

## 8. Running and Validating

Start the services from the repository root:

```powershell
docker compose config --quiet
docker compose up --build -d
```

Run the API locally with `uv`:

```powershell
uv sync --locked
uv run uvicorn aia.api.app:app --reload --host 127.0.0.1 --port 8000
```

Build the dashboard CSS when its source changes:

```powershell
npm ci
npm run build:css
```

The FastAPI interactive documentation is available at `/docs` while the API is running.
