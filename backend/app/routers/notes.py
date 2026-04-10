from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth.security import get_current_user
from app.services.notes import (
    create_note_revision_save_job,
    create_note_save_job,
    get_note_detail,
    get_note_save_job,
    launch_note_revision_save_job,
    launch_note_save_job,
    list_notes,
)


router = APIRouter(prefix="/api/notes", tags=["notes"])


class NoteSourcePayload(BaseModel):
    index: int = Field(default=0)
    doc_id: str = Field(default="")
    filename: str = Field(default="")
    chunk_index: int = Field(default=0)
    knowledge_space: str = Field(default="")
    tags: str = Field(default="")
    source_type: str = Field(default="text")
    source_label: str = Field(default="")
    source_page: int = Field(default=0)
    section_title: str = Field(default="")
    heading_path: str = Field(default="")
    image_count: int = Field(default=0)
    summary: str = Field(default="")


class NoteSaveRequest(BaseModel):
    session_id: str = Field(default="")
    message_id: str = Field(default="")
    query: str = Field(default="")
    answer: str = Field(default="")
    knowledge_space: str = Field(default="")
    sources: list[NoteSourcePayload] = Field(default_factory=list)


class NoteRevisionSaveRequest(BaseModel):
    answer: str = Field(default="")
    sources: list[NoteSourcePayload] = Field(default_factory=list)


def _resolve_user_id(current_user: dict) -> str:
    user_id = str(current_user.get("id") or current_user.get("user_id") or "").strip()
    if not user_id:
        raise HTTPException(status_code=401, detail="当前用户不存在")
    return user_id


@router.post("/save-jobs")
async def submit_note_save_job(
    payload: NoteSaveRequest,
    current_user: dict = Depends(get_current_user),
):
    user_id = _resolve_user_id(current_user)
    query = payload.query.strip()
    answer = payload.answer.strip()
    if not query:
        raise HTTPException(status_code=400, detail="问题不能为空")
    if not answer:
        raise HTTPException(status_code=400, detail="回答不能为空")

    created = create_note_save_job(
        user_id=user_id,
        session_id=payload.session_id.strip() or "default",
        message_id=payload.message_id.strip() or "",
        query=query,
        answer=answer,
        knowledge_space=payload.knowledge_space.strip(),
        sources=[item.model_dump() for item in payload.sources],
    )
    launch_note_save_job(
        job_id=created["job"]["job_id"],
        note_id=created["note"]["note_id"],
        user_id=user_id,
        query=created["payload"]["query"],
        answer=created["payload"]["answer"],
        sources=created["payload"]["sources"],
    )
    return {
        "success": True,
        "job": created["job"],
        "note": created["note"],
    }


@router.get("/save-jobs/{job_id}")
async def get_note_job_status(
    job_id: str,
    current_user: dict = Depends(get_current_user),
):
    job = get_note_save_job(user_id=_resolve_user_id(current_user), job_id=job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="笔记保存任务不存在")
    return {"job": job}


@router.get("")
async def get_note_list(current_user: dict = Depends(get_current_user)):
    return {"items": list_notes(user_id=_resolve_user_id(current_user))}


@router.get("/{note_id}")
async def get_note(note_id: str, current_user: dict = Depends(get_current_user)):
    detail = get_note_detail(user_id=_resolve_user_id(current_user), note_id=note_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="笔记不存在")
    return detail


@router.post("/{note_id}/revision-save-jobs")
async def submit_note_revision_save_job_route(
    note_id: str,
    payload: NoteRevisionSaveRequest,
    current_user: dict = Depends(get_current_user),
):
    user_id = _resolve_user_id(current_user)
    answer = payload.answer.strip()
    if not answer:
        raise HTTPException(status_code=400, detail="候选答案不能为空")

    created = create_note_revision_save_job(
        user_id=user_id,
        note_id=note_id.strip(),
        answer=answer,
        sources=[item.model_dump() for item in payload.sources],
    )
    if created is None:
        raise HTTPException(status_code=404, detail="笔记不存在")

    launch_note_revision_save_job(
        job_id=created["job"]["job_id"],
        note_id=note_id.strip(),
        user_id=user_id,
        query=created["payload"]["query"],
        answer=created["payload"]["answer"],
        sources=created["payload"]["sources"],
    )
    return {
        "success": True,
        "job": created["job"],
    }