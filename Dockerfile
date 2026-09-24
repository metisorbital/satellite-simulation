# syntax=docker/dockerfile:1
FROM node:22.23.0-bookworm@sha256:e0d149b4727ac0c20d9774e801e423d7a946a0bffced886f42cfe9cd3c67820a AS frontend-build

ARG FLUTTER_REVISION=6a19cca56475dbfba1478ee68d7bd0c2ef891da1
RUN apt-get update && apt-get install -y --no-install-recommends git curl unzip xz-utils libglu1-mesa ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && git clone --branch 3.47.5 --depth 1 https://github.com/flutter/flutter.git /opt/flutter \
    && test "$(git -C /opt/flutter rev-parse HEAD)" = "$FLUTTER_REVISION"
ENV PATH=/opt/flutter/bin:$PATH \
    CI=true \
    FLUTTER_SUPPRESS_ANALYTICS=true \
    TAR_OPTIONS=--no-same-owner
RUN flutter config --no-analytics && flutter precache --web

WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
COPY tests/fixtures/orbit-interpolation.json /build/tests/fixtures/orbit-interpolation.json
RUN npm run prepare:cesium && flutter pub get --enforce-lockfile && flutter build web --release --no-web-resources-cdn

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
COPY --chown=metis:metis --from=frontend-build /build/frontend/build/web ./frontend/build/web
USER metis
EXPOSE 8000
CMD ["sh", "-c", "metis-sim migrate && exec metis-sim serve --host 0.0.0.0 --port ${PORT:-8000}"]
