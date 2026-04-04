# Stage 1: Install Python dependencies
FROM python:3.13-slim AS builder

WORKDIR /build

COPY pyproject.toml .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --prefix=/install .

# Stage 2: Runtime image (no build tools)
FROM python:3.13-slim

WORKDIR /app

COPY --from=builder /install /usr/local
COPY app/ app/
COPY data/ data/
COPY run.py .

EXPOSE 5000

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')"

CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:5000", "--graceful-timeout", "10", "app:create_app()"]
