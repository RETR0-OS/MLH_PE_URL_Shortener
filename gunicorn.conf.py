import multiprocessing

bind = "0.0.0.0:5000"
workers = min(4, multiprocessing.cpu_count() * 2 + 1)
threads = 2
worker_class = "gthread"

timeout = 30
graceful_timeout = 30
keepalive = 5

max_requests = 10000
max_requests_jitter = 1000

accesslog = "-"
errorlog = "-"
loglevel = "info"

preload_app = False

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
    """Called after a worker is forked – good place for per-worker init."""
    server.log.info("Worker spawned (pid=%s)", worker.pid)
