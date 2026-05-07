from __future__ import annotations

import asyncio
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from app.agent.rag_agent import _run_auxiliary_completion
from app.auth.database import get_connection


NOTE_STATUS_PENDING = "pending"
NOTE_STATUS_READY = "ready"
NOTE_STATUS_FAILED = "failed"

NOTE_JOB_STATUS_PENDING = "pending"
NOTE_JOB_STATUS_RUNNING = "running"
NOTE_JOB_STATUS_SUCCEEDED = "succeeded"
NOTE_JOB_STATUS_FAILED = "failed"

_save_tasks: dict[str, asyncio.Task[None]] = {}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _truncate_text(value: str, limit: int) -> str:
    normalized = " ".join(str(value or "").strip().split())
    if len(normalized) <= limit:
        return normalized
    if limit <= 1:
        return normalized[:limit]
    return normalized[: limit - 1].rstrip() + "…"


def _fallback_title(query: str) -> str:
    normalized = _truncate_text(query, 28)
    return normalized or "未命名笔记"


def _sanitize_title(title: str, query: str) -> str:
    normalized = " ".join(str(title or "").replace("\n", " ").split())
    normalized = normalized.strip("#*-_ ")
    normalized = _truncate_text(normalized, 28)
    return normalized or _fallback_title(query)


def generate_note_title(query: str, answer: str, sources: list[dict[str, Any]]) -> str:
    source_hints = []
    for item in list(sources or [])[:3]:
        label = str(item.get("source_label", "") or "").strip()
        filename = str(item.get("filename", "") or "").strip()
        summary = _truncate_text(str(item.get("summary", "") or ""), 80)
        parts = [part for part in (filename, label, summary) if part]
        if parts:
            source_hints.append(" | ".join(parts))

    source_hint_text = "\n".join(source_hints) if source_hints else "无"
    system_prompt = (
        "你是一个知识型笔记标题生成器。"
        "请基于用户问题、AI回答和来源线索，生成一个简洁、明确、适合归档的中文标题。"
        "要求：只输出标题本身，不加引号，不加序号，不加句号，长度尽量控制在 8 到 20 个汉字以内。"
    )
    user_prompt = (
        f"用户问题：\n{query.strip()}\n\n"
        f"AI回答：\n{_truncate_text(answer, 800)}\n\n"
        f"来源线索：\n{source_hint_text}"
    )
    generated = _run_auxiliary_completion(system_prompt, user_prompt)
    return _sanitize_title(generated, query)


