# One image recipe for all Python apps. Build with --build-arg APP=api|voice|worker.
FROM python:3.12-slim AS base

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1

WORKDIR /app

ARG APP

# Install deps first (cached layer), then the workspace code.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=packages/shared/pyproject.toml,target=packages/shared/pyproject.toml \
    --mount=type=bind,source=apps/api/pyproject.toml,target=apps/api/pyproject.toml \
    --mount=type=bind,source=apps/voice/pyproject.toml,target=apps/voice/pyproject.toml \
    --mount=type=bind,source=apps/worker/pyproject.toml,target=apps/worker/pyproject.toml \
    uv sync --frozen --no-dev --no-install-workspace --package propcall-${APP}

COPY packages/shared packages/shared
COPY apps apps
COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable --package propcall-${APP}

ENV PATH="/app/.venv/bin:$PATH"

RUN useradd --create-home --uid 10001 app && mkdir -p /app/audio_cache && chown -R app /app
USER app
