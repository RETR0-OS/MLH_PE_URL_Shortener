import atexit
import datetime
import json
import logging
import queue
import threading

logger = logging.getLogger(__name__)

_queue = queue.Queue()
_BATCH_SIZE = 50
_FLUSH_INTERVAL = 0.5
_shutdown = threading.Event()


class _FlushSentinel:
    def __init__(self):
        self.done = threading.Event()


def _flush(batch):
    if not batch:
        return
    try:
        from app.database import db
        from app.models.event import Event

        db.connect(reuse_if_open=True)
        with db.atomic():
            Event.insert_many(batch).execute()
    except Exception:
        logger.exception("Failed to flush %d events", len(batch))


def _writer_loop():
    batch = []
    while not _shutdown.is_set():
        try:
            item = _queue.get(timeout=_FLUSH_INTERVAL)
            if isinstance(item, _FlushSentinel):
                _flush(batch)
                batch = []
                item.done.set()
                continue
            batch.append(item)
            if len(batch) >= _BATCH_SIZE:
                _flush(batch)
                batch = []
        except queue.Empty:
            _flush(batch)
            batch = []
    while not _queue.empty():
        try:
            item = _queue.get_nowait()
            if isinstance(item, _FlushSentinel):
                item.done.set()
            else:
                batch.append(item)
        except queue.Empty:
            break
    _flush(batch)


_writer_thread = threading.Thread(target=_writer_loop, daemon=True)
_writer_thread.start()


def _shutdown_writer():
    _shutdown.set()
    _writer_thread.join(timeout=5)


atexit.register(_shutdown_writer)


def log_event(url_id, user_id, event_type, short_code="", original_url="", extra=None):
    details = {"short_code": short_code, "original_url": original_url}
    if extra:
        details.update(extra)
    _queue.put({
        "url_id": url_id,
        "user_id": user_id,
        "event_type": event_type,
        "timestamp": datetime.datetime.now(),
        "details": json.dumps(details),
    })


def flush_pending():
    """Block until all queued events are flushed to the database."""
    sentinel = _FlushSentinel()
    _queue.put(sentinel)
    sentinel.done.wait(timeout=5)