def initialize_notes_db() -> None:
    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS notes (
                note_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                message_id TEXT NOT NULL,
                knowledge_space TEXT NOT NULL DEFAULT '',
                query TEXT NOT NULL,
                answer_excerpt TEXT NOT NULL DEFAULT '',
                title TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL,
                current_revision_id TEXT NOT NULL DEFAULT '',
                last_error TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS note_revisions (
                revision_id TEXT PRIMARY KEY,
                note_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                query TEXT NOT NULL,
                answer TEXT NOT NULL,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(note_id) REFERENCES notes(note_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS note_sources (
                note_source_id TEXT PRIMARY KEY,
                note_id TEXT NOT NULL,
                revision_id TEXT NOT NULL,
                source_rank INTEGER NOT NULL DEFAULT 0,
                doc_id TEXT NOT NULL DEFAULT '',
                filename TEXT NOT NULL DEFAULT '',
                chunk_index INTEGER NOT NULL DEFAULT 0,
                knowledge_space TEXT NOT NULL DEFAULT '',
                tags TEXT NOT NULL DEFAULT '',
                source_type TEXT NOT NULL DEFAULT 'text',
                source_label TEXT NOT NULL DEFAULT '',
                source_page INTEGER NOT NULL DEFAULT 0,
                section_title TEXT NOT NULL DEFAULT '',
                heading_path TEXT NOT NULL DEFAULT '',
                image_count INTEGER NOT NULL DEFAULT 0,
                summary TEXT NOT NULL DEFAULT '',
                FOREIGN KEY(note_id) REFERENCES notes(note_id) ON DELETE CASCADE,
                FOREIGN KEY(revision_id) REFERENCES note_revisions(revision_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS note_save_jobs (
                job_id TEXT PRIMARY KEY,
                note_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                status TEXT NOT NULL,
                error_message TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                completed_at TEXT NOT NULL DEFAULT '',
                FOREIGN KEY(note_id) REFERENCES notes(note_id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_notes_user_updated
            ON notes(user_id, updated_at DESC);

            CREATE INDEX IF NOT EXISTS idx_note_revisions_note_created
            ON note_revisions(note_id, created_at DESC);

            CREATE INDEX IF NOT EXISTS idx_note_sources_revision_rank
            ON note_sources(revision_id, source_rank ASC);

            CREATE INDEX IF NOT EXISTS idx_note_save_jobs_user_created
            ON note_save_jobs(user_id, created_at DESC);
            """
        )


def _serialize_note_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "note_id": str(row["note_id"]),
        "session_id": str(row["session_id"]),
        "message_id": str(row["message_id"]),
        "knowledge_space": str(row["knowledge_space"] or ""),
        "query": str(row["query"] or ""),
        "answer_excerpt": str(row["answer_excerpt"] or ""),
        "title": str(row["title"] or ""),
        "status": str(row["status"] or NOTE_STATUS_PENDING),
        "current_revision_id": str(row["current_revision_id"] or ""),
        "last_error": str(row["last_error"] or ""),
        "created_at": str(row["created_at"] or ""),
        "updated_at": str(row["updated_at"] or ""),
    }


def _serialize_job_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "job_id": str(row["job_id"]),
        "note_id": str(row["note_id"]),
        "status": str(row["status"] or NOTE_JOB_STATUS_PENDING),
        "error_message": str(row["error_message"] or ""),
        "created_at": str(row["created_at"] or ""),
        "updated_at": str(row["updated_at"] or ""),
        "completed_at": str(row["completed_at"] or ""),
    }


def create_note_save_job(
    *,
    user_id: str,
    session_id: str,
    message_id: str,
    query: str,
    answer: str,
    knowledge_space: str,
    sources: list[dict[str, Any]],
) -> dict[str, Any]:
    note_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    now = _utc_now().isoformat()
    normalized_query = str(query or "").strip()
    normalized_answer = str(answer or "").strip()
    normalized_knowledge_space = str(knowledge_space or "").strip()
    answer_excerpt = _truncate_text(normalized_answer, 140)

    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO notes (
                note_id, user_id, session_id, message_id, knowledge_space, query,
                answer_excerpt, title, status, current_revision_id, last_error, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '', '', ?, ?)
            """,
            (
                note_id,
                user_id,
                session_id,
                message_id,
                normalized_knowledge_space,
                normalized_query,
                answer_excerpt,
                "",
                NOTE_STATUS_PENDING,
                now,
                now,
            ),
        )
        connection.execute(
            """
            INSERT INTO note_save_jobs (
                job_id, note_id, user_id, status, error_message, created_at, updated_at, completed_at
            ) VALUES (?, ?, ?, ?, '', ?, ?, '')
            """,
            (
                job_id,
                note_id,
                user_id,
                NOTE_JOB_STATUS_PENDING,
                now,
                now,
            ),
        )

    return {
        "job": {
            "job_id": job_id,
            "note_id": note_id,
            "status": NOTE_JOB_STATUS_PENDING,
            "error_message": "",
            "created_at": now,
            "updated_at": now,
            "completed_at": "",
        },
        "note": {
            "note_id": note_id,
            "session_id": session_id,
            "message_id": message_id,
            "knowledge_space": normalized_knowledge_space,
            "query": normalized_query,
            "answer_excerpt": answer_excerpt,
            "title": "",
            "status": NOTE_STATUS_PENDING,
            "current_revision_id": "",
            "last_error": "",
            "created_at": now,
            "updated_at": now,
        },
        "payload": {
            "query": normalized_query,
            "answer": normalized_answer,
            "knowledge_space": normalized_knowledge_space,
            "sources": list(sources or []),
        },
    }


def create_note_revision_save_job(
    *,
    user_id: str,
    note_id: str,
    answer: str,
    sources: list[dict[str, Any]],
) -> dict[str, Any] | None:
    job_id = str(uuid.uuid4())
    now = _utc_now().isoformat()
    normalized_answer = str(answer or "").strip()

    with get_connection() as connection:
        note_row = connection.execute(
            """
            SELECT note_id, query, status
            FROM notes
            WHERE user_id = ? AND note_id = ?
            LIMIT 1
            """,
            (user_id, note_id),
        ).fetchone()
        if note_row is None:
            return None

        connection.execute(
            """
            INSERT INTO note_save_jobs (
                job_id, note_id, user_id, status, error_message, created_at, updated_at, completed_at
            ) VALUES (?, ?, ?, ?, '', ?, ?, '')
            """,
            (
                job_id,
                note_id,
                user_id,
                NOTE_JOB_STATUS_PENDING,
                now,
                now,
            ),
        )

    return {
        "job": {
            "job_id": job_id,
            "note_id": note_id,
            "status": NOTE_JOB_STATUS_PENDING,
            "error_message": "",
            "created_at": now,
            "updated_at": now,
            "completed_at": "",
        },
        "payload": {
            "query": str(note_row["query"] or "").strip(),
            "answer": normalized_answer,
            "sources": list(sources or []),
        },
    }


def get_note_save_job(*, user_id: str, job_id: str) -> dict[str, Any] | None:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT job_id, note_id, status, error_message, created_at, updated_at, completed_at
            FROM note_save_jobs
            WHERE user_id = ? AND job_id = ?
            LIMIT 1
            """,
            (user_id, job_id),
        ).fetchone()

    if row is None:
        return None
    return _serialize_job_row(row)


def list_notes(*, user_id: str) -> list[dict[str, Any]]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT note_id, session_id, message_id, knowledge_space, query, answer_excerpt,
                   title, status, current_revision_id, last_error, created_at, updated_at
            FROM notes
            WHERE user_id = ?
            ORDER BY updated_at DESC, created_at DESC
            """,
            (user_id,),
        ).fetchall()

    return [_serialize_note_row(row) for row in rows]


def get_note_detail(*, user_id: str, note_id: str) -> dict[str, Any] | None:
    with get_connection() as connection:
        note_row = connection.execute(
            """
            SELECT note_id, session_id, message_id, knowledge_space, query, answer_excerpt,
                   title, status, current_revision_id, last_error, created_at, updated_at
            FROM notes
            WHERE user_id = ? AND note_id = ?
            LIMIT 1
            """,
            (user_id, note_id),
        ).fetchone()
        if note_row is None:
            return None

        note = _serialize_note_row(note_row)
        revision_id = note["current_revision_id"]
        revision = None
        sources: list[dict[str, Any]] = []

        if revision_id:
            revision_row = connection.execute(
                """
                SELECT revision_id, query, answer, title, created_at
                FROM note_revisions
                WHERE note_id = ? AND revision_id = ?
                LIMIT 1
                """,
                (note_id, revision_id),
            ).fetchone()
            if revision_row is not None:
                revision = {
                    "revision_id": str(revision_row["revision_id"]),
                    "query": str(revision_row["query"] or ""),
                    "answer": str(revision_row["answer"] or ""),
                    "title": str(revision_row["title"] or ""),
                    "created_at": str(revision_row["created_at"] or ""),
                }
                source_rows = connection.execute(
                    """
                    SELECT source_rank, doc_id, filename, chunk_index, knowledge_space, tags,
                           source_type, source_label, source_page, section_title, heading_path,
                           image_count, summary
                    FROM note_sources
                    WHERE note_id = ? AND revision_id = ?
                    ORDER BY source_rank ASC
                    """,
                    (note_id, revision_id),
                ).fetchall()
                sources = [
                    {
                        "index": int(row["source_rank"] or 0),
                        "doc_id": str(row["doc_id"] or ""),
                        "filename": str(row["filename"] or ""),
                        "chunk_index": int(row["chunk_index"] or 0),
                        "knowledge_space": str(row["knowledge_space"] or ""),
                        "tags": str(row["tags"] or ""),
                        "source_type": str(row["source_type"] or "text"),
                        "source_label": str(row["source_label"] or ""),
                        "source_page": int(row["source_page"] or 0),
                        "section_title": str(row["section_title"] or ""),
                        "heading_path": str(row["heading_path"] or ""),
                        "image_count": int(row["image_count"] or 0),
                        "summary": str(row["summary"] or ""),
                    }
                    for row in source_rows
                ]

    return {
        "note": note,
        "current_revision": revision,
        "sources": sources,
    }


def _mark_job_status(
    *,
    job_id: str,
    status: str,
    error_message: str = "",
    completed: bool = False,
) -> None:
    now = _utc_now().isoformat()
    completed_at = now if completed else ""
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE note_save_jobs
            SET status = ?, error_message = ?, updated_at = ?, completed_at = ?
            WHERE job_id = ?
            """,
            (status, str(error_message or "").strip(), now, completed_at, job_id),
        )


def _write_note_revision(
    *,
    note_id: str,
    user_id: str,
    query: str,
    answer: str,
    title: str,
    sources: list[dict[str, Any]],
) -> None:
    now = _utc_now().isoformat()
    with get_connection() as connection:
        note_row = connection.execute(
            """
            SELECT current_revision_id
            FROM notes
            WHERE note_id = ? AND user_id = ?
            LIMIT 1
            """,
            (note_id, user_id),
        ).fetchone()
        if note_row is None:
            raise ValueError("笔记不存在")

        revision_id = str(note_row["current_revision_id"] or "").strip()
        if revision_id:
            connection.execute(
                """
                UPDATE note_revisions
                SET query = ?, answer = ?, title = ?, created_at = ?
                WHERE revision_id = ? AND note_id = ? AND user_id = ?
                """,
                (query, answer, title, now, revision_id, note_id, user_id),
            )
            connection.execute(
                """
                DELETE FROM note_sources
                WHERE note_id = ? AND revision_id = ?
                """,
                (note_id, revision_id),
            )
        else:
            revision_id = str(uuid.uuid4())
            connection.execute(
                """
                INSERT INTO note_revisions (
                    revision_id, note_id, user_id, query, answer, title, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (revision_id, note_id, user_id, query, answer, title, now),
            )

        for index, source in enumerate(list(sources or []), 1):
            connection.execute(
                """
                INSERT INTO note_sources (
                    note_source_id, note_id, revision_id, source_rank, doc_id, filename,
                    chunk_index, knowledge_space, tags, source_type, source_label,
                    source_page, section_title, heading_path, image_count, summary
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    note_id,
                    revision_id,
                    index,
                    str(source.get("doc_id", "") or ""),
                    str(source.get("filename", "") or ""),
                    int(source.get("chunk_index", 0) or 0),
                    str(source.get("knowledge_space", "") or ""),
                    str(source.get("tags", "") or ""),
                    str(source.get("source_type", "text") or "text"),
                    str(source.get("source_label", "") or ""),
                    int(source.get("source_page", 0) or 0),
                    str(source.get("section_title", "") or ""),
                    str(source.get("heading_path", "") or ""),
                    int(source.get("image_count", 0) or 0),
                    str(source.get("summary", "") or ""),
                ),
            )

        connection.execute(
            """
            UPDATE notes
            SET title = ?, answer_excerpt = ?, status = ?, current_revision_id = ?,
                last_error = '', updated_at = ?
            WHERE note_id = ?
            """,
            (
                title,
                _truncate_text(answer, 140),
                NOTE_STATUS_READY,
                revision_id,
                now,
                note_id,
            ),
        )


async def _process_note_save_job(
    *,
    job_id: str,
    note_id: str,
    user_id: str,
    query: str,
    answer: str,
    sources: list[dict[str, Any]],
) -> None:
    _mark_job_status(job_id=job_id, status=NOTE_JOB_STATUS_RUNNING)
    try:
        title = await asyncio.to_thread(generate_note_title, query, answer, sources)
        await asyncio.to_thread(
            _write_note_revision,
            note_id=note_id,
            user_id=user_id,
            query=query,
            answer=answer,
            title=title,
            sources=sources,
        )
        _mark_job_status(job_id=job_id, status=NOTE_JOB_STATUS_SUCCEEDED, completed=True)
    except Exception as exc:
        now = _utc_now().isoformat()
        error_message = str(exc or "笔记保存失败").strip() or "笔记保存失败"
        with get_connection() as connection:
            connection.execute(
                """
                UPDATE notes
                SET status = ?, last_error = ?, updated_at = ?
                WHERE note_id = ?
                """,
                (NOTE_STATUS_FAILED, error_message, now, note_id),
            )
        _mark_job_status(
            job_id=job_id,
            status=NOTE_JOB_STATUS_FAILED,
            error_message=error_message,
            completed=True,
        )
        raise


async def _process_note_revision_save_job(
    *,
    job_id: str,
    note_id: str,
    user_id: str,
    query: str,
    answer: str,
    sources: list[dict[str, Any]],
) -> None:
    _mark_job_status(job_id=job_id, status=NOTE_JOB_STATUS_RUNNING)
    try:
        title = await asyncio.to_thread(generate_note_title, query, answer, sources)
        await asyncio.to_thread(
            _write_note_revision,
            note_id=note_id,
            user_id=user_id,
            query=query,
            answer=answer,
            title=title,
            sources=sources,
        )
        _mark_job_status(job_id=job_id, status=NOTE_JOB_STATUS_SUCCEEDED, completed=True)
    except Exception as exc:
        error_message = str(exc or "笔记版本保存失败").strip() or "笔记版本保存失败"
        _mark_job_status(
            job_id=job_id,
            status=NOTE_JOB_STATUS_FAILED,
            error_message=error_message,
            completed=True,
        )
        raise


def launch_note_save_job(
    *,
    job_id: str,
    note_id: str,
    user_id: str,
    query: str,
    answer: str,
    sources: list[dict[str, Any]],
) -> None:
    task = asyncio.create_task(
        _process_note_save_job(
            job_id=job_id,
            note_id=note_id,
            user_id=user_id,
            query=query,
            answer=answer,
            sources=list(sources or []),
        )
    )
    _save_tasks[job_id] = task

    def _cleanup(_: asyncio.Task[None]) -> None:
        _save_tasks.pop(job_id, None)

    task.add_done_callback(_cleanup)


def launch_note_revision_save_job(
    *,
    job_id: str,
    note_id: str,
    user_id: str,
    query: str,
    answer: str,
    sources: list[dict[str, Any]],
) -> None:
    task = asyncio.create_task(
        _process_note_revision_save_job(
            job_id=job_id,
            note_id=note_id,
            user_id=user_id,
            query=query,
            answer=answer,
            sources=list(sources or []),
        )
    )
    _save_tasks[job_id] = task

    def _cleanup(_: asyncio.Task[None]) -> None:
        _save_tasks.pop(job_id, None)

    task.add_done_callback(_cleanup)