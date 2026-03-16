import threading
import uuid
from copy import deepcopy
from datetime import datetime, timedelta, timezone

from app.config import settings


_jobs: dict[str, dict] = {}
_lock = threading.Lock()


def _terminal_job_retention() -> timedelta:
    return timedelta(hours=max(int(settings.knowledge_base_job_retention_hours or 0), 0))


def _max_job_history() -> int:
    return max(int(settings.knowledge_base_job_history_limit or 0), 1)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None

    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _prune_jobs_locked() -> None:
    now = datetime.now(timezone.utc)
    retention = _terminal_job_retention()
    expired_job_ids: list[str] = []

    for job_id, snapshot in _jobs.items():
        if snapshot.get("status") not in {"completed", "failed"}:
            continue

        finished_at = _parse_iso_timestamp(snapshot.get("finished_at"))
        if finished_at is None:
            continue
        if now - finished_at >= retention:
            expired_job_ids.append(job_id)

    for job_id in expired_job_ids:
        _jobs.pop(job_id, None)

    overflow = len(_jobs) - _max_job_history()
    if overflow <= 0:
        return

    terminal_jobs = sorted(
        (
            (job_id, snapshot)
            for job_id, snapshot in _jobs.items()
            if snapshot.get("status") in {"completed", "failed"}
        ),
        key=lambda item: item[1].get("finished_at") or item[1].get("updated_at") or item[1].get("created_at") or "",
    )

    for job_id, _ in terminal_jobs[:overflow]:
        _jobs.pop(job_id, None)


def create_job(
    *,
    job_type: str,
    total_documents: int = 0,
    total_chunks: int = 0,
    message: str = "任务已创建，等待执行。",
) -> dict:
    job_id = str(uuid.uuid4())
    snapshot = {
        "job_id": job_id,
        "job_type": job_type,
        "status": "queued",
        "message": message,
        "error_message": "",
        "current_document": "",
        "total_documents": int(total_documents or 0),
        "processed_documents": 0,
        "total_chunks": int(total_chunks or 0),
        "processed_chunks": 0,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "finished_at": "",
        "result": {},
    }

    with _lock:
        _prune_jobs_locked()
        _jobs[job_id] = snapshot

    return deepcopy(snapshot)


def update_job(job_id: str, **fields) -> dict | None:
    with _lock:
        _prune_jobs_locked()
        snapshot = _jobs.get(job_id)
        if snapshot is None:
            return None

        for key, value in fields.items():
            if key in snapshot:
                snapshot[key] = value
        snapshot["updated_at"] = _now_iso()
        return deepcopy(snapshot)


def advance_job(
    job_id: str,
    *,
    documents: int = 0,
    chunks: int = 0,
    total_chunks_delta: int = 0,
    message: str | None = None,
    current_document: str | None = None,
) -> dict | None:
    with _lock:
        _prune_jobs_locked()
        snapshot = _jobs.get(job_id)
        if snapshot is None:
            return None

        snapshot["processed_documents"] = int(snapshot.get("processed_documents", 0) or 0) + int(documents or 0)
        snapshot["processed_chunks"] = int(snapshot.get("processed_chunks", 0) or 0) + int(chunks or 0)
        snapshot["total_chunks"] = int(snapshot.get("total_chunks", 0) or 0) + int(total_chunks_delta or 0)
        if message is not None:
            snapshot["message"] = message
        if current_document is not None:
            snapshot["current_document"] = current_document
        snapshot["updated_at"] = _now_iso()
        return deepcopy(snapshot)


def complete_job(job_id: str, *, message: str, result: dict | None = None) -> dict | None:
    with _lock:
        _prune_jobs_locked()
        snapshot = _jobs.get(job_id)
        if snapshot is None:
            return None

        finished_at = _now_iso()
        snapshot["status"] = "completed"
        snapshot["message"] = message
        snapshot["current_document"] = ""
        snapshot["result"] = deepcopy(result or {})
        snapshot["finished_at"] = finished_at
        snapshot["updated_at"] = finished_at
        return deepcopy(snapshot)


def fail_job(job_id: str, *, error_message: str) -> dict | None:
    with _lock:
        _prune_jobs_locked()
        snapshot = _jobs.get(job_id)
        if snapshot is None:
            return None

        finished_at = _now_iso()
        snapshot["status"] = "failed"
        snapshot["message"] = "任务执行失败。"
        snapshot["error_message"] = error_message
        snapshot["finished_at"] = finished_at
        snapshot["updated_at"] = finished_at
        return deepcopy(snapshot)


def get_job(job_id: str) -> dict | None:
    with _lock:
        _prune_jobs_locked()
        snapshot = _jobs.get(job_id)
        return deepcopy(snapshot) if snapshot is not None else None