import json
import hashlib
import streamlit as st
from pathlib import Path

USERS_FILE = Path("data/users.json")

def _hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def _load_users() -> list:
    if USERS_FILE.exists():
        return json.loads(USERS_FILE.read_text())
    return []

def _save_users(users: list):
    USERS_FILE.write_text(json.dumps(users, indent=2))

def login(username: str, password: str) -> dict | None:
    users = _load_users()
    h = _hash(password)
    for u in users:
        if u["username"] == username and u["password_hash"] == h:
            if not u.get("enabled", True):
                return {"error": "disabled"}
            return u
    return None

def logout():
    for key in ["user", "role", "username", "name", "team"]:
        st.session_state.pop(key, None)

def is_authenticated() -> bool:
    return "username" in st.session_state

def get_current_user() -> dict:
    return {
        "username": st.session_state.get("username", ""),
        "name": st.session_state.get("name", ""),
        "role": st.session_state.get("role", ""),
        "team": st.session_state.get("team", ""),
    }

def require_role(allowed_roles: list) -> bool:
    if not is_authenticated():
        st.warning("Please log in to access this page.")
        st.stop()
        return False
    role = st.session_state.get("role", "")
    if role not in allowed_roles:
        st.error("🚫 Access Denied — you don't have permission to view this page.")
        st.stop()
        return False
    return True

def get_all_users() -> list:
    return _load_users()

def update_user(username: str, updates: dict):
    users = _load_users()
    for u in users:
        if u["username"] == username:
            u.update(updates)
    _save_users(users)

def add_user(user: dict):
    users = _load_users()
    users.append(user)
    _save_users(users)
