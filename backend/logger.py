"""
logger.py — Structured production logging for J.A.R.V.I.S.

Logs everything to:
  - Console (colored, minimal)
  - File: logs/jarvis.log (rotating, detailed JSON)
  - In-memory ring buffer (for live log tab in HUD)
"""

import os
import json
import logging
import logging.handlers
import threading
import time
from collections import deque
from datetime import datetime
from typing import Dict, List, Optional, Any

LOGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs")
os.makedirs(LOGS_DIR, exist_ok=True)

LOG_FILE = os.path.join(LOGS_DIR, "jarvis.log")
MAX_MEMORY_ENTRIES = 500


# ── JSON Formatter ────────────────────────────────────────────────────────────

class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {
            "ts":      datetime.utcnow().isoformat() + "Z",
            "level":   record.levelname,
            "logger":  record.name,
            "msg":     record.getMessage(),
        }
        if record.exc_info:
            data["exc"] = self.formatException(record.exc_info)
        return json.dumps(data, ensure_ascii=False)


# ── In-memory Ring Buffer Handler ─────────────────────────────────────────────

class RingBufferHandler(logging.Handler):
    def __init__(self, maxlen: int = MAX_MEMORY_ENTRIES):
        super().__init__()
        self._buffer: deque = deque(maxlen=maxlen)
        self._lock = threading.Lock()

    def emit(self, record: logging.LogRecord):
        entry = {
            "ts":      datetime.utcnow().isoformat() + "Z",
            "level":   record.levelname,
            "logger":  record.name.split(".")[-1],
            "msg":     self.format(record),
        }
        with self._lock:
            self._buffer.append(entry)

    def get_logs(self, limit: int = 100, level: str = "") -> List[Dict]:
        with self._lock:
            entries = list(self._buffer)
        if level:
            entries = [e for e in entries if e["level"] == level.upper()]
        return entries[-limit:]

    def clear(self):
        with self._lock:
            self._buffer.clear()


# ── Task Performance Logger ───────────────────────────────────────────────────

class PerformanceTracker:
    """Track AI response times, tool execution durations, API latencies."""

    def __init__(self):
        self._metrics: deque = deque(maxlen=1000)
        self._lock = threading.Lock()

    def record(self, operation: str, duration_ms: float, metadata: Dict = None):
        entry = {
            "ts":          datetime.utcnow().isoformat() + "Z",
            "operation":   operation,
            "duration_ms": round(duration_ms, 2),
            "meta":        metadata or {},
        }
        with self._lock:
            self._metrics.append(entry)

    def get_recent(self, limit: int = 50, operation: str = "") -> List[Dict]:
        with self._lock:
            entries = list(self._metrics)
        if operation:
            entries = [e for e in entries if e["operation"] == operation]
        return entries[-limit:]

    def stats(self, operation: str = "") -> Dict:
        entries = self.get_recent(500, operation)
        if not entries:
            return {}
        durations = [e["duration_ms"] for e in entries]
        return {
            "count":   len(durations),
            "avg_ms":  round(sum(durations) / len(durations), 1),
            "min_ms":  round(min(durations), 1),
            "max_ms":  round(max(durations), 1),
        }


# ── Context Manager for timing ────────────────────────────────────────────────

class Timer:
    def __init__(self, operation: str, tracker: "PerformanceTracker", metadata: Dict = None):
        self.operation = operation
        self.tracker   = tracker
        self.metadata  = metadata or {}
        self._start    = 0.0

    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, *args):
        elapsed_ms = (time.perf_counter() - self._start) * 1000
        self.tracker.record(self.operation, elapsed_ms, self.metadata)


# ── Setup ─────────────────────────────────────────────────────────────────────

_ring_handler = RingBufferHandler()
_perf_tracker = PerformanceTracker()


def setup_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers
    root.handlers.clear()

    # Console handler — simple
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%H:%M:%S"
    ))
    console.setLevel(logging.DEBUG)
    root.addHandler(console)

    # File handler — rotating JSON
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(JSONFormatter())
    file_handler.setLevel(logging.DEBUG)
    root.addHandler(file_handler)

    # Ring buffer handler — for HUD live log tab
    _ring_handler.setFormatter(logging.Formatter("%(message)s"))
    _ring_handler.setLevel(logging.DEBUG)
    root.addHandler(_ring_handler)

    # Quieten noisy third-party libs
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"jarvis.{name}")


def get_ring_buffer() -> RingBufferHandler:
    return _ring_handler


def get_perf_tracker() -> PerformanceTracker:
    return _perf_tracker


def timer(operation: str, metadata: Dict = None) -> Timer:
    return Timer(operation, _perf_tracker, metadata)


# Initialize on import
setup_logging()
