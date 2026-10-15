FROM node:22-alpine AS frontend

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY src/aia/web ./src/aia/web
RUN npm run build:css

FROM ghcr.io/astral-sh/uv:latest AS uv

FROM python:3.12-slim

COPY --from=uv /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY . .
COPY --from=frontend /app/src/aia/web/static/app.css ./src/aia/web/static/app.css
RUN uv sync --locked --no-dev

CMD ["uv", "run", "--no-sync", "uvicorn", "aia.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
