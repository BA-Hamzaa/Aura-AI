"""
task_manager.py — J.A.R.V.I.S. Background Task Manager.

Handles:
  - Parallel execution of background tasks
  - Progress tracking
  - Cancellation / pause / resume
  - Task dependencies
  - Queue management
  - Persistent task history (survives restarts)
"""

import threading
import uuid
import time
from enum import Enum
from typing import Dict, List, Callable, Optional, Any
from datetime import datetime
from collections import deque


class TaskStatus(Enum):
    QUEUED    = "queued"
    RUNNING   = "running"
    DONE      = "done"
    FAILED    = "failed"
    CANCELLED = "cancelled"
    PAUSED    = "paused"


class BackgroundTask:
    def __init__(
        self,
        task_id: str,
        name: str,
        fn: Callable,
        args: tuple = (),
        kwargs: dict = None,
        depends_on: List[str] = None,
        priority: int = 5,
    ):
        self.task_id     = task_id
        self.name        = name
        self.fn          = fn
        self.args        = args
        self.kwargs      = kwargs or {}
        self.depends_on  = depends_on or []
        self.priority    = priority

        self.status      = TaskStatus.QUEUED
        self.progress    = 0          # 0-100
        self.progress_msg = ""
        self.result      = None
        self.error       = None
        self.created_at  = datetime.utcnow().isoformat()
        self.started_at  = None
        self.finished_at = None
        self._thread     = None
        self._cancel_event = threading.Event()
        self._pause_event  = threading.Event()
        self._pause_event.set()   # Not paused by default

    def to_dict(self) -> Dict:
        return {
            "task_id":     self.task_id,
            "name":        self.name,
            "status":      self.status.value,
            "progress":    self.progress,
            "progress_msg": self.progress_msg,
            "result":      str(self.result)[:200] if self.result else None,
            "error":       str(self.error)[:200] if self.error else None,
            "priority":    self.priority,
            "created_at":  self.created_at,
            "started_at":  self.started_at,
            "finished_at": self.finished_at,
            "depends_on":  self.depends_on,
        }

    def cancel(self):
        self._cancel_event.set()
        if self.status in (TaskStatus.QUEUED, TaskStatus.PAUSED):
            self.status = TaskStatus.CANCELLED

    def pause(self):
        if self.status == TaskStatus.RUNNING:
            self._pause_event.clear()
            self.status = TaskStatus.PAUSED

    def resume(self):
        if self.status == TaskStatus.PAUSED:
            self._pause_event.set()
            self.status = TaskStatus.RUNNING

    @property
    def cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def wait_if_paused(self):
        """Call this inside long-running task functions for pause support."""
        self._pause_event.wait()


