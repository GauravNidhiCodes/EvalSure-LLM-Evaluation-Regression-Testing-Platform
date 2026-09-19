FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 evalsure \
    && useradd --system --uid 10001 --gid evalsure --create-home --home-dir /home/evalsure evalsure

COPY pyproject.toml ./
COPY app ./app
COPY alembic.ini ./
COPY alembic ./alembic
COPY docker/entrypoint.sh /entrypoint.sh

RUN pip install --upgrade pip \
    && pip install . \
    && chmod +x /entrypoint.sh \
    && chown -R evalsure:evalsure /app

USER evalsure

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
