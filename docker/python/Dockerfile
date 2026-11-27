FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:0.13.10 /uv /usr/local/bin/uv

# Virtualenv lives outside the bind-mounted project dir so the host folder stays clean
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_CACHE_DIR=/tmp/uv-cache \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY pyproject.toml uv.lock* ./
RUN uv sync --no-install-project && rm -rf "$UV_CACHE_DIR" && chmod -R a+rwX /opt/venv

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
