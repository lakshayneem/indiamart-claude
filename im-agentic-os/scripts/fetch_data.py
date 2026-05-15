"""
Skill catalog fetcher — talks to the backend API.

All skill listings come from the FastAPI backend; the legacy
data/skills_registry.json and data/pending_skills.json files are no longer
read here. They may be left on disk as historical artifacts.
"""
import sys

from components.sandbox_client import list_skills, list_all_skills, get_skill


def fetch_all_skills(team: str | None = None, category: str | None = None,
                     search: str | None = None) -> list:
    """Approved skills only — what end users browse."""
    return list_skills(team=team, category=category, search=search)


def fetch_skill(skill_id: str) -> dict | None:
    return get_skill(skill_id)


def fetch_creator_skills(creator_id: str, include_pending: bool = True) -> list:
    """All skills (any status) owned by `creator_id`."""
    skills = list_all_skills()
    out = [s for s in skills if s.get("creator_id") == creator_id]
    if not include_pending:
        out = [s for s in out if s.get("status") == "approved"]
    return out


if __name__ == "__main__":
    import json
    skill_id = sys.argv[1] if len(sys.argv) > 1 else None
    if skill_id:
        print(json.dumps(fetch_skill(skill_id), indent=2))
    else:
        print(json.dumps(fetch_all_skills(), indent=2))
