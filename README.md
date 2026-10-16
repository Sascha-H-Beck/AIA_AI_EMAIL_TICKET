# AIA

AIA is an AI-assisted support-ticket system with a web dashboard and a separate FastAPI service. The API analyzes submitted support emails using Google's Gemini API (`gemini-3.8-flash`) with a local Ollama fallback, verifies customers against PostgreSQL, and stores tickets and workflow statuses.

## Project layout

- `src/aia/main.py` contains the AI-assisted email-processing flow and PostgreSQL operations.
- `src/aia/api/` contains the FastAPI application and ticket endpoints.
- `src/aia/web/` contains the dashboard HTML, JavaScript, and Tailwind CSS source.
- `src/aia/sql/init.sql` creates empty customer and support-ticket tables; new tickets start with the `new` status.
- `src/aia/sql/migrations/` contains the ticket-status migration and idempotent mock-customer seed for existing PostgreSQL databases.
- `pyproject.toml` declares the Python package and dependencies; `uv.lock` pins the resolved dependencies.
- `package.json` and `package-lock.json` pin the Tailwind CSS CLI used to build production CSS.
- `Dockerfile` builds the Tailwind assets and Python API image.
- `docker-compose.yml` runs the API, PostgreSQL, and Ollama services.
- `vercel.json` configures the API image as a Vercel Container Service.
- `.envtemplate` lists the local environment variables to copy into `.env`.

## Requirements

- Docker Desktop configured to use its Linux engine, with the Docker daemon running.
- Internet access on the first Compose startup to download the Ollama image and model.
- A Gemini API key for Gemini-first operation; it is optional when using local Ollama.
- Enough memory allocated to Docker Desktop for Ollama and the selected model. The default `qwen2.5:3b` model needs several gigabytes of available memory while running.
- For running outside Docker: Python 3.12 or newer and `uv`.
- For building the UI locally: Node.js and npm.

## Configure environment

In PowerShell, create your local environment file:

```powershell
Copy-Item .envtemplate .env
```

Edit `.env` and set a strong, unique `DB_PASSWORD` before starting the services. Set `DB_HOST`, `DB_NAME`, and `DB_USER` for your PostgreSQL instance as needed. Replace the empty `GEMINI_API_KEY` value with your key if you want Gemini tried first; without a key, the app uses Ollama directly. The template also includes database and model settings used by Compose. Never commit `.env` or use a shared/default database password.

The Gemini model is selected in `src/aia/main.py`; the Ollama model can be changed with `OLLAMA_MODEL`.

| Variable | Purpose |
| --- | --- |
| `GEMINI_API_KEY` | API key used by the Gemini client |
| `DB_HOST` | Database hostname; Compose sets this to `postgres_db` |
| `DB_NAME` | PostgreSQL database name |
| `DB_USER` | PostgreSQL user |
| `DB_PASSWORD` | PostgreSQL password |
| `DB_PORT` | PostgreSQL port |
| `SUPABASE_DB_URL` | Optional Supabase PostgreSQL connection URL; takes precedence over `DB_*` |
| `OLLAMA_MODEL` | Local model to pull and use as fallback; defaults to `qwen2.5:3b` |
| `OLLAMA_BASE_URL` | Ollama API URL for running the app outside Compose; defaults to `http://localhost:11434` |
| `API_PORT` | Host port for the dashboard and REST API; defaults to `8000` |

Keep `.env` private. It is excluded by `.gitignore` and `.dockerignore`; do not commit it or include the API key in logs or screenshots.

## Build and run with Docker Compose

From the project directory:

```powershell
docker compose config --quiet
docker compose up --build -d
```

Open the web dashboard at `http://localhost:8000` (or the configured `API_PORT`). The FastAPI interactive documentation is at `http://localhost:8000/docs`.

```powershell
docker compose logs -f ticket_api
```

Compose starts PostgreSQL and Ollama, applies the ticket-status migration and mock-customer seed, pulls the configured local model if needed, then starts the API service. The seed provides 30 fictional companies with customer IDs `CUST-1001` through `CUST-1030`; applying it repeatedly does not duplicate or overwrite existing customers. Existing tickets receive the `new` status. The model and database remain in named volumes. Gemini credentials are optional; if Gemini is unavailable, Ollama handles inference.

A fresh database starts with the schema and receives the mock customer records from the migration job. It contains no sample tickets. Ticket text is analyzed, customer-checked, and stored only when a ticket is submitted through `POST /api/tickets` or the dashboard. When an email contains one `CUST-####` ID, that exact ID is used instead of an inconsistent model extraction. The dashboard displays the matched company name; IDs outside the seed set are flagged for account-management review and shown without a company name until added to the customer table.

The API binds to localhost by default. This is appropriate for local development; add authentication and access controls before exposing ticket data to a network.

## Deploy to Vercel with Container Services

Vercel's Container Images feature is currently in beta. The root `vercel.json` routes all requests to the `aia-api` container service, which builds the existing `Dockerfile`. The API container serves both the dashboard and its `/static` assets. Keep the Vercel project Root Directory empty so the build can access the Dockerfile, Python project files, frontend sources, and lockfiles.

This deploys only the API container; Vercel does not start the services in `docker-compose.yml`. Before deploying:

