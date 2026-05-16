import base64
import mimetypes
import streamlit as st
import json
import uuid
import pandas as pd
from pathlib import Path
from datetime import datetime

from components.design_system import inject_css, topnav, hero_banner, empty_state, loading_animation, stars
from components.auth import require_role, get_current_user, logout
from components.sandbox_client import run_skill, stream_skill_run, check_sandbox_health
from components.quota_checker import compute_quota, can_run
from components.hours_counter import compute_hours_saved, format_hours
from components.announcement_banner import get_active_announcements, render_banners
from components.output_renderer import render_output, render_error
from scripts.fetch_data import fetch_all_skills, fetch_skill

st.set_page_config(
    page_title="IM Agentic OS — Dashboard",
    page_icon=":material/dashboard:",
    layout="wide",
)
inject_css()
require_role(["user", "creator", "admin"])

user = get_current_user()

# ── Data helpers ──────────────────────────────────────────────────────────────
def load_json(path):
    return json.loads(Path(path).read_text()) if Path(path).exists() else []

def save_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2))

def load_config_teams():
    try:
        df = pd.read_excel("assets/config.xlsx", sheet_name="Teams")
        return ["All teams"] + [r["team_name"] for _, r in df.iterrows() if r.get("is_active")]
    except:
        return ["All teams"]

def load_config_categories(team=None):
    try:
        df = pd.read_excel("assets/config.xlsx", sheet_name="Categories")
        if team and team != "All teams":
            df_t = pd.read_excel("assets/config.xlsx", sheet_name="Teams")
            tid = df_t[df_t["team_name"] == team]["team_id"].iloc[0]
            df = df[df["team_id"] == tid]
        return ["All categories"] + [r["category_name"] for _, r in df.iterrows() if r.get("is_active")]
    except:
        return ["All categories"]

def get_skill_stats(skill_id):
    adoptions = load_json("data/adoptions.json")
    feedback  = load_json("data/feedback.json")
    runs    = len([a for a in adoptions if a["skill_id"] == skill_id])
    ratings = [f["rating"] for f in feedback if f["skill_id"] == skill_id]
    avg     = round(sum(ratings) / len(ratings), 1) if ratings else 0.0
    return runs, avg, len(ratings)

def log_run(skill_id, username, status, exec_time):
    adoptions = load_json("data/adoptions.json")
    adoptions.append({
        "run_id": str(uuid.uuid4())[:8],
        "skill_id": skill_id,
        "username": username,
        "status": status,
        "execution_time": exec_time,
        "ran_at": datetime.now().isoformat(),
    })
    save_json("data/adoptions.json", adoptions)

def toggle_favourite(username, skill_id):
    favs = load_json("data/favourites.json")
    if not isinstance(favs, dict):
        favs = {}
    user_favs = favs.get(username, [])
    if skill_id in user_favs:
        user_favs.remove(skill_id)
    else:
        user_favs.append(skill_id)
    favs[username] = user_favs
    save_json("data/favourites.json", favs)

def get_favourites(username):
    favs = load_json("data/favourites.json")
    return favs.get(username, []) if isinstance(favs, dict) else []

def submit_feedback(skill_id, username, rating, comment):
    feedback = load_json("data/feedback.json")
    feedback.append({
        "feedback_id": f"fb{str(uuid.uuid4())[:6]}",
        "skill_id": skill_id,
        "username": username,
        "rating": rating,
        "comment": comment,
        "created_at": datetime.now().isoformat(),
    })
    save_json("data/feedback.json", feedback)

def submit_skill_request(data):
    reqs = load_json("data/skill_requests.json")
    reqs.append(data)
    save_json("data/skill_requests.json", reqs)

