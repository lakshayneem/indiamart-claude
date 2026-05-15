import json
import streamlit as st
from pathlib import Path
from datetime import datetime

ANNOUNCEMENTS_FILE = Path("data/announcements.json")

def _load_announcements() -> list:
    if ANNOUNCEMENTS_FILE.exists():
        return json.loads(ANNOUNCEMENTS_FILE.read_text())
    return []

def _save_announcements(items: list):
    ANNOUNCEMENTS_FILE.write_text(json.dumps(items, indent=2))

def get_active_announcements(user_role: str, user_team: str) -> list:
    now = datetime.now().isoformat()
    all_ann = _load_announcements()
    result = []
    for a in all_ann:
        if not a.get("is_active", True):
            continue
        if a.get("expires_at") and a["expires_at"] < now:
            continue
        audience = a.get("audience", "all")
        if audience == "all":
            result.append(a)
        elif audience == "creators" and user_role == "creator":
            result.append(a)
        elif audience == "team" and a.get("team") == user_team:
            result.append(a)
    return result

def render_banners(announcements: list):
    from components.design_system import announcement_banner
    dismissed = st.session_state.get("dismissed_announcements", set())
    for a in announcements:
        aid = a["announcement_id"]
        if aid in dismissed:
            continue
        col1, col2 = st.columns([20, 1])
        with col1:
            st.markdown(announcement_banner(a), unsafe_allow_html=True)
        with col2:
            if st.button("✕", key=f"dismiss_{aid}", help="Dismiss"):
                dismissed.add(aid)
                st.session_state["dismissed_announcements"] = dismissed
                st.rerun()

def post_announcement(ann: dict):
    items = _load_announcements()
    items.append(ann)
    _save_announcements(items)

def update_announcement(ann_id: str, updates: dict):
    items = _load_announcements()
    for a in items:
        if a["announcement_id"] == ann_id:
            a.update(updates)
    _save_announcements(items)

def delete_announcement(ann_id: str):
    items = _load_announcements()
    items = [a for a in items if a["announcement_id"] != ann_id]
    _save_announcements(items)
