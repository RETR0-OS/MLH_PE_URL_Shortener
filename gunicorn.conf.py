bind = "0.0.0.0:5000"
workers = 2
threads = 4
worker_class = "gthread"

timeout = 30
graceful_timeout = 30
keepalive = 30

max_requests = 10000
max_requests_jitter = 1000

accesslog = "-"
errorlog = "-"
loglevel = "info"

logconfig_dict = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.json.JsonFormatter",
            "fmt": "%(asctime)s %(levelname)s %(name)s %(message)s",
            "rename_fields": {"asctime": "timestamp", "levelname": "level"},
            "datefmt": "%Y-%m-%dT%H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "stream": "ext://sys.stdout",
        },
    },
    "root": {
        "level": "INFO",
        "handlers": ["console"],
    },
    "loggers": {
        "gunicorn.error": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False,
        },
        "gunicorn.access": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False,
        },
    },
}

preload_app = True

forwarded_allow_ips = "*"
proxy_protocol = False
proxy_allow_from = "*"


def on_starting(server):
    """Log when Gunicorn master starts."""
    server.log.info("Gunicorn master starting (pid=%s)", server.pid)


def worker_int(worker):
    """Called when a worker receives SIGINT/SIGQUIT – drain gracefully."""
    worker.log.info("Worker %s shutting down gracefully", worker.pid)


def on_exit(server):
    """Called just before the master process exits."""
    server.log.info("Gunicorn master exiting")


def post_fork(server, worker):
    """Re-initialize DB pool in child to avoid sharing connections across fork."""
    server.log.info("Worker spawned (pid=%s), reinitializing DB pool", worker.pid)
    from app.database import db, _create_database

    if not db.is_closed():
        db.close()
    db.initialize(_create_database())
