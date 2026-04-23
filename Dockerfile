FROM python:3.12-slim-bookworm AS base

RUN apt-get update && apt-get upgrade -y && apt-get install -y \
    curl \
    git \
    unzip \
    libaio1 \
    build-essential \
    gcc \
    libssl-dev \
    pkg-config \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /tmp/* /var/tmp/*

FROM base AS uv-setup

RUN curl -Ls https://astral.sh/uv/install.sh | bash
ENV PATH="/root/.local/bin:${PATH}"
ENV UV_SYSTEM_PYTHON=true

FROM uv-setup AS development

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --all-extras

COPY . .

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
RUN groupadd -r appuser && useradd -r -g appuser appuser
RUN chown -R appuser:appuser /app

ENV VIRTUAL_ENV=/app/.venv
ENV PATH="/app/.venv/bin:$PATH"
USER appuser

FROM uv-setup AS production

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev

COPY . .

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
RUN groupadd -r appuser && useradd -r -g appuser appuser
RUN chown -R appuser:appuser /app

RUN find /app -name "*.pyc" -delete && \
    find /app -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true && \
    find /app -name "tests" -type d -exec rm -rf {} + 2>/dev/null || true && \
    find /app -name "test_*" -delete && \
    find /app -name "*_test.py" -delete

ENV VIRTUAL_ENV=/app/.venv
ENV PATH="/app/.venv/bin:$PATH"
USER appuser

FROM production
