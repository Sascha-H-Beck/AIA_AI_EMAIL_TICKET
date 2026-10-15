---
name: aia-project
description: "Work on the AIA support-ticket application. Use when changing, debugging, reviewing, or running its FastAPI API, Python ticket processing, PostgreSQL schema, Docker Compose services, AI providers, or web dashboard."
---

# AIA Project

Use this skill for project-specific work in the AIA support-ticket application. First inspect the relevant source and follow existing patterns; do not assume the README is more current than the implementation.

## Project map

- `src/aia/main.py` contains PostgreSQL access, Gemini/Ollama ticket analysis, customer verification, and persistence.
- `src/aia/api/` contains the FastAPI app and ticket routes.
- `src/aia/web/` contains the dashboard HTML, JavaScript, and Tailwind CSS source.
- `src/aia/sql/init.sql` creates the initial database tables for a fresh PostgreSQL volume.
- `src/aia/sql/migrations/` contains migrations for existing database volumes.
- `docker-compose.yml` runs PostgreSQL, the API, the migration job, and Ollama.
- `Dockerfile` builds the frontend CSS and Python API image.
- `pyproject.toml` and `uv.lock` define Python dependencies; `package.json` and `package-lock.json` define frontend build dependencies.

## Application behavior and invariants

- The Python import package and project name are `aia`. Keep imports, Uvicorn targets, Docker paths, package metadata, and frontend build paths consistent with that name.
- `POST /api/tickets` is the creation path: it validates `email_content`, invokes ticket analysis, verifies the extracted customer ID against active PostgreSQL customers, then saves the ticket.
- Ticket analysis uses Gemini when `GEMINI_API_KEY` is set and falls back to the configured local Ollama model. Preserve structured output validation through `SupportTicketSchema`.
- A fresh database receives 30 fictional customer fixtures (`CUST-1001` through `CUST-1030`) through the idempotent Compose migration; it must not receive sample tickets. Do not add other startup/demo inserts or trigger ticket analysis during app startup, health checks, listing, or status updates.
- Customer records must be populated through an intentional data-management path; do not silently treat unknown customers as verified. An unknown or inactive customer is marked for review and escalated.
- Ticket list and creation responses omit `raw_email_content`; the individual detail endpoint intentionally returns it to populate the ticket accordion. Keep raw text out of list responses and logs, and escape it before rendering in the browser.
- Preserve explicit failure behavior: ticket analysis/database failures become `TicketProcessingError` and an HTTP 503; missing tickets return HTTP 404. Do not mask failures with empty or success-shaped results.
- Database changes must account for both new installations (`init.sql`) and existing named volumes (an idempotent migration). Never recommend deleting the database volume as a routine schema fix.
- Keep credentials in `.env`/environment variables; never commit or log API keys, passwords, or submitted ticket contents.

## Common development and validation commands

Run from the repository root:

```powershell
uv sync --locked
uv run uvicorn aia.api.app:app --reload --host 127.0.0.1 --port 8000
npm ci
npm run build:css
docker compose config --quiet
docker compose up --build -d
```

Use only the commands relevant to the change. For Python changes, run focused tests if present and check Python diagnostics/syntax. For frontend source or Tailwind changes, run `npm run build:css`. For dependency changes, update the appropriate manifest and lockfile. Validate Compose changes with `docker compose config --quiet` when local environment configuration is available.

## Change workflow

1. Trace the existing route-to-service-to-database flow before editing. Search for other callers when changing shared processing behavior.
2. Make the smallest complete change, preserving API schemas, status values, response privacy, and error semantics unless the request explicitly requires otherwise.
3. For schema work, update the fresh-install SQL and an appropriate migration, then check migration idempotency and compatibility with existing data.
4. Verify the requested behavior directly. Prefer focused tests or checks over unrelated full-suite work; report validation that could not be run.
5. Update README documentation when setup, endpoints, configuration, or operator behavior changes.