# ── Skill card ────────────────────────────────────────────────────────────────
def render_skill_card(sk, username, ctx=""):
    skill_id  = sk["skill_id"]
    runs, avg_rating, rating_count = get_skill_stats(skill_id)
    is_fav    = skill_id in get_favourites(username)
    is_new    = sk.get("approved_at", "") >= (datetime.now().strftime("%Y-%m") + "-01")
    est_min   = sk.get("adoption_projection", {}).get("x_mins", 0)
    key_sfx   = f"{skill_id}_{username}_{ctx}" if ctx else f"{skill_id}_{username}"

    # Inline badge syntax — no custom HTML needed
    team_badge = f":blue-badge[{sk.get('team', '')}]" if sk.get("team") else ""
    cat_badge  = f":green-badge[{sk.get('category', '')}]" if sk.get("category") else ""
    feat_badge = " :orange-badge[Featured]" if sk.get("is_featured") else ""
    new_badge  = " :blue-badge[New]" if is_new else ""

    with st.container(border=True):
        # Name row
        name_col, fav_col = st.columns([5, 1])
        with name_col:
            st.markdown(f"**{sk['name']}**")
        with fav_col:
            fav_icon = ":material/star:" if is_fav else ":material/star_outline:"
            if st.button(fav_icon, key=f"fav_{key_sfx}", help="Toggle favourite"):
                toggle_favourite(username, skill_id)
                st.rerun()

        # Badges
        st.markdown(f"{team_badge} {cat_badge}{feat_badge}{new_badge}")

        # Description (truncated)
        desc = sk.get("description", "")
        st.caption(desc[:110] + "…" if len(desc) > 110 else desc)

        # Meta: time · rating · runs
        rating_str = f"{avg_rating:.1f} ★ ({rating_count})" if rating_count else "No ratings yet"
        meta_parts = []
        if est_min:
            meta_parts.append(f"~{est_min} min")
        meta_parts.append(rating_str)
        meta_parts.append(f"{runs} runs")
        st.caption(" · ".join(meta_parts))

        # Run button
        if st.button(
            ":material/play_arrow: Run skill",
            key=f"run_{key_sfx}",
            type="primary",
        ):
            st.session_state["active_skill"]      = skill_id
            st.session_state["active_skill_data"] = sk
            st.rerun()

