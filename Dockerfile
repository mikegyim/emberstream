# Multi-stage build: slim production image, fast builds via cached deps layer.

FROM python:3.11-slim AS builder
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /build
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --upgrade pip && \
    pip wheel --wheel-dir=/wheels .

FROM python:3.11-slim AS runtime
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

# Non-root user
RUN groupadd --system app && useradd --system --gid app --home /app app

COPY --from=builder /wheels /wheels
RUN pip install --no-index --find-links=/wheels emberstream && rm -rf /wheels

USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').status==200 else 1)"

CMD ["uvicorn", "emberstream.main:app", "--host", "0.0.0.0", "--port", "8000"]
