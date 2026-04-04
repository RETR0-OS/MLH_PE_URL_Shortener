"""Redis cache-aside with circuit-breaker fallback to DB."""
import json
import logging
import os
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_redis_client = None
_circuit_open = False
_circuit_open_until = 0.0
CIRCUIT_RESET_SECONDS = 30


def _read_secret(name, default=None):
    secret_path = Path(f"/run/secrets/{name}")
    if secret_path.exists():
        return secret_path.read_text().strip()
    return os.environ.get(name.upper(), default)


def get_redis():
    """Return a Redis client, or None if Redis is unavailable."""
    global _redis_client, _circuit_open, _circuit_open_until

    if _circuit_open and time.monotonic() < _circuit_open_until:
        return None

    if _circuit_open:
        _circuit_open = False

    if _redis_client is not None:
        return _redis_client

    try:
        import redis

        host = _read_secret("redis_host", "redis")
        port = int(_read_secret("redis_port", "6379"))
        password = _read_secret("redis_password", None)
        _redis_client = redis.Redis(
            host=host,
            port=port,
            password=password,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        _redis_client.ping()
        return _redis_client
    except Exception:
        logger.warning("Redis unavailable, falling back to DB-only")
        _open_circuit()
        return None


def _open_circuit():
    global _circuit_open, _circuit_open_until
    _circuit_open = True
    _circuit_open_until = time.monotonic() + CIRCUIT_RESET_SECONDS


def cache_get(key):
    """Get a value from Redis. Returns None on miss or Redis failure."""
    r = get_redis()
    if r is None:
        return None
    try:
        val = r.get(key)
        if val is not None:
            return json.loads(val)
    except Exception:
        logger.warning("Redis GET failed for key=%s", key)
        _open_circuit()
    return None


def cache_set(key, value, ttl=300):
    """Set a value in Redis. Fails silently on Redis errors."""
    r = get_redis()
    if r is None:
        return
    try:
        r.setex(key, ttl, json.dumps(value))
    except Exception:
        logger.warning("Redis SET failed for key=%s", key)
        _open_circuit()


def cache_delete(key):
    """Delete a key from Redis. Fails silently on Redis errors."""
    r = get_redis()
    if r is None:
        return
    try:
        r.delete(key)
    except Exception:
        logger.warning("Redis DELETE failed for key=%s", key)
        _open_circuit()


def cache_delete_pattern(pattern):
    """Delete keys matching a pattern using SCAN (non-blocking). Fails silently."""
    r = get_redis()
    if r is None:
        return
    try:
        cursor = 0
        while True:
            cursor, keys = r.scan(cursor, match=pattern, count=100)
            if keys:
                r.delete(*keys)
            if cursor == 0:
                break
    except Exception:
        logger.warning("Redis DELETE pattern failed for %s", pattern)
        _open_circuit()