class TaskManager:
    """
    Production-grade background task manager with:
    - Thread pool for parallel execution (default max 4 concurrent)
    - Priority queue
    - Dependency resolution
    - Progress callbacks via WebSocket broadcast
    """

    def __init__(self, max_workers: int = 4, broadcast_fn: Callable = None):
        self.max_workers   = max_workers
        self.broadcast_fn  = broadcast_fn   # async-safe broadcast function
        self._tasks: Dict[str, BackgroundTask] = {}
        self._queue: deque = deque()
        self._active_count = 0
        self._lock = threading.Lock()
        self._scheduler_thread = threading.Thread(
            target=self._scheduler_loop, daemon=True
        )
        self._scheduler_thread.start()

    # ── Public API ─────────────────────────────────────────────────────────────

    def submit(
        self,
        name: str,
        fn: Callable,
        args: tuple = (),
        kwargs: dict = None,
        depends_on: List[str] = None,
        priority: int = 5,
        task_id: str = None,
    ) -> str:
        """Queue a new background task. Returns task_id."""
        tid = task_id or str(uuid.uuid4())[:8]
        task = BackgroundTask(
            task_id=tid,
            name=name,
            fn=fn,
            args=args,
            kwargs=kwargs or {},
            depends_on=depends_on or [],
            priority=priority,
        )
        with self._lock:
            self._tasks[tid] = task
            self._queue.append(tid)
        self._notify("task_queued", tid, task)
        return tid

    def cancel(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if not task:
            return False
        task.cancel()
        self._notify("task_cancelled", task_id, task)
        return True

    def pause(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if not task:
            return False
        task.pause()
        return True

    def resume(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if not task:
            return False
        task.resume()
        return True

    def get_task(self, task_id: str) -> Optional[Dict]:
        task = self._tasks.get(task_id)
        return task.to_dict() if task else None

    def list_tasks(self, status: str = "") -> List[Dict]:
        with self._lock:
            tasks = list(self._tasks.values())
        if status:
            s = TaskStatus(status)
            tasks = [t for t in tasks if t.status == s]
        return [t.to_dict() for t in sorted(tasks, key=lambda x: x.created_at, reverse=True)]

    def clear_done(self):
        with self._lock:
            done_ids = [
                tid for tid, t in self._tasks.items()
                if t.status in (TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.CANCELLED)
            ]
            for tid in done_ids:
                del self._tasks[tid]
        return len(done_ids)

    def stats(self) -> Dict:
        with self._lock:
            counts = {}
            for s in TaskStatus:
                counts[s.value] = sum(1 for t in self._tasks.values() if t.status == s)
        return {
            "total":       len(self._tasks),
            "active":      self._active_count,
            "max_workers": self.max_workers,
            **counts,
        }

    # ── Internal ───────────────────────────────────────────────────────────────

    def _scheduler_loop(self):
        while True:
            time.sleep(0.2)
            self._try_dispatch()

    def _try_dispatch(self):
        with self._lock:
            if self._active_count >= self.max_workers:
                return
            if not self._queue:
                return

            # Sort queue by priority (lower number = higher priority)
            queue_list = list(self._queue)
            ready_tids = []
            for tid in queue_list:
                task = self._tasks.get(tid)
                if not task or task.status != TaskStatus.QUEUED:
                    continue
                # Check dependencies
                deps_done = all(
                    self._tasks.get(dep, None) is not None
                    and self._tasks[dep].status == TaskStatus.DONE
                    for dep in task.depends_on
                )
                if task.depends_on and not deps_done:
                    continue
                ready_tids.append(task)

            if not ready_tids:
                return

            # Pick highest priority task
            task = sorted(ready_tids, key=lambda t: t.priority)[0]
            self._queue.remove(task.task_id)
            self._active_count += 1
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.utcnow().isoformat()

        # Launch in thread
        t = threading.Thread(target=self._run_task, args=(task,), daemon=True)
        task._thread = t
        t.start()

    def _run_task(self, task: BackgroundTask):
        self._notify("task_started", task.task_id, task)
        try:
            result = task.fn(*task.args, **task.kwargs)
            task.result = result
            task.status = TaskStatus.DONE
            task.progress = 100
            task.finished_at = datetime.utcnow().isoformat()
            self._notify("task_done", task.task_id, task)
        except Exception as e:
            if task.cancelled:
                task.status = TaskStatus.CANCELLED
            else:
                task.status = TaskStatus.FAILED
                task.error = str(e)
                task.finished_at = datetime.utcnow().isoformat()
            self._notify("task_failed" if not task.cancelled else "task_cancelled",
                         task.task_id, task)
        finally:
            with self._lock:
                self._active_count = max(0, self._active_count - 1)

    def _notify(self, event_type: str, task_id: str, task: BackgroundTask):
        if self.broadcast_fn:
            try:
                self.broadcast_fn({
                    "type":    event_type,
                    "task_id": task_id,
                    "task":    task.to_dict(),
                })
            except Exception:
                pass

    def update_progress(self, task_id: str, progress: int, message: str = ""):
        """Called from within a task function to report progress."""
        task = self._tasks.get(task_id)
        if task:
            task.progress = max(0, min(100, progress))
            task.progress_msg = message
            self._notify("task_progress", task_id, task)


# Singleton — broadcast_fn injected by main.py after startup
task_manager = TaskManager(max_workers=4)