# ── Skill execution dialog ────────────────────────────────────────────────────
@st.dialog("Run skill", width="large")
def skill_dialog(sk, username):
    skill_id     = sk["skill_id"]
    input_fields = sk.get("input_fields", [])
    est          = sk.get("adoption_projection", {}).get("x_mins", 0)
    ok, msg      = can_run(username, st.session_state.get("role", "user"), skill_id)

    st.markdown(f"**{sk['name']}**")
    if est:
        st.caption(f":material/schedule: Estimated time: ~{est} min")

    if not ok:
        st.warning(f":material/warning: {msg}")
        return

    collected = {}
    uploaded_files = {}
    with st.form(key=f"dialog_form_{skill_id}", border=False):
        for field in input_fields:
            key        = field["key"]
            label      = field["label"] + (" *" if field.get("required") else "")
            ftype      = field.get("type", "text")
            placeholder = field.get("placeholder", "")

            if ftype == "textarea":
                collected[key] = st.text_area(label, placeholder=placeholder, height=150)
            elif ftype == "number":
                collected[key] = st.number_input(label, value=0)
            elif ftype == "date":
                collected[key] = str(st.date_input(label))
            elif ftype == "dropdown":
                opts = field.get("options", [])
                collected[key] = st.selectbox(label, opts, accept_new_options=True)
            elif ftype == "file_upload":
                allowed = field.get("allowed_file_types", [".pdf", ".txt"])
                st.caption(f"Accepted: {', '.join(allowed)}")
                f = st.file_uploader(label, type=[e.lstrip(".") for e in allowed])
                if f is not None:
                    uploaded_files[key] = (f.name, f.getvalue())
                    collected[key] = f.name
                else:
                    collected[key] = ""
            else:
                collected[key] = st.text_input(label, placeholder=placeholder)

        submitted = st.form_submit_button(
            ":material/play_arrow: Run skill",
            type="primary",
        )

    if submitted:
        # Validate required fields
        missing = [f["label"] for f in input_fields if f.get("required") and not collected.get(f["key"])]
        if missing:
            st.error(f"Required: {', '.join(missing)}")
            return

        result = None
        _stage_labels = {
            "sandbox_creating": "Creating sandbox…",
            "sandbox_ready":    "✅ Sandbox ready",
            "uploading_skill":  "Uploading skill files…",
            "files_uploaded":   "✅ Files uploaded",
            "running":          "🤖 Claude is running the skill…",
            "downloading":      "Downloading outputs…",
        }

        with st.status("Running skill…", expanded=True) as run_status:
            for event in stream_skill_run(skill_id, collected, files=uploaded_files or None):
                stage = event.get("stage")
                if stage in _stage_labels:
                    label = _stage_labels[stage]
                    if stage == "files_uploaded" and event.get("user_files"):
                        n = len(event["user_files"])
                        label = f"✅ Files uploaded ({n} user file{'s' if n != 1 else ''})"
                    st.write(label)
                elif stage == "complete":
                    result = {
                        "status": "success",
                        "output": event.get("output", ""),
                        "output_files": event.get("output_files", {}),
                        "output_files_binary": event.get("output_files_binary", {}),
                        "execution_time_seconds": event.get("execution_time", 0),
                        "cost_usd": event.get("cost_usd", 0),
                        "source": "live",
                    }
                    run_status.update(label="✅ Complete", state="complete")
                elif stage == "error":
                    result = {
                        "status": "error",
                        "error": event.get("error", "Unknown error"),
                        "execution_time_seconds": 0,
                    }
                    run_status.update(
                        label=f"❌ Failed at: {event.get('failed_at', 'unknown')}",
                        state="error",
                    )

        if result is None:
            result = {"status": "error", "error": "No response from backend", "execution_time_seconds": 0}

        log_run(skill_id, username, result["status"], result.get("execution_time_seconds", 0))

        if result["status"] == "success":
            exec_time = result.get("execution_time_seconds", 0)
            st.success(f":material/check_circle: Completed in {exec_time:.1f}s", icon=None)
            render_output(result["output"], exec_time, sk["name"], result.get("source", "live"))

            # ── Downloads ────────────────────────────────────────────────────
            text_files = result.get("output_files") or {}
            bin_files  = result.get("output_files_binary") or {}
            all_files  = list(text_files) + list(bin_files)

            if all_files:
                st.markdown("**Download output files**")
                dl_cols = st.columns(min(len(all_files), 4))
                for i, fname in enumerate(all_files):
                    mime = mimetypes.guess_type(fname)[0] or "application/octet-stream"
                    data = base64.b64decode(bin_files[fname]) if fname in bin_files else text_files[fname].encode()
                    with dl_cols[i % 4]:
                        st.download_button(
                            f":material/download: {fname}",
                            data=data,
                            file_name=fname,
                            mime=mime,
                            key=f"dl_{skill_id}_{fname}_{exec_time}",
                        )
            else:
                st.download_button(
                    ":material/download: Download output",
                    data=result["output"],
                    file_name=f"{skill_id}_output.md",
                    mime="text/markdown",
                    key=f"dl_{skill_id}_main_{exec_time}",
                )

            # Feedback
            run_key = str(exec_time)
            if not st.session_state.get(f"fb_done_{skill_id}_{run_key}"):
                st.divider()
                st.markdown("**Rate this skill**")
                rating  = st.slider("Rating", 1, 5, 4, key=f"dlg_rating_{skill_id}_{run_key}")
                comment = st.text_area("Comment (optional)", key=f"dlg_comment_{skill_id}_{run_key}")
                if st.button("Submit feedback", key=f"dlg_fb_{skill_id}_{run_key}"):
                    submit_feedback(skill_id, username, rating, comment)
                    st.session_state[f"fb_done_{skill_id}_{run_key}"] = True
                    st.toast("Thank you for your feedback!", icon=":material/thumb_up:")
                    st.rerun()
        else:
            render_error(result.get("error", "Skill execution failed. Please try again."))

# ── Top nav ──────────────────────────────────────────────────────────────────
topnav(user["name"], user["role"])

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    backend_up = check_sandbox_health()
    if backend_up:
        st.markdown(":green-badge[:material/cloud_done: Backend online]")
    else:
        st.markdown(":red-badge[:material/cloud_off: Backend offline — runs use mock]")

    quota     = compute_quota(user["username"], user["role"])
    remaining = quota["remaining_day"]
    max_day   = quota["max_day"]
    used      = quota["total_today"]

    if remaining > max_day * 0.5:
        q_color = "green"
    elif remaining > 0:
        q_color = "orange"
    else:
        q_color = "red"

    st.markdown(f":{q_color}-badge[{used} / {max_day} runs today]")

    nav = st.pills(
        "Navigate",
        [":material/home: Browse", ":material/star: Favourites", ":material/lightbulb: Requests"],
        label_visibility="collapsed",
    )

    st.divider()
    if st.button(":material/logout: Sign out"):
        logout()
        st.switch_page("app.py")

