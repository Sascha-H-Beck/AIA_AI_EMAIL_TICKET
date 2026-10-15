"""FastAPI application setup and dashboard/health routes."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from aia.api.tickets import router as tickets_router

WEB_DIR = Path(__file__).resolve().parent.parent / "web"

app = FastAPI(
    title="AI Support Ticket System API",
    version="1.0.0",
    description="Ticket management API and web dashboard.",
)
app.include_router(tickets_router)
app.mount(
    "/static",
    StaticFiles(directory=WEB_DIR / "static"),
    name="static",
)


@app.get("/", include_in_schema=False)
def dashboard() -> FileResponse:
    """Serve the static ticket dashboard."""
    return FileResponse(WEB_DIR / "index.html")


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    """Return the API process health status."""
    return {"status": "ok"}
