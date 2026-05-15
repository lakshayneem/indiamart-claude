from dotenv import load_dotenv
load_dotenv()

import json
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from .skill_registry import (
    SkillAlreadyExistsError,
    SkillNotFoundError,
    create_pending_skill,
    delete_skill,
    list_skills,
    load_skill_metadata,
    set_skill_status,
)
from .skill_runner import run_skill

app = FastAPI(title="IM Agentic OS — Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok"}


# ── Skill catalog ─────────────────────────────────────────────────────────────
@app.get("/skills")
def get_skills(
    team: Optional[str] = None,
    category: Optional[str] = None,
    search: Optional[str] = None,
):
    """List approved skills (the catalog visible to end users)."""
    return list_skills(status="approved", team=team, category=category, search=search)


@app.get("/skills/all")
def get_all_skills(status: Optional[str] = None):
    """List every skill regardless of status (admin/creator view)."""
    return list_skills(status=status)


@app.get("/skills/{skill_id}")
def get_skill(skill_id: str):
    try:
        return load_skill_metadata(skill_id)
    except SkillNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


class CreateSkillRequest(BaseModel):
    metadata: dict
    skill_md: str = ""


@app.post("/skills", status_code=201)
def create_skill(payload: CreateSkillRequest):
    try:
        return create_pending_skill(payload.metadata, payload.skill_md)
    except SkillAlreadyExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


class ApproveRequest(BaseModel):
    pass


class RejectRequest(BaseModel):
    reason: str = ""


@app.post("/skills/{skill_id}/approve")
def approve_skill(skill_id: str):
    try:
        return set_skill_status(skill_id, "approved")
    except SkillNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/skills/{skill_id}/reject")
def reject_skill(skill_id: str, payload: RejectRequest):
    try:
        return set_skill_status(skill_id, "rejected", payload.reason)
    except SkillNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.delete("/skills/{skill_id}", status_code=204)
def remove_skill(skill_id: str):
    try:
        delete_skill(skill_id)
    except SkillNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── Skill execution ───────────────────────────────────────────────────────────
@app.post("/run-skill")
async def run_skill_endpoint(
    skill_id: str = Form(...),
    inputs: str = Form("{}"),
    files: list[UploadFile] = File(default=[]),
):
    """
    Multipart endpoint.
      - skill_id: form field (required)
      - inputs: JSON-encoded string of text/dropdown/textarea inputs
      - files: zero or more uploaded files; each is written to the sandbox workspace
    """
    try:
        inputs_dict = json.loads(inputs) if inputs else {}
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"inputs must be valid JSON: {e}")

    file_bytes: dict[str, bytes] = {}
    for f in files or []:
        if not f or not f.filename:
            continue
        file_bytes[f.filename] = await f.read()

    try:
        result = await run_in_threadpool(
            run_skill, skill_id, inputs_dict, file_bytes
        )
        return {
            "status": "success",
            "skill_id": skill_id,
            "output": result["output"],
            "output_files": result["output_files"],
            "output_files_binary": result.get("output_files_binary", {}),
            "execution_time_seconds": result["execution_time"],
            "cost_usd": result.get("cost_usd", 0.0),
            "source": "live",
        }
    except SkillNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        return {
            "status": "error",
            "skill_id": skill_id,
            "output": "",
            "error": str(e),
            "execution_time_seconds": 0,
            "source": "live",
        }
