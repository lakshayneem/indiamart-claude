import os
from pathlib import Path
from typing import Optional
import yaml

SKILLS_DIR = Path(__file__).parent.parent / "skills"


class SkillNotFoundError(Exception):
    pass


def load_skill_md(skill_name: str) -> bytes:
    """Return SKILL.md bytes for the named skill."""
    path = SKILLS_DIR / skill_name / "SKILL.md"
    if not path.exists():
        raise SkillNotFoundError(f"Skill '{skill_name}' not found at {path}")
    return path.read_bytes()


def load_skill_metadata(skill_name: str) -> dict:
    """Return parsed metadata.yaml for the named skill."""
    path = SKILLS_DIR / skill_name / "metadata.yaml"
    if not path.exists():
        raise SkillNotFoundError(f"Metadata for skill '{skill_name}' not found at {path}")
    with path.open() as f:
        return yaml.safe_load(f)


def list_skills() -> list[dict]:
    """Return metadata for all available skills."""
    skills = []
    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        if not skill_dir.is_dir():
            continue
        meta_path = skill_dir / "metadata.yaml"
        if not meta_path.exists():
            continue
        with meta_path.open() as f:
            skills.append(yaml.safe_load(f))
    return skills


def skill_exists(skill_name: str) -> bool:
    return (SKILLS_DIR / skill_name / "SKILL.md").exists()
