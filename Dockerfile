FROM python:3.13-slim AS builder

WORKDIR /build
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY pyproject.toml .
RUN python3 -c "\
import tomllib, pathlib;\
deps=tomllib.loads(pathlib.Path('pyproject.toml').read_text())['project']['dependencies'];\
pathlib.Path('requirements.txt').write_text('\n'.join(deps))" && \
    uv pip install --system --no-cache-dir -r requirements.txt gunicorn

FROM python:3.13-slim

RUN groupadd -r app && useradd -r -g app -d /app app
WORKDIR /app

COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin/gunicorn /usr/local/bin/gunicorn

COPY . .
RUN chown -R app:app /app
USER app

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')" || exit 1

CMD ["gunicorn", "-c", "gunicorn.conf.py", "run:app"]
