# DeliverIQ backend image (DOCKER_DEPLOYMENT_DESIGN §4). Build context: repository root.
# Targets: api (Task 2), worker (Task 5), agent and agent-proxy (Task 15B).
FROM ghcr.io/astral-sh/uv:0.11.8@sha256:3b7b60a81d3c57ef471703e5c83fd4aaa33abcd403596fb22ab07db85ae91347 AS uv

FROM python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# ---- dependencies (locked, api group only) ----
FROM base AS api-deps
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /build
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-default-groups --group api --no-install-project

# ---- runtime: non-root, no compilers, no uv ----
FROM base AS api
ARG APP_UID=1000
ARG APP_GID=1000
RUN groupadd --gid "${APP_GID}" app \
    && useradd --uid "${APP_UID}" --gid app --no-create-home --shell /usr/sbin/nologin app
COPY --from=api-deps /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONPATH=/srv/backend
WORKDIR /srv/backend
COPY --chown=root:root backend/app ./app
COPY --chown=root:root backend/config ./config
COPY --chown=root:root backend/migrations ./migrations
COPY --chown=root:root backend/alembic.ini ./alembic.ini
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
# ---- worker dependencies: api + worker groups (CODE_STRUCTURE §11) ----
FROM api-deps AS worker-deps
RUN uv sync --locked --no-default-groups --group api --group worker --no-install-project
# ---- worker runtime: same source tree, job queue entry point (DDR-63, DDR-105) ----
FROM api AS worker
USER root
COPY --from=worker-deps /opt/venv /opt/venv
USER app
CMD ["python", "-m", "app.worker"]

# ---- disposable Builder Agent sandbox (DDR-70, DDR-127) ----
FROM api-deps AS agent-deps
RUN uv sync --locked --no-default-groups --group api --group dev --no-install-project
FROM api AS agent
USER root
RUN apt-get update \
    && apt-get install --no-install-recommends -y bash curl git \
    && rm -rf /var/lib/apt/lists/*
COPY --from=agent-deps /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONPATH=/workspace/backend
USER app
CMD ["sleep", "infinity"]

# ---- minimal standard-library HTTPS egress proxy ----
FROM base AS agent-proxy
COPY --from=api /srv/backend/app/shared/agent_egress.py /srv/agent/proxy.py
USER nobody
EXPOSE 3128
CMD ["python", "/srv/agent/proxy.py", "/run/agent/ai_models.yaml"]
