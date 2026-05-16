import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

SKILLS_DIR = Path(__file__).parent.parent / "skills"


class SkillNotFoundError(Exception):
    pass


class SkillAlreadyExistsError(Exception):
    pass


def _skill_dir(skill_id: str) -> Path:
    return SKILLS_DIR / skill_id


def load_skill_md(skill_id: str) -> bytes:
    path = _skill_dir(skill_id) / "SKILL.md"
    if not path.exists():
        raise SkillNotFoundError(f"Skill '{skill_id}' not found at {path}")
    return path.read_bytes()


def load_skill_metadata(skill_id: str) -> dict:
    path = _skill_dir(skill_id) / "metadata.yaml"
    if not path.exists():
        raise SkillNotFoundError(f"Metadata for skill '{skill_id}' not found at {path}")
    with path.open(encoding="utf-8") as f:
        meta = yaml.safe_load(f) or {}
    meta.setdefault("skill_id", skill_id)
    return meta


def list_skills(
    status: Optional[str] = "approved",
    team: Optional[str] = None,
    category: Optional[str] = None,
    search: Optional[str] = None,
) -> list[dict]:
    skills: list[dict] = []
    if not SKILLS_DIR.exists():
        return skills
    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        if not skill_dir.is_dir():
            continue
        meta_path = skill_dir / "metadata.yaml"
        if not meta_path.exists():
            continue
        with meta_path.open(encoding="utf-8") as f:
            meta = yaml.safe_load(f) or {}
        meta.setdefault("skill_id", skill_dir.name)
        skills.append(meta)

    if status:
        skills = [s for s in skills if s.get("status") == status]
    if team:
        skills = [s for s in skills if s.get("team") == team]
    if category:
        skills = [s for s in skills if s.get("category") == category]
    if search:
        q = search.lower()
        skills = [
            s for s in skills
            if q in (s.get("name", "") or "").lower()
            or q in (s.get("description", "") or "").lower()
        ]
    return skills


def skill_exists(skill_id: str) -> bool:
    return (_skill_dir(skill_id) / "SKILL.md").exists()


def create_pending_skill(metadata: dict, skill_md: str) -> dict:
    """Create a new skill directory with status=pending."""
    skill_id = metadata.get("skill_id")
    if not skill_id:
        raise ValueError("metadata.skill_id is required")
    target = _skill_dir(skill_id)
    if target.exists():
        raise SkillAlreadyExistsError(f"Skill '{skill_id}' already exists")
    target.mkdir(parents=True)

    metadata = dict(metadata)
    metadata["status"] = "pending"
    metadata.setdefault("version", 1)
    metadata.setdefault("created_at", datetime.now().isoformat())
    metadata.pop("approved_at", None)

    _write_metadata(skill_id, metadata)
    (target / "SKILL.md").write_text(skill_md or _default_skill_md(metadata), encoding="utf-8")
    return metadata


def update_skill(skill_id: str, metadata: dict, skill_md: str) -> dict:
    """Update an existing skill. Bumps version, resets status to pending for re-review."""
    target = _skill_dir(skill_id)
    if not target.exists():
        raise SkillNotFoundError(f"Skill '{skill_id}' not found")

    metadata = dict(metadata)
    metadata["skill_id"] = skill_id
    metadata["status"] = "pending"
    metadata["version"] = int(metadata.get("version", 1)) + 1
    metadata.setdefault("created_at", datetime.now().isoformat())
    metadata.pop("approved_at", None)
    metadata.pop("rejection_reason", None)

    _write_metadata(skill_id, metadata)
    if skill_md:
        (target / "SKILL.md").write_text(skill_md, encoding="utf-8")
    return metadata


def set_skill_status(skill_id: str, status: str, reason: Optional[str] = None) -> dict:
    if status not in ("approved", "rejected", "pending"):
        raise ValueError(f"invalid status: {status}")
    meta = load_skill_metadata(skill_id)
    meta["status"] = status
    if status == "approved":
        meta["approved_at"] = datetime.now().isoformat()
        meta.pop("rejection_reason", None)
    elif status == "rejected":
        meta["rejection_reason"] = reason or ""
        meta.pop("approved_at", None)
    _write_metadata(skill_id, meta)
    return meta


def admin_update_skill(skill_id: str, metadata: dict, skill_md: str = "") -> dict:
    """Admin update — preserves current status, does NOT bump version or reset to pending."""
    target = _skill_dir(skill_id)
    if not target.exists():
        raise SkillNotFoundError(f"Skill '{skill_id}' not found")
    existing = load_skill_metadata(skill_id)
    metadata = dict(metadata)
    metadata["skill_id"] = skill_id
    metadata["status"] = existing.get("status", "pending")
    metadata.setdefault("version", existing.get("version", 1))
    metadata.setdefault("created_at", existing.get("created_at", datetime.now().isoformat()))
    if existing.get("approved_at"):
        metadata["approved_at"] = existing["approved_at"]
    if existing.get("rejection_reason"):
        metadata["rejection_reason"] = existing["rejection_reason"]
    _write_metadata(skill_id, metadata)
    if skill_md:
        (target / "SKILL.md").write_text(skill_md, encoding="utf-8")
    return metadata


def delete_skill(skill_id: str) -> None:
    target = _skill_dir(skill_id)
    if not target.exists():
        raise SkillNotFoundError(f"Skill '{skill_id}' not found")
    shutil.rmtree(target)


def _write_metadata(skill_id: str, metadata: dict) -> None:
    path = _skill_dir(skill_id) / "metadata.yaml"
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(metadata, f, sort_keys=False, allow_unicode=True)


def _default_skill_md(metadata: dict) -> str:
    name = metadata.get("name", metadata["skill_id"])
    owner = metadata.get("owner", metadata.get("team", "unknown"))
    return (
        f"# Skill: {metadata['skill_id']}\n"
        f"<!-- version: {metadata.get('version', 1)} | owner: {owner} -->\n\n"
        f"## Task\n{metadata.get('description', name)}\n\n"
        "## Steps\n"
        "1. Read the inputs from the prompt\n"
        "2. Produce the requested output in `output/`\n"
        "3. Append progress to `output/run.log`\n"
    )
