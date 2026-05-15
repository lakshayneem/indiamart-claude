import json
from pathlib import Path
from datetime import datetime, date

from components.sandbox_client import list_all_skills

ADOPTIONS_FILE = Path("data/adoptions.json")

def _load_adoptions() -> list:
    if ADOPTIONS_FILE.exists():
        return json.loads(ADOPTIONS_FILE.read_text())
    return []

def _load_skills() -> dict:
    skills = list_all_skills()
    return {s["skill_id"]: s for s in skills}

def compute_hours_saved(scope: str = "all", creator_id: str = None, period: str = "month") -> dict:
    adoptions = _load_adoptions()
    skills = _load_skills()

    now = datetime.now()
    if period == "month":
        adoptions = [a for a in adoptions if a["ran_at"][:7] == now.strftime("%Y-%m")]
    elif period == "today":
        adoptions = [a for a in adoptions if a["ran_at"][:10] == date.today().isoformat()]

    if creator_id:
        creator_skills = {sid for sid, s in skills.items() if s.get("creator_id") == creator_id}
        adoptions = [a for a in adoptions if a["skill_id"] in creator_skills]

    total_mins = 0.0
    for a in adoptions:
        skill = skills.get(a["skill_id"], {})
        x_mins = skill.get("adoption_projection", {}).get("x_mins", 0)
        total_mins += x_mins

    unique_users = len({a["username"] for a in adoptions})
    return {
        "hours": round(total_mins / 60, 1),
        "minutes": round(total_mins, 0),
        "runs": len(adoptions),
        "unique_users": unique_users
    }

def format_hours(h: float) -> str:
    if h >= 1000:
        return f"{h/1000:.1f}K"
    return str(int(h)) if h == int(h) else f"{h:.1f}"
