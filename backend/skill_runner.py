import base64
import html
import json
import logging
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

from daytona import Daytona, DaytonaConfig, CreateSandboxFromSnapshotParams

from .skill_registry import load_skill_md

SNAPSHOT = os.environ.get("SNAPSHOT_NAME", "company-claude-v1")
GLOBAL_CLAUDE_MD = Path(__file__).parent.parent / "snapshot" / "CLAUDE.md"
SKILLS_DIR = Path(__file__).parent.parent / "skills"
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

log = logging.getLogger(__name__)

_config = DaytonaConfig(
    api_key=os.environ["DAYTONA_API_KEY"],
    api_url=os.environ.get("DAYTONA_API_URL", "http://localhost:3000"),
)


def _format_task(inputs: dict) -> str:
    return "\n".join(f"{k}: {v}" for k, v in inputs.items())


_MENTION_RE = re.compile(r"<mention\b[^>]*>(.*?)</mention>", re.DOTALL | re.IGNORECASE)


def _clean_comment(text: str) -> str:
    return html.unescape(_MENTION_RE.sub(lambda m: m.group(1), text or ""))


def _fetch_gitlab_archive(repo_url: str) -> bytes:
    token = (os.environ.get("GITLAB_TOKEN") or "").strip()
    if not token:
        raise RuntimeError("GITLAB_TOKEN not set in env")
    repo_url = repo_url.strip().rstrip("/")
    if repo_url.endswith(".git"):
        repo_url = repo_url[:-4]
    parsed = urllib.parse.urlparse(repo_url)
    if parsed.scheme in ("http", "https"):
        base = f"{parsed.scheme}://{parsed.netloc}"
        project_path = parsed.path.lstrip("/")
    else:
        base = (os.environ.get("GITLAB_URL") or "").rstrip("/")
        if not base.startswith(("http://", "https://")):
            raise RuntimeError("repo_url is a bare path but GITLAB_URL base is missing/invalid")
        project_path = repo_url.lstrip("/")
    if not project_path:
        raise RuntimeError(f"could not extract project path from {repo_url!r}")
    encoded = urllib.parse.quote(project_path, safe="")
    url = f"{base}/api/v4/projects/{encoded}/repository/archive.tar.gz"
    req = urllib.request.Request(url, headers={"PRIVATE-TOKEN": token})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:300]
        raise RuntimeError(f"GitLab archive HTTP {e.code}: {body}") from e


