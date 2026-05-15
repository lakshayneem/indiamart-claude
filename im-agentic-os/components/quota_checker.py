import json
import pandas as pd
from pathlib import Path
from datetime import datetime, date

ADOPTIONS_FILE = Path("data/adoptions.json")
CONFIG_FILE = Path("assets/config.xlsx")

def _load_adoptions() -> list:
    if ADOPTIONS_FILE.exists():
        return json.loads(ADOPTIONS_FILE.read_text())
    return []

def _load_rate_limits() -> dict:
    try:
        df = pd.read_excel(CONFIG_FILE, sheet_name="RateLimits")
        limits = {}
        for _, row in df.iterrows():
            limits[str(row["role"]).strip()] = {
                "max_runs_per_day": int(row["max_runs_per_day"]),
                "max_runs_per_skill_per_day": int(row["max_runs_per_skill_per_day"])
            }
        return limits
    except Exception:
        return {
            "user": {"max_runs_per_day": 20, "max_runs_per_skill_per_day": 5},
            "creator": {"max_runs_per_day": 50, "max_runs_per_skill_per_day": 10},
            "admin": {"max_runs_per_day": 999, "max_runs_per_skill_per_day": 999}
        }

def compute_quota(username: str, role: str, skill_id: str = None) -> dict:
    today = date.today().isoformat()
    adoptions = _load_adoptions()
    limits = _load_rate_limits()
    role_limits = limits.get(role, limits.get("user"))

    today_runs = [a for a in adoptions if a["username"] == username and a["ran_at"][:10] == today]
    total_today = len(today_runs)
    skill_today = len([a for a in today_runs if skill_id and a["skill_id"] == skill_id])

    max_day = role_limits["max_runs_per_day"]
    max_skill = role_limits["max_runs_per_skill_per_day"]

    return {
        "total_today": total_today,
        "max_day": max_day,
        "remaining_day": max(0, max_day - total_today),
        "skill_today": skill_today,
        "max_skill": max_skill,
        "remaining_skill": max(0, max_skill - skill_today) if skill_id else max_skill,
        "is_blocked_day": total_today >= max_day,
        "is_blocked_skill": skill_id is not None and skill_today >= max_skill,
    }

def can_run(username: str, role: str, skill_id: str) -> tuple[bool, str]:
    q = compute_quota(username, role, skill_id)
    if q["is_blocked_day"]:
        return False, f"Daily run limit reached ({q['max_day']} runs). Resets at midnight."
    if q["is_blocked_skill"]:
        return False, f"Daily limit for this skill reached ({q['max_skill']} runs). Resets at midnight."
    return True, ""

def quota_color(remaining: int, max_val: int) -> str:
    if max_val >= 999:
        return "green"
    pct = remaining / max_val if max_val else 0
    if pct > 0.3:
        return "green"
    elif pct > 0.1:
        return "amber"
    return "red"
