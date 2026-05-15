from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from .skill_runner import run_skill
from .skill_registry import SkillNotFoundError

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class RunSkillRequest(BaseModel):
    skill_id: str
    inputs: dict


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/run-skill")
async def run_skill_endpoint(payload: RunSkillRequest):
    try:
        result = await run_in_threadpool(run_skill, payload.skill_id, payload.inputs)
        return {
            "status": "success",
            "skill_id": payload.skill_id,
            "output": result["output"],
            "output_files": result["output_files"],
            "execution_time_seconds": result["execution_time"],
            "source": "live",
        }
    except SkillNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        return {
            "status": "error",
            "skill_id": payload.skill_id,
            "output": "",
            "error": str(e),
            "execution_time_seconds": 0,
        }