1. Create a server-only `SUPABASE_DB_URL` environment variable in Vercel and set it to the Supabase Postgres **non-pooling** connection string. The app also recognizes `NEXT_PUBLIC_AIA_POSTGRES_URL_NON_POOLING` and `NEXT_PUBLIC_AIA_POSTGRES_URL` if those integration variables are already present, but do not create new database credentials with a `NEXT_PUBLIC_` prefix. The anon/publishable key, JWT secret, and service-role key variables are not used for PostgreSQL connections. The URL connection uses SSL by default; set `DB_SSLMODE` only if you need to override the default. Apply `src/aia/sql/init.sql` to a new database and `src/aia/sql/migrations/001_add_ticket_status.sql` when migrating an existing database. Populate real customer records through your intended data-management process; the demo customer seed is not run automatically.
2. Set `GEMINI_API_KEY` for AI analysis. If using Ollama instead or as a fallback, also set `OLLAMA_BASE_URL` to a publicly or privately reachable Ollama service and configure `OLLAMA_MODEL`; the Compose-only hostname `ollama` is not available to the Vercel container.
3. Deploy using the Vercel Container Images feature. The container listens on Vercel's `PORT` value (defaulting to port 80); Docker Compose overrides the container command to use its local API port.

Keep database and API credentials in Vercel environment settings, never in source control. Vercel deployment does not provide persistent PostgreSQL or Ollama model storage through this API container. Local Docker Compose continues to use its existing `DB_HOST`, `DB_NAME`, `DB_USER`, and `DB_PASSWORD` settings when `SUPABASE_DB_URL` is empty. To have the local API container connect to Supabase instead, set `SUPABASE_DB_URL` in `.env`; the Compose PostgreSQL service still starts for local migrations.

## Dashboard features

- Browse tickets with 25 rows per page.
- Choose Light, Dark, Dracula, Nord, or High Contrast themes; the selection is saved in the browser.
- Filter for **Today**, choose a single date or inclusive date range, or use **All** to clear filters and browse the latest tickets.
- Update a ticket to **In progress**, **Done**, or **Rejected**.
- Create a ticket by submitting support email text for AI analysis.
- See the API endpoints and open their interactive documentation in the API Endpoints panel.

## REST API

Ticket list and creation responses omit the original email. `GET /api/tickets/{ticket_id}` returns the full submitted email as `raw_email_content` for the dashboard's expandable ticket details.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/tickets` | List tickets; optional `date_from`, `date_to`, `limit`, and `offset` query parameters |
| `GET` | `/api/tickets/{ticket_id}` | Read a ticket and its full submitted description by ID |
| `POST` | `/api/tickets` | Create a ticket from `{"email_content": "..."}`; returns `201` and the persisted ticket |
| `PATCH` | `/api/tickets/{ticket_id}/status` | Set status to `in_progress`, `done`, or `rejected` |
| `GET` | `/health` | API health check |

Example PowerShell requests:

```powershell
Invoke-RestMethod http://localhost:8000/api/tickets
Invoke-RestMethod "http://localhost:8000/api/tickets?date_from=2026-10-01&date_to=2026-10-31"
Invoke-RestMethod http://localhost:8000/api/tickets/1

$ticket = @{ email_content = "Customer CUST-5582 reports a production API outage." } | ConvertTo-Json
Invoke-RestMethod http://localhost:8000/api/tickets -Method Post -ContentType "application/json" -Body $ticket

$status = @{ status = "in_progress" } | ConvertTo-Json
Invoke-RestMethod http://localhost:8000/api/tickets/1/status -Method Patch -ContentType "application/json" -Body $status
```

Stop services:

```powershell
docker compose down
```

PostgreSQL data and the downloaded Ollama model are stored in named volumes and remain when containers are stopped or removed. To delete both volumes, including all database data and downloaded model files, run `docker compose down --volumes`.

## Run locally with uv

With Python 3.12 or newer, `uv`, and PostgreSQL/Ollama reachable from the host:

```powershell
uv sync --locked
npm ci
npm run build:css
uv run uvicorn aia.api.app:app --reload --host 127.0.0.1 --port 8000
```

The local API loads `.env` from the project directory. Set `DB_HOST=localhost` when connecting to PostgreSQL published by Compose, and `OLLAMA_BASE_URL=http://localhost:11434` when using Compose's Ollama service from the host.


## Screenshots

### UI - Intreface with Theme selected:
![UI Screenshot 1](https://raw.githubusercontent.com/Sascha-H-Beck/AIA_AI_EMAIL_TICKET/refs/heads/main/src/aia/web/static/ui_1.png)

### UI - Intreface with Theme selected and Ticket overview and ticket details:
![UI Screenshot 2](https://raw.githubusercontent.com/Sascha-H-Beck/AIA_AI_EMAIL_TICKET/refs/heads/main/src/aia/web/static/ui_2.png)

### API Documentaion OPENAPI -USeage and Reference:

![UI Screenshot 2](https://raw.githubusercontent.com/Sascha-H-Beck/AIA_AI_EMAIL_TICKET/refs/heads/main/src/aia/web/static/api.png)


### API Test with Insomnia:

![API Test with Insomnia](https://raw.githubusercontent.com/Sascha-H-Beck/AIA_AI_EMAIL_TICKET/refs/heads/main/src/aia/web/static/api_insomnia_call.png)