def _op_get(path: str) -> dict:
    token = (os.environ.get("OPENPROJECT_TOKEN") or "").strip()
    if not token:
        raise RuntimeError("OPENPROJECT_TOKEN not set in env")
    base = (os.environ.get("OPENPROJECT_BASE_URL") or "https://project.intermesh.net").rstrip("/")
    auth = base64.b64encode(f"apikey:{token}".encode()).decode()
    url = f"{base}/api/v3{path}"
    req = urllib.request.Request(url, headers={"Authorization": f"Basic {auth}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:300]
        raise RuntimeError(f"OpenProject HTTP {e.code} on {path}: {body}") from e


def _fetch_openproject_ticket(wp_id) -> dict:
    wp = _op_get(f"/work_packages/{wp_id}")
    acts = _op_get(f"/work_packages/{wp_id}/activities?pageSize=1000")
    atts = _op_get(f"/work_packages/{wp_id}/attachments")
    elements = (acts.get("_embedded") or {}).get("elements") or []
    user_cache: dict[str, str] = {}
    for a in elements:
        if (a.get("comment") or {}).get("raw"):
            a["comment"]["raw"] = _clean_comment(a["comment"]["raw"])
        href = ((a.get("_links") or {}).get("user") or {}).get("href") or ""
        if href and href not in user_cache:
            try:
                user_cache[href] = _op_get(href.replace("/api/v3", "")).get("name") or "?"
            except Exception:
                user_cache[href] = "?"
        a["_resolved_author"] = user_cache.get(href, "?")
    return {
        "work_package": wp,
        "activities": elements,
        "attachments": (atts.get("_embedded") or {}).get("elements") or [],
    }


def _parse_output(raw: str) -> str:
    parts = []
    for line in raw.splitlines():
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("type") == "assistant":
            for block in ev.get("message", {}).get("content", []):
                if block.get("type") == "text":
                    parts.append(block["text"])
    return "".join(parts)


def _parse_cost(raw: str) -> float:
    for line in raw.splitlines():
        try:
            ev = json.loads(line)
            if ev.get("type") == "result":
                return ev.get("total_cost_usd") or 0.0
        except json.JSONDecodeError:
            continue
    return 0.0


def _parse_session_id(raw: str) -> str | None:
    for line in raw.splitlines():
        try:
            ev = json.loads(line)
            if ev.get("type") == "result":
                return ev.get("session_id") or None
        except json.JSONDecodeError:
            continue
    return None


def _download_outputs(sandbox) -> dict[str, bytes]:
    try:
        files = sandbox.fs.list_files("/home/daytona/output")
    except Exception:
        return {}

    result = {}
    for f in files:
        if f.is_dir:
            continue
        try:
            content = sandbox.fs.download_file(f"/home/daytona/output/{f.name}")
            if content:
                result[f.name] = content
        except Exception:
            pass
    return result


def _pick_main_output(output_files: dict[str, bytes], fallback: str) -> str:
    md_files = {k: v for k, v in output_files.items()
                if k.endswith(".md") and k != "run.log"}
    if md_files:
        return next(iter(md_files.values())).decode(errors="replace")
    return fallback


def stream_skill(
    skill_id: str,
    inputs: dict,
    files: dict[str, bytes] | None = None,
):
    """
    Generator that runs a skill and yields stage events.
    Every event is also appended to logs/<run_id>.jsonl.

    Stage sequence (happy path):
        sandbox_creating → sandbox_ready → uploading_skill → files_uploaded
        → running → downloading → complete

    On any error:
        → error  (with failed_at and error message)
    """
    run_id = str(uuid.uuid4())[:8]
    log_path = LOG_DIR / f"{run_id}.jsonl"
    files = files or {}
    current_stage = "init"

    def emit(event: dict) -> dict:
        event = {"run_id": run_id, "ts": time.time(), **event}
        log.info("[%s] stage=%s %s", run_id, event.get("stage"), event.get("detail", ""))
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
        return event

    sandbox = None
    session_id: str | None = None
    repo_tarball: bytes | None = None
    ticket_payload: dict | None = None
    try:
        repo_url = (inputs.get("repo_url") or "").strip()
        ticket_id = inputs.get("ticket_id")
        if repo_url or ticket_id:
            current_stage = "fetching_assets"
            yield emit({"stage": "fetching_assets",
                        "fetch_repo": bool(repo_url),
                        "fetch_ticket": bool(ticket_id)})
            if repo_url:
                repo_tarball = _fetch_gitlab_archive(repo_url)
            if ticket_id:
                ticket_payload = _fetch_openproject_ticket(ticket_id)
            yield emit({"stage": "assets_fetched",
                        "repo_bytes": len(repo_tarball) if repo_tarball else 0,
                        "ticket_activities": len(ticket_payload["activities"]) if ticket_payload else 0})

        current_stage = "sandbox_creating"
        yield emit({"stage": "sandbox_creating"})

        skill_md = load_skill_md(skill_id)
        task = _format_task(inputs)
        skill_dir_in_sandbox = f"/home/daytona/skills/{skill_id}"

        daytona = Daytona(_config)
        sandbox = daytona.create(
            CreateSandboxFromSnapshotParams(
                snapshot=SNAPSHOT,
                env_vars={
                    "ANTHROPIC_BASE_URL": os.environ["ANTHROPIC_BASE_URL"],
                    "ANTHROPIC_AUTH_TOKEN": os.environ["ANTHROPIC_AUTH_TOKEN"],
                    "CLAUDE_SKILL_DIR": skill_dir_in_sandbox,
                },
                auto_stop_interval=30,
            )
        )
        yield emit({"stage": "sandbox_ready", "sandbox_id": sandbox.id})

        current_stage = "uploading_skill"
        yield emit({"stage": "uploading_skill"})

        if GLOBAL_CLAUDE_MD.exists():
            sandbox.fs.upload_file(GLOBAL_CLAUDE_MD.read_bytes(), "/home/daytona/CLAUDE.md")

        sandbox.fs.upload_file(skill_md, "/home/daytona/workspace/SKILL.md")

        skill_local_dir = SKILLS_DIR / skill_id
        for fpath in sorted(skill_local_dir.rglob("*")):
            if fpath.is_file() and fpath.name != "metadata.yaml":
                rel = fpath.relative_to(skill_local_dir).as_posix()
                sandbox.fs.upload_file(
                    fpath.read_bytes(),
                    f"{skill_dir_in_sandbox}/{rel}",
                )

        uploaded_names: list[str] = []
        for filename, content in files.items():
            safe_name = Path(filename).name
            if not safe_name:
                continue
            sandbox.fs.upload_file(content, f"/home/daytona/workspace/{safe_name}")
            uploaded_names.append(safe_name)

        fetched_paths: list[str] = []
        if repo_tarball:
            sandbox.fs.upload_file(repo_tarball, "/home/daytona/workspace/_repo.tar.gz")
            extract_cmd = (
                "cd /home/daytona/workspace && "
                "mkdir -p repo && "
                "tar xzf _repo.tar.gz --strip-components=1 -C repo && "
                "rm _repo.tar.gz && "
                "find repo -maxdepth 1 -mindepth 1 | wc -l"
            )
            r = sandbox.process.exec(extract_cmd, timeout=120)
            if getattr(r, "exit_code", 0) != 0:
                raise RuntimeError(
                    f"repo extract failed (exit={r.exit_code}): {getattr(r, 'result', '')[:300]}"
                )
            fetched_paths.append("workspace/repo/")

        if ticket_payload:
            sandbox.fs.upload_file(
                json.dumps(ticket_payload, ensure_ascii=False, indent=2).encode("utf-8"),
                "/home/daytona/workspace/ticket.json",
            )
            fetched_paths.append("workspace/ticket.json")

        yield emit({
            "stage": "files_uploaded",
            "user_files": uploaded_names,
            "fetched_paths": fetched_paths,
        })

        notes_lines: list[str] = []
        if uploaded_names:
            notes_lines.append("Uploaded files (in /home/daytona/workspace/):")
            notes_lines.extend(f"  - {n}" for n in uploaded_names)
        if fetched_paths:
            notes_lines.append("Pre-fetched assets:")
            for p in fetched_paths:
                if p.endswith("/"):
                    notes_lines.append(f"  - /home/daytona/{p}  (source tree — read files with Read/Grep)")
                else:
                    notes_lines.append(f"  - /home/daytona/{p}")
        files_note = ("\n\n" + "\n".join(notes_lines)) if notes_lines else ""

        prompt = (
            "Read /home/daytona/workspace/SKILL.md and execute the task described there.\n\n"
            f"Inputs:\n{task}{files_note}"
        )
        safe_prompt = prompt.replace("'", "'\\''")

        model = os.environ.get("CLAUDE_MODEL", "")
        model_flag = f"--model {model}" if model else ""
        cmd = (
            f"claude -p '{safe_prompt}' "
            f"{model_flag} "
            f"--output-format stream-json "
            f"--dangerously-skip-permissions "
            f"--verbose"
        )

        current_stage = "running"
        yield emit({"stage": "running"})

        chunks: list[str] = []
        start = time.time()
        pty = sandbox.process.create_pty_session(id="skill-run")
        pty.wait_for_connection()
        pty.send_input(cmd + "\nexit\n")
        pty.wait(on_data=lambda data: chunks.append(data.decode(errors="replace")))
        elapsed = time.time() - start
        raw = "".join(chunks)
        session_id = _parse_session_id(raw)

        # Save raw Claude stream-json so tool calls / bash commands are inspectable
        raw_log_path = LOG_DIR / f"{run_id}_claude.jsonl"
        with raw_log_path.open("w", encoding="utf-8") as f:
            f.write(raw)

        current_stage = "downloading"
        yield emit({"stage": "downloading"})

        output_files = _download_outputs(sandbox)
        main_output = _pick_main_output(output_files, fallback=_parse_output(raw))

        text_files: dict[str, str] = {}
        binary_files: dict[str, str] = {}
        for fname, content in output_files.items():
            try:
                text_files[fname] = content.decode("utf-8")
            except (UnicodeDecodeError, ValueError):
                binary_files[fname] = base64.b64encode(content).decode()

        yield emit({
            "stage": "complete",
            "output": main_output,
            "output_files": text_files,
            "output_files_binary": binary_files,
            "execution_time": elapsed,
            "cost_usd": _parse_cost(raw),
            "session_id": session_id,
            "claude_log": f"{run_id}_claude.jsonl",
        })

    except Exception as e:
        yield emit({
            "stage": "error",
            "failed_at": current_stage,
            "error": str(e),
            "session_id": session_id,
            "claude_log": f"{run_id}_claude.jsonl" if (LOG_DIR / f"{run_id}_claude.jsonl").exists() else None,
        })

    finally:
        if sandbox:
            try:
                sandbox.delete()
            except Exception:
                pass


def run_skill(
    skill_id: str,
    inputs: dict,
    files: dict[str, bytes] | None = None,
) -> dict:
    """Blocking wrapper around stream_skill — collects all events, returns final result."""
    for event in stream_skill(skill_id, inputs, files):
        if event["stage"] == "complete":
            return {k: v for k, v in event.items() if k not in ("stage", "run_id", "ts")}
        if event["stage"] == "error":
            raise RuntimeError(f"[{event.get('failed_at', '?')}] {event['error']}")
    raise RuntimeError("stream_skill ended without a complete or error event")