# ── Announcements ─────────────────────────────────────────────────────────────
announcements = get_active_announcements(user["role"], user["team"])
if announcements:
    render_banners(announcements)

# ── Open skill dialog if requested ───────────────────────────────────────────
if "active_skill" in st.session_state:
    sk = st.session_state.pop("active_skill_data", {})
    st.session_state.pop("active_skill", None)
    skill_dialog(sk, user["username"])

# ════════════════════════════════════════════════════════════════════════════
# BROWSE SKILLS
# ════════════════════════════════════════════════════════════════════════════
if nav is None or "Browse" in (nav or ""):
    # Hero banner
    stats = compute_hours_saved(period="month")
    hero_banner(
        title="IM Agentic OS",
        subtitle=f"{stats['runs']} runs · {stats['unique_users']} active users this month",
        kpi_value=f"{format_hours(stats['hours'])}h",
        kpi_label="saved this month",
    )

    # Filters
    col_t, col_c, col_s, col_sort = st.columns([2, 2, 3, 2])
    with col_t:
        sel_team = st.selectbox("Team", load_config_teams(), label_visibility="collapsed")
    with col_c:
        sel_cat  = st.selectbox("Category", load_config_categories(sel_team), label_visibility="collapsed")
    with col_s:
        search_q = st.text_input(
            "Search",
            placeholder="Search skills…",
            label_visibility="collapsed",
        )
    with col_sort:
        sort_by = st.selectbox(
            "Sort",
            ["Default", "Most used", "Newest", "Top rated"],
            label_visibility="collapsed",
        )

    all_skills = fetch_all_skills(
        sel_team if sel_team != "All teams" else None,
        sel_cat  if sel_cat  != "All categories" else None,
        search_q or None,
    )

    if sort_by == "Most used":
        all_skills.sort(key=lambda s: get_skill_stats(s["skill_id"])[0], reverse=True)
    elif sort_by == "Newest":
        all_skills.sort(key=lambda s: s.get("approved_at", ""), reverse=True)
    elif sort_by == "Top rated":
        all_skills.sort(key=lambda s: get_skill_stats(s["skill_id"])[1], reverse=True)
    else:
        all_skills.sort(key=lambda s: (not s.get("is_featured"), -get_skill_stats(s["skill_id"])[0]))

    # Featured row
    featured = [s for s in all_skills if s.get("is_featured")]
    if featured:
        st.markdown("#### :material/star: Featured skills")
        fcols = st.columns(min(len(featured), 3))
        for i, sk in enumerate(featured[:3]):
            with fcols[i]:
                render_skill_card(sk, user["username"], ctx=f"feat{i}")
        st.space("small")

    # All skills grid
    st.markdown(f"#### :material/grid_view: All skills ({len(all_skills)})")

    if not all_skills:
        empty_state(":material/search_off:", "No skills found", "Try adjusting your filters or search.")
    else:
        cols = st.columns(3)
        for i, sk in enumerate(all_skills):
            with cols[i % 3]:
                render_skill_card(sk, user["username"], ctx=f"grid{i}")

# ════════════════════════════════════════════════════════════════════════════
# MY FAVOURITES
# ════════════════════════════════════════════════════════════════════════════
elif "Favourites" in (nav or ""):
    st.markdown("#### :material/star: My favourites")
    favs       = get_favourites(user["username"])
    fav_skills = [s for sid in favs for s in [fetch_skill(sid)] if s]

    if not fav_skills:
        empty_state("⭐", "No favourites yet", "Star a skill from Browse to save it here.")
    else:
        cols = st.columns(3)
        for i, sk in enumerate(fav_skills):
            with cols[i % 3]:
                render_skill_card(sk, user["username"], ctx=f"fav{i}")

