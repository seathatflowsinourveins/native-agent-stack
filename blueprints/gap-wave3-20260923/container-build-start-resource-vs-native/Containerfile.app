# Pinned base: docker.io/library/python:3.13-slim@sha256:8d9d0b8bcf6506481eae4907c18f5e3e7902e629f5f6d684f9e7c32e85e3ddf0
FROM docker.io/library/python@sha256:8d9d0b8bcf6506481eae4907c18f5e3e7902e629f5f6d684f9e7c32e85e3ddf0
ENV PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_CACHE_DIR=/tmp/uv-cache
WORKDIR /app
COPY pyproject.toml uv.lock alembic.ini /app/
COPY backend /app/backend
COPY migrations /app/migrations
RUN pip install --no-cache-dir uv==0.12.17 \
    && uv sync --frozen --no-build
EXPOSE 8000
CMD ["uv", "run", "--frozen", "uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000"]
