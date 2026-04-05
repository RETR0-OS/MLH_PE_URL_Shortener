"""Redis cache-aside with circuit-breaker fallback to DB."""
import json
import logging
import time

from app.utils.secrets import read_secret

logger = logging.getLogger(__name__)

_redis_client = None
_circuit_open = False
_circuit_open_until = 0.0
CIRCUIT_RESET_SECONDS = 30


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

        host = read_secret("redis_host", "redis")
        port = int(read_secret("redis_port", "6379"))
        password = read_secret("redis_password", None) or None
        _redis_client = redis.Redis(
            host=host,
            port=port,
            password=password,
            decode_responses=True,
            socket_connect_timeout=0.5,
            socket_timeout=0.5,
            health_check_interval=30,
        )
        _redis_client.ping()
        return _redis_client
    except Exception:
        logger.warning("Redis unavailable, falling back to DB-only")
        _redis_client = None
        _open_circuit()
        return None


def warm_up():
    """Eagerly establish the Redis connection at startup."""
    get_redis()


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
    """Delete keys matching a pattern using SCAN + pipeline. Fails silently."""
    r = get_redis()
    if r is None:
        return
    try:
        cursor = 0
        pipe = r.pipeline()
        while True:
            cursor, keys = r.scan(cursor, match=pattern, count=100)
            for key in keys:
                pipe.delete(key)
            if cursor == 0:
                break
        pipe.execute()
    except Exception:
        logger.warning("Redis DELETE pattern failed for %s", pattern)
        _open_circuit()
