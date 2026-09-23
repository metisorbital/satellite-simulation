# syntax=docker/dockerfile:1
FROM node:22.23.0-alpine@sha256:ab07539e0988b63558ff621f5fbe1077054c39d9809112974fb79993949d41cd AS frontend-build

WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
COPY tests/fixtures/orbit-interpolation.json /build/tests/fixtures/orbit-interpolation.json
RUN npm run build

FROM python:3.12.12-slim@sha256:f3fa41d74a768c2fce8016b98c191ae8c1bacd8f1152870a3f9f87d350920b7c AS python-build

WORKDIR /build
ENV UV_PROJECT_ENVIRONMENT=/app/.venv \
    UV_LINK_MODE=copy
RUN pip install --no-cache-dir uv==0.10.2
COPY pyproject.toml uv.lock README.md ./
COPY backend/ ./backend/
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev

FROM python:3.12.12-slim@sha256:f3fa41d74a768c2fce8016b98c191ae8c1bacd8f1152870a3f9f87d350920b7c

WORKDIR /app
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONPATH=/app/backend/src \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
RUN groupadd --gid 10001 metis && useradd --uid 10001 --gid metis --create-home --shell /usr/sbin/nologin metis
COPY --chown=metis:metis --from=python-build /app/.venv /app/.venv
COPY --chown=metis:metis alembic.ini ./
COPY --chown=metis:metis uv.lock ./
COPY --chown=metis:metis backend/src ./backend/src
COPY --chown=metis:metis backend/migrations ./backend/migrations
COPY --chown=metis:metis configs ./configs
COPY --chown=metis:metis --from=frontend-build /build/frontend/dist ./frontend/dist
USER metis
EXPOSE 8000
CMD ["metis-sim", "serve", "--host", "0.0.0.0", "--port", "8000"]