# ════════════════════════════════════════════════════════════════════════════
# SKILL REQUESTS
# ════════════════════════════════════════════════════════════════════════════
elif "Requests" in (nav or ""):
    st.markdown("#### :material/lightbulb: Skill requests")
    st.caption("Request a skill you need. Upvote colleagues' requests to signal demand to creators.")

    with st.expander(":material/add: Submit a new request", expanded=False):
        teams = load_config_teams()
        with st.form("new_request_form", border=False):
            req_title    = st.text_input("Skill title *", max_chars=80, placeholder="e.g. Email Draft Generator…")
            req_desc     = st.text_area("What should this skill automate? *", max_chars=500)
            c1, c2       = st.columns(2)
            with c1:
                req_team     = st.selectbox("Team *", teams[1:])
            with c2:
                req_priority = st.selectbox("Priority", ["Low", "Medium", "High", "Critical"])
            req_adopters = st.number_input("Estimated people who need this", min_value=1, value=10)

            if st.form_submit_button(":material/send: Submit request", type="primary"):
                open_reqs = load_json("data/skill_requests.json")
                my_open   = [r for r in open_reqs
                             if r["requested_by"] == user["username"] and r["status"] == "open"]
                if len(my_open) >= 3:
                    st.error("You can have at most 3 open requests at a time.")
                elif not req_title or len(req_title) < 3:
                    st.error("Please enter a valid skill title.")
                elif not req_desc or len(req_desc) < 20:
                    st.error("Description must be at least 20 characters.")
                else:
                    cats = load_config_categories(req_team)
                    submit_skill_request({
                        "request_id": f"req{str(uuid.uuid4())[:6]}",
                        "requested_by": user["username"],
                        "title": req_title,
                        "description": req_desc,
                        "team": req_team,
                        "category": cats[1] if len(cats) > 1 else "",
                        "estimated_adopters": int(req_adopters),
                        "priority": req_priority,
                        "status": "open",
                        "assigned_to": None,
                        "linked_skill_id": None,
                        "upvotes": [],
                        "created_at": datetime.now().isoformat(),
                    })
                    st.toast("Request submitted!", icon=":material/check_circle:")
                    st.rerun()

    sort_req  = st.segmented_control(
        "Sort requests",
        ["Most upvoted", "Newest", "Mine"],
        default="Most upvoted",
        label_visibility="collapsed",
    )
    all_reqs  = load_json("data/skill_requests.json")

    if sort_req == "Most upvoted":
        all_reqs.sort(key=lambda r: len(r.get("upvotes", [])), reverse=True)
    elif sort_req == "Newest":
        all_reqs.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    elif sort_req == "Mine":
        all_reqs = [r for r in all_reqs if r["requested_by"] == user["username"]]

    if not all_reqs:
        empty_state("💡", "No requests yet", "Be the first to request a skill!")
    else:
        priority_color = {"Low": "gray", "Medium": "blue", "High": "orange", "Critical": "red"}
        status_color   = {"open": "blue", "in_progress": "orange", "fulfilled": "green"}
        for req in all_reqs:
            upvotes       = req.get("upvotes", [])
            already_voted = user["username"] in upvotes
            is_mine       = req["requested_by"] == user["username"]
            days_ago      = max(0, (datetime.now() - datetime.fromisoformat(req["created_at"])).days)

            with st.container(border=True):
                title_col, badge_col = st.columns([4, 2])
                with title_col:
                    st.markdown(f"**{req['title']}**")
                with badge_col:
                    prio  = req.get("priority", "Low")
                    stat  = req.get("status", "open")
                    pc    = priority_color.get(prio, "gray")
                    sc    = status_color.get(stat, "blue")
                    st.markdown(
                        f":{pc}-badge[{prio}] :{sc}-badge[{stat.replace('_',' ').title()}]"
                    )

                st.caption(req["description"])
                st.caption(
                    f":blue-badge[{req['team']}] · {days_ago}d ago · {req['estimated_adopters']} potential adopters"
                )

                upvote_label = f":material/thumb_up: {len(upvotes)}" + (" ✓" if already_voted else "")
                if st.button(
                    upvote_label,
                    key=f"upvote_{req['request_id']}",
                    disabled=is_mine or already_voted,
                ):
                    fresh = load_json("data/skill_requests.json")
                    for r in fresh:
                        if r["request_id"] == req["request_id"]:
                            r.setdefault("upvotes", [])
                            if user["username"] not in r["upvotes"]:
                                r["upvotes"].append(user["username"])
                    save_json("data/skill_requests.json", fresh)
                    st.rerun()
