import streamlit as st
import json, uuid, hashlib, secrets
import pandas as pd
from pathlib import Path
from datetime import datetime

from components.design_system import inject_css, topnav, badge, section_heading, stars, empty_state, metric_card
from components.auth import require_role, get_current_user, logout, get_all_users, update_user, add_user
from components.hours_counter import compute_hours_saved, format_hours
from components.announcement_banner import post_announcement, update_announcement, delete_announcement
from components.sandbox_client import (
    list_skills as api_list_skills,
    list_all_skills as api_list_all_skills,
    approve_skill as api_approve_skill,
    reject_skill as api_reject_skill,
    admin_update_skill as api_admin_update_skill,
)

st.set_page_config(page_title="IM Agentic OS — Admin", page_icon=":material/admin_panel_settings:", layout="wide")
inject_css()
require_role(["admin"])
user = get_current_user()

def load_json(path): return json.loads(Path(path).read_text()) if Path(path).exists() else []
def save_json(path, data): Path(path).write_text(json.dumps(data, indent=2))

def log_audit(actor, action, target, details):
    audit = load_json("data/audit_log.json")
    audit.append({"log_id": f"log{str(uuid.uuid4())[:6]}", "actor": actor,
                  "action": action, "target": target, "details": details,
                  "created_at": datetime.now().isoformat()})
    save_json("data/audit_log.json", audit)

def approve_skill(skill_id):
    resp = api_approve_skill(skill_id)
    if resp.get("status") == "success":
        skill = resp.get("skill", {})
        log_audit(user["username"], "skill_approved", skill_id, f"Approved skill: {skill.get('name', skill_id)}")
        return True
    return False

def reject_skill(skill_id, reason):
    resp = api_reject_skill(skill_id, reason)
    if resp.get("status") == "success":
        log_audit(user["username"], "skill_rejected", skill_id, f"Rejected: {reason}")
        return True
    return False

def admin_edit_skill(skill_id, metadata, skill_md=""):
    resp = api_admin_update_skill(skill_id, metadata, skill_md)
    if resp.get("status") == "success":
        skill = resp.get("skill", {})
        log_audit(user["username"], "skill_edited_by_admin", skill_id, f"Admin edited skill: {skill.get('name', skill_id)}")
        return True
    return False


def load_rate_limits():
    try:
        df = pd.read_excel("assets/config.xlsx", sheet_name="RateLimits")
        return {str(r["role"]): {"max_runs_per_day": int(r["max_runs_per_day"]),
                                  "max_runs_per_skill_per_day": int(r["max_runs_per_skill_per_day"])}
                for _, r in df.iterrows()}
    except:
        return {"user":{"max_runs_per_day":20,"max_runs_per_skill_per_day":5},
                "creator":{"max_runs_per_day":50,"max_runs_per_skill_per_day":10},
                "admin":{"max_runs_per_day":999,"max_runs_per_skill_per_day":999}}

# ── Top Nav ──────────────────────────────────────────────────────────────────
topnav(user["name"], user["role"])
if st.sidebar.button(":material/logout: Sign out"):
    logout(); st.switch_page("app.py")

st.sidebar.caption("Admin panel")
nav = st.sidebar.radio(
    "Section",
    [
        ":material/dashboard: Dashboard",
        ":material/check_circle: Skill Approvals",
        ":material/group: User Management",
        ":material/timer: Rate Limits",
        ":material/bar_chart: Analytics",
        ":material/history: Audit Log",
        ":material/campaign: Announcements",
        ":material/search: Run Logs",
    ],
    label_visibility="collapsed",
)

# ════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ════════════════════════════════════════════════════════════════════════════
if "Dashboard" in nav:
    section_heading("Admin dashboard", ":material/dashboard:")
    approved  = api_list_skills()
    pending   = [s for s in api_list_all_skills() if s.get("status") == "pending"]
    all_users = get_all_users()
    adoptions = load_json("data/adoptions.json")
    today     = datetime.now().date().isoformat()
    runs_today = len([a for a in adoptions if a["ran_at"][:10] == today])

    with st.container(horizontal=True):
        st.metric("Active skills",    len(approved),  border=True)
        st.metric("Pending approval", len(pending),   border=True)
        st.metric("Total users",      len(all_users), border=True)
        st.metric("Runs today",       runs_today,     border=True)

    st.space("small")
    section_heading("Recent activity", ":material/history:")
    audit = sorted(load_json("data/audit_log.json"), key=lambda x: x["created_at"], reverse=True)[:10]
    action_colors = {"skill_approved":"success","skill_rejected":"danger","skill_submitted":"info",
                     "role_changed":"warning","user_disabled":"warning","announcement_posted":"secondary",
                     "rate_limit_changed":"neutral"}
    for entry in audit:
        action = entry["action"]
        days_ago = max(0, (datetime.now()-datetime.fromisoformat(entry["created_at"])).days)
        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:12px;padding:8px 0;border-bottom:1px solid var(--neutral-200);">
          {badge(action.replace('_',' ').title(), action_colors.get(action,'neutral'))}
          <span style="font-size:13px;color:var(--neutral-700);">{entry['details']}</span>
          <span style="font-size:12px;color:var(--neutral-400);margin-left:auto;">by {entry['actor']} · {days_ago}d ago</span>
        </div>
        """, unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════
# SKILL APPROVALS
# ════════════════════════════════════════════════════════════════════════════
elif "Approvals" in nav:
    section_heading("Skill approvals", ":material/check_circle:")
    all_skills = api_list_all_skills()

    status_filter = st.selectbox("Filter", ["All","Pending","Approved","Rejected"], key="approval_filter")
    search_a = st.text_input("Search by skill name or creator", placeholder="Search…", key="approval_search")

    filtered = all_skills
    if status_filter != "All":
        filtered = [p for p in filtered if p.get("status","pending").lower() == status_filter.lower()]
    if search_a:
        q = search_a.lower()
        filtered = [p for p in filtered if q in p["name"].lower() or q in p.get("creator_id","").lower()]

    # Bulk action state
    if "bulk_selected" not in st.session_state:
        st.session_state["bulk_selected"] = set()

    pending_only = [p for p in filtered if p.get("status") == "pending"]
    if pending_only:
        st.markdown(f"**{len(pending_only)} pending** skills await approval")
        select_all = st.checkbox("Select All Pending", key="select_all_pending")
        if select_all:
            st.session_state["bulk_selected"] = {p["skill_id"] for p in pending_only}

        selected = st.session_state["bulk_selected"]
        if selected:
            st.markdown(f'<div class="im-announcement im-announcement-info">{len(selected)} skills selected</div>', unsafe_allow_html=True)
            c_app, c_rej, c_clr = st.columns([2, 2, 2])
            with c_app:
                if st.button("✅ Approve All Selected", type="primary"):
                    success, fail = 0, 0
                    for sid in list(selected):
                        if approve_skill(sid): success += 1
                        else: fail += 1
                    st.session_state["bulk_selected"] = set()
                    msg = f"✅ {success} skills approved."
                    if fail: msg += f" ⚠️ {fail} failed — check audit log."
                    st.success(msg); st.rerun()
            with c_rej:
                if st.button("❌ Reject All Selected"):
                    st.session_state["bulk_reject_mode"] = True
            with c_clr:
                if st.button("✕ Clear Selection"):
                    st.session_state["bulk_selected"] = set(); st.rerun()

            if st.session_state.get("bulk_reject_mode"):
                reason = st.text_area("Rejection reason (applies to all selected) *", key="bulk_reject_reason")
                if st.button("Confirm Reject All", type="primary"):
                    if not reason or len(reason) < 20:
                        st.error("Rejection reason must be at least 20 characters.")
                    else:
                        for sid in list(selected):
                            reject_skill(sid, reason)
                        st.session_state["bulk_selected"] = set()
                        st.session_state["bulk_reject_mode"] = False
                        st.success(f"Rejected {len(selected)} skills."); st.rerun()

    for sk in filtered:
        stat = sk.get("status","pending")
        sid = sk["skill_id"]
        with st.expander(f"{'🆕' if stat=='pending' else '✅' if stat=='approved' else '❌'} {sk['name']} — by {sk.get('creator_id','')}"):
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"**Team:** {sk.get('team','')} | **Category:** {sk.get('category','')}")
                st.markdown(f"**Description:** {sk.get('description','')}")
                st.markdown(f"**Inputs:** {len(sk.get('input_fields',[]))} field(s)")
                proj = sk.get("adoption_projection",{})
                if proj:
                    st.markdown(f"**Projected impact:** {proj.get('hours_saved_per_month',0)} hrs/month · {proj.get('n_adopters',0)} adopters")
            with c2:
                st.markdown(badge(stat.title(), {"pending":"warning","approved":"success","rejected":"danger"}.get(stat,"neutral")), unsafe_allow_html=True)
                if sk.get("rejection_reason"):
                    st.warning(f"Rejection reason: {sk['rejection_reason']}")

            if stat == "pending":
                is_checked = sid in st.session_state["bulk_selected"]
                if st.checkbox("Select for bulk action", value=is_checked, key=f"chk_{sid}"):
                    st.session_state["bulk_selected"].add(sid)
                else:
                    st.session_state["bulk_selected"].discard(sid)

                c_app, c_rej, c_edit = st.columns(3)
                with c_app:
                    if st.button("✅ Approve", key=f"app_{sid}", type="primary"):
                        approve_skill(sid)
                        st.success(f"Approved: {sk['name']}"); st.rerun()
                with c_rej:
                    if st.button("❌ Reject", key=f"rej_{sid}"):
                        st.session_state[f"rejecting_{sid}"] = True
                with c_edit:
                    if st.button("✏️ Edit", key=f"edit_{sid}"):
                        st.session_state[f"admin_editing_{sid}"] = not st.session_state.get(f"admin_editing_{sid}", False)
                if st.session_state.get(f"rejecting_{sid}"):
                    reason = st.text_area("Rejection reason *", key=f"rej_reason_{sid}")
                    if st.button("Confirm Reject", key=f"conf_rej_{sid}"):
                        if len(reason) < 20: st.error("Reason must be at least 20 characters.")
                        else:
                            reject_skill(sid, reason)
                            del st.session_state[f"rejecting_{sid}"]
                            st.success("Skill rejected."); st.rerun()
            else:
                c_edit = st.columns(1)[0]
                with c_edit:
                    if st.button("✏️ Edit", key=f"edit_{sid}"):
                        st.session_state[f"admin_editing_{sid}"] = not st.session_state.get(f"admin_editing_{sid}", False)

            # ── Inline admin edit form ────────────────────────────────────────
            if st.session_state.get(f"admin_editing_{sid}"):
                st.markdown("---")
                st.markdown("**Edit skill** *(status preserved — no re-review triggered)*")
                proj = sk.get("adoption_projection", {})
                with st.form(key=f"admin_edit_form_{sid}"):
                    e_desc = st.text_area("Description", value=sk.get("description",""), key=f"e_desc_{sid}")
                    e_tags = st.text_input("Tags (comma-separated)", value=", ".join(sk.get("tags",[])), key=f"e_tags_{sid}")
                    st.markdown("**Adoption projection**")
                    ec1, ec2, ec3 = st.columns(3)
                    with ec1: e_mins = st.number_input("Minutes saved / run", min_value=0, value=int(proj.get("x_mins",0)), key=f"e_mins_{sid}")
                    with ec2: e_occ  = st.number_input("Occurrences / day", min_value=0, value=int(proj.get("y_occurrences_per_day",0)), key=f"e_occ_{sid}")
                    with ec3: e_nadp = st.number_input("Adopters", min_value=0, value=int(proj.get("n_adopters",0)), key=f"e_nadp_{sid}")
                    e_skill_md = st.text_area("SKILL.md content (leave blank to keep existing)", value="", height=200, key=f"e_md_{sid}")
                    submitted = st.form_submit_button("💾 Save changes", type="primary")

                if submitted:
                    hours_per_month = round(e_mins * e_occ * e_nadp * 22 / 60, 1)
                    new_meta = dict(sk)
                    new_meta["description"] = e_desc
                    new_meta["tags"] = [t.strip() for t in e_tags.split(",") if t.strip()]
                    new_meta["adoption_projection"] = {
                        "x_mins": e_mins,
                        "y_occurrences_per_day": e_occ,
                        "n_adopters": e_nadp,
                        "hours_saved_per_month": hours_per_month,
                    }
                    ok = admin_edit_skill(sid, new_meta, skill_md=e_skill_md)
                    if ok:
                        st.session_state[f"admin_editing_{sid}"] = False
                        st.success("Skill updated."); st.rerun()
                    else:
                        st.error("Update failed — check backend logs.")

# ════════════════════════════════════════════════════════════════════════════
# USER MANAGEMENT
# ════════════════════════════════════════════════════════════════════════════
elif "User" in nav:
    section_heading("User Management", "👥")
    all_users = get_all_users()

    with st.expander("➕ Add New User"):
        with st.form("add_user_form"):
            nu_name = st.text_input("Full Name *")
            nu_user = st.text_input("Username *")
            nu_role = st.selectbox("Role", ["user","creator","admin"])
            try:
                df_t = pd.read_excel("assets/config.xlsx", sheet_name="Teams")
                team_opts = [r["team_name"] for _, r in df_t.iterrows()]
            except: team_opts = ["Catalog Team","Product Team","QA Team"]
            nu_team = st.selectbox("Team", team_opts)
            if st.form_submit_button("Create User"):
                if not nu_name or not nu_user: st.error("Name and username are required.")
                elif any(u["username"] == nu_user for u in all_users): st.error("Username already exists.")
                else:
                    temp_pwd = secrets.token_urlsafe(8)
                    new_u = {"username": nu_user,
                             "password_hash": hashlib.sha256(temp_pwd.encode()).hexdigest(),
                             "role": nu_role, "name": nu_name, "team": nu_team,
                             "enabled": True, "created_at": datetime.now().isoformat(), "last_login": ""}
                    add_user(new_u)
                    log_audit(user["username"], "user_created", nu_user, f"Created user {nu_name} as {nu_role}")
                    st.success(f"User created. Temp password: `{temp_pwd}` (shown once)")
                    st.rerun()

    for u in all_users:
        is_self = u["username"] == user["username"]
        col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
        with col1: st.markdown(f"**{u['name']}** `{u['username']}` · {u.get('team','')}")
        with col2:
            new_role = st.selectbox("Role", ["user","creator","admin"],
                                     index=["user","creator","admin"].index(u.get("role","user")),
                                     key=f"role_{u['username']}", disabled=is_self)
        with col3:
            enabled = st.toggle("Enabled", value=u.get("enabled",True),
                                 key=f"en_{u['username']}", disabled=is_self)
        with col4:
            if st.button("💾 Save", key=f"save_{u['username']}", disabled=is_self):
                old_role = u.get("role","user")
                update_user(u["username"], {"role": new_role, "enabled": enabled})
                if old_role != new_role:
                    log_audit(user["username"], "role_changed", u["username"], f"Role: {old_role} → {new_role}")
                if u.get("enabled") != enabled:
                    log_audit(user["username"], "user_disabled" if not enabled else "user_enabled",
                              u["username"], f"User {'disabled' if not enabled else 'enabled'}")
                st.success("Saved"); st.rerun()
        if is_self:
            st.caption("(You cannot modify your own account)")
        st.markdown('<div class="im-divider"></div>', unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════
# RATE LIMITS
# ════════════════════════════════════════════════════════════════════════════
elif "Rate" in nav:
    section_heading("Rate Limits", "⏱")
    limits = load_rate_limits()
    st.markdown("Configure the maximum number of skill runs per role per day.")

    updated = {}
    for role, vals in limits.items():
        c1, c2, c3 = st.columns([2, 2, 2])
        with c1: st.markdown(f"**{role.title()}**")
        with c2: updated[role] = {"max_runs_per_day": st.number_input(f"Max runs/day ({role})", min_value=1,
                                  value=vals["max_runs_per_day"], key=f"mrd_{role}")}
        with c3: updated[role]["max_runs_per_skill_per_day"] = st.number_input(f"Max runs/skill/day ({role})",
                                  min_value=1, value=vals["max_runs_per_skill_per_day"], key=f"mrsd_{role}")

    if st.button("💾 Save Rate Limits", type="primary"):
        try:
            wb = pd.ExcelFile("assets/config.xlsx")
            with pd.ExcelWriter("assets/config.xlsx", engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
                df_rl = pd.DataFrame([{"role": r, "max_runs_per_day": v["max_runs_per_day"],
                                        "max_runs_per_skill_per_day": v["max_runs_per_skill_per_day"]}
                                       for r, v in updated.items()])
                df_rl.to_excel(writer, sheet_name="RateLimits", index=False)
            log_audit(user["username"], "rate_limit_changed", "all_roles", f"Updated rate limits")
            st.success("Rate limits saved.")
        except Exception as e:
            st.error(f"Could not save: {e}")

# ════════════════════════════════════════════════════════════════════════════
# ANALYTICS
# ════════════════════════════════════════════════════════════════════════════
elif "Analytics" in nav:
    section_heading("Platform Analytics", "📈")
    adoptions = load_json("data/adoptions.json")
    approved = api_list_skills()
    feedback = load_json("data/feedback.json")
    all_stats = compute_hours_saved(period="month")
    all_time = compute_hours_saved(period="all")

    c1, c2, c3 = st.columns(3)
    with c1: st.markdown(f'<div class="im-metric-card"><div class="im-metric-value" style="color:var(--secondary)">{format_hours(all_time["hours"])}h</div><div class="im-metric-label">Hours Saved (All Time)</div></div>', unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="im-metric-card"><div class="im-metric-value">{all_time["runs"]}</div><div class="im-metric-label">Total Runs (All Time)</div></div>', unsafe_allow_html=True)
    with c3: st.markdown(f'<div class="im-metric-card"><div class="im-metric-value">{all_time["unique_users"]}</div><div class="im-metric-label">Unique Users</div></div>', unsafe_allow_html=True)

    # Skill-wise stats
    section_heading("Skill-wise Stats", "🗂")
    rows = []
    for sk in approved:
        sid = sk["skill_id"]
        sk_runs = [a for a in adoptions if a["skill_id"] == sid]
        sk_fb = [f["rating"] for f in feedback if f["skill_id"] == sid]
        x_mins = sk.get("adoption_projection",{}).get("x_mins",0)
        hrs = round(len(sk_runs)*x_mins/60, 1)
        rows.append({"Skill": sk["name"], "Team": sk["team"], "Creator": sk.get("creator_id",""),
                      "Runs": len(sk_runs), "Unique Users": len({a["username"] for a in sk_runs}),
                      "Avg Rating": round(sum(sk_fb)/len(sk_fb),1) if sk_fb else "—",
                      "Hrs Saved": hrs})
    if rows:
        df_sk = pd.DataFrame(rows)
        st.dataframe(df_sk, use_container_width=True)
        csv = df_sk.to_csv(index=False)
        st.download_button("⬇ Download CSV", data=csv, file_name="skill_stats.csv", mime="text/csv")

    # User-wise stats
    section_heading("User-wise Stats", "👥")
    all_users = get_all_users()
    user_rows = []
    for u in all_users:
        u_runs = [a for a in adoptions if a["username"] == u["username"]]
        u_skills = len({a["skill_id"] for a in u_runs})
        last = max((a["ran_at"] for a in u_runs), default="—")[:10]
        user_rows.append({"Name": u["name"], "Team": u.get("team",""), "Role": u.get("role",""),
                           "Total Runs": len(u_runs), "Skills Used": u_skills, "Last Active": last})
    if user_rows:
        df_usr = pd.DataFrame(user_rows)
        st.dataframe(df_usr, use_container_width=True)
        st.download_button("⬇ Download CSV", data=df_usr.to_csv(index=False), file_name="user_stats.csv", mime="text/csv")

# ════════════════════════════════════════════════════════════════════════════
# AUDIT LOG
# ════════════════════════════════════════════════════════════════════════════
elif "Audit" in nav:
    section_heading("Audit Log", "📜")
    audit = sorted(load_json("data/audit_log.json"), key=lambda x: x["created_at"], reverse=True)

    action_types = ["All"] + list({e["action"] for e in audit})
    c_filter, c_search = st.columns([2, 3])
    with c_filter: filter_action = st.selectbox("Filter by Action", action_types)
    with c_search: search_audit = st.text_input("🔍 Search actor or details")

    filtered_audit = audit
    if filter_action != "All": filtered_audit = [e for e in audit if e["action"] == filter_action]
    if search_audit:
        q = search_audit.lower()
        filtered_audit = [e for e in filtered_audit if q in e["actor"].lower() or q in e["details"].lower()]

    action_colors = {"skill_approved":"success","skill_rejected":"danger","skill_submitted":"info",
                     "role_changed":"warning","user_disabled":"warning","user_enabled":"success",
                     "announcement_posted":"secondary","rate_limit_changed":"neutral","user_created":"info"}

    PAGE_SIZE = 25
    total_pages = max(1, (len(filtered_audit)-1)//PAGE_SIZE + 1)
    page = st.number_input("Page", min_value=1, max_value=total_pages, value=1, step=1) - 1
    page_entries = filtered_audit[page*PAGE_SIZE:(page+1)*PAGE_SIZE]

    for entry in page_entries:
        action = entry["action"]
        ts = entry["created_at"][:16].replace("T"," ")
        days_ago = max(0,(datetime.now()-datetime.fromisoformat(entry["created_at"])).days)
        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:12px;padding:10px 0;border-bottom:1px solid var(--neutral-200);">
          <span style="font-size:12px;color:var(--neutral-400);min-width:120px;">{ts}</span>
          {badge(action.replace('_',' ').title(), action_colors.get(action,'neutral'))}
          <span style="font-size:13px;color:var(--neutral-700);flex:1;">{entry['details']}</span>
          <span style="font-size:12px;color:var(--neutral-400);">by {entry['actor']}</span>
        </div>
        """, unsafe_allow_html=True)

    df_audit = pd.DataFrame(filtered_audit)
    if not df_audit.empty:
        st.download_button("⬇ Download as CSV", data=df_audit.to_csv(index=False),
                           file_name="audit_log.csv", mime="text/csv")

# ════════════════════════════════════════════════════════════════════════════
# ANNOUNCEMENTS
# ════════════════════════════════════════════════════════════════════════════
elif "Announcements" in nav:
    section_heading("Platform Announcements", "📢")

    with st.form("new_announcement"):
        ann_title = st.text_input("Title *", max_chars=80)
        ann_msg = st.text_area("Message *", max_chars=300)
        st.markdown(f'<div class="im-form-helper">{len(ann_msg)}/300 characters</div>', unsafe_allow_html=True)

        ann_audience = st.selectbox("Audience", ["all","creators","team"])
        ann_team = None
        if ann_audience == "team":
            try:
                df_t = pd.read_excel("assets/config.xlsx", sheet_name="Teams")
                team_opts = [r["team_name"] for _, r in df_t.iterrows()]
            except: team_opts = ["Catalog Team"]
            ann_team = st.selectbox("Select Team", team_opts)

        ann_type = st.radio("Type", ["info","success","warning","critical"], horizontal=True)
        ann_expires = st.date_input("Expires At (optional)", value=None)

        if st.form_submit_button("📢 Post Announcement", type="primary"):
            if not ann_title or not ann_msg:
                st.error("Title and message are required.")
            elif ann_expires and ann_expires.isoformat() <= datetime.now().date().isoformat():
                st.error("Expiry date must be in the future.")
            else:
                new_ann = {
                    "announcement_id": f"ann{str(uuid.uuid4())[:6]}",
                    "title": ann_title, "message": ann_msg,
                    "audience": ann_audience, "team": ann_team,
                    "type": ann_type, "created_by": user["username"],
                    "created_at": datetime.now().isoformat(),
                    "expires_at": ann_expires.isoformat() if ann_expires else None,
                    "is_active": True
                }
                post_announcement(new_ann)
                log_audit(user["username"], "announcement_posted", new_ann["announcement_id"], f"Posted: {ann_title}")
                st.success("Announcement posted!"); st.rerun()

    # Existing announcements
    section_heading("Active Announcements", "📋")
    all_ann = load_json("data/announcements.json")
    for ann in all_ann:
        type_icons = {"info":"ℹ️","success":"✅","warning":"⚠️","critical":"🚨"}
        status = "Active" if ann.get("is_active") else "Inactive"
        expires = ann.get("expires_at","Never") or "Never"
        st.markdown(f"""
        <div class="im-card">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;">
            <div>
              <strong>{type_icons.get(ann['type'],'')} {ann['title']}</strong>
              <div style="font-size:13px;color:var(--neutral-700);margin-top:4px;">{ann['message']}</div>
              <div style="font-size:12px;color:var(--neutral-400);margin-top:8px;">
                Audience: {ann['audience']} | Expires: {expires} | Status: {status}
              </div>
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)
        col_toggle, col_del = st.columns([3, 1])
        with col_toggle:
            label = "Deactivate" if ann.get("is_active") else "Activate"
            if st.button(label, key=f"toggle_ann_{ann['announcement_id']}"):
                update_announcement(ann["announcement_id"], {"is_active": not ann.get("is_active")})
                st.rerun()
        with col_del:
            if st.button("🗑 Delete", key=f"del_ann_{ann['announcement_id']}"):
                st.session_state[f"confirm_del_{ann['announcement_id']}"] = True
            if st.session_state.get(f"confirm_del_{ann['announcement_id']}"):
                st.warning("Are you sure? This cannot be undone.")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Confirm Delete", key=f"conf_del_{ann['announcement_id']}", type="primary"):
                        delete_announcement(ann["announcement_id"])
                        log_audit(user["username"],"announcement_deleted",ann["announcement_id"],f"Deleted: {ann['title']}")
                        st.rerun()
                with c2:
                    if st.button("Cancel", key=f"canc_del_{ann['announcement_id']}"):
                        del st.session_state[f"confirm_del_{ann['announcement_id']}"]
                        st.rerun()

# ════════════════════════════════════════════════════════════════════════════
# RUN LOGS
# ════════════════════════════════════════════════════════════════════════════
elif "Logs" in nav:
    section_heading("Run Logs", ":material/search:")

    LOG_DIR = Path(__file__).parent.parent.parent / "logs"

    if not LOG_DIR.exists() or not any(LOG_DIR.glob("*.jsonl")):
        st.info("No run logs yet — they appear here after skills are executed.")
    else:
        col_s, col_f = st.columns([3, 2])
        with col_s:
            log_search = st.text_input("Search run ID or skill", placeholder="Search…", key="log_search")
        with col_f:
            log_status = st.selectbox("Status", ["All", "complete", "error"], key="log_status")

        runs = []
        for lf in sorted(LOG_DIR.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True):
            if "_claude" in lf.stem:
                continue
            events = []
            try:
                for line in lf.read_text(encoding="utf-8", errors="replace").splitlines():
                    line = line.strip()
                    if line:
                        try:
                            events.append(json.loads(line))
                        except Exception:
                            pass
            except Exception:
                continue
            if not events:
                continue
            first = events[0]
            final = next((e for e in reversed(events) if e.get("stage") in ("complete", "error")), {})
            runs.append({
                "run_id":    first.get("run_id", lf.stem[:8]),
                "skill_id":  first.get("skill_id", "—"),
                "ts":        datetime.fromtimestamp(first.get("ts", 0)).strftime("%Y-%m-%d %H:%M"),
                "status":    final.get("stage", "running"),
                "exec_time": round(final.get("execution_time", 0), 1),
                "cost_usd":  final.get("cost_usd", 0.0),
                "failed_at": final.get("failed_at", ""),
                "error":     final.get("error", ""),
                "claude_log": final.get("claude_log", lf.stem + "_claude.jsonl"),
                "events":    events,
            })

        if log_search:
            q = log_search.lower()
            runs = [r for r in runs if q in r["run_id"].lower() or q in r["skill_id"].lower()]
        if log_status != "All":
            runs = [r for r in runs if r["status"] == log_status]

        st.caption(f"{len(runs)} run(s) shown")

        for run in runs[:100]:
            icon = "✅" if run["status"] == "complete" else "❌" if run["status"] == "error" else "⏳"
            meta = f"{run['exec_time']}s · ${run['cost_usd']:.4f}" if run["status"] == "complete" else (f"failed at **{run['failed_at']}**" if run["failed_at"] else "")
            label = f"{icon} `{run['run_id']}` &nbsp;·&nbsp; **{run['skill_id']}** &nbsp;·&nbsp; {run['ts']}" + (f" &nbsp;·&nbsp; {meta}" if meta else "")

            with st.expander(f"{icon} {run['run_id']} — {run['skill_id']} — {run['ts']}"):
                # Stage timeline
                st.markdown("**Stages**")
                for ev in run["events"]:
                    stage = ev.get("stage", "")
                    ts_str = datetime.fromtimestamp(ev.get("ts", 0)).strftime("%H:%M:%S")
                    if stage == "error":
                        st.markdown(f"❌ `{ts_str}` **{stage}** — {ev.get('error','')[:120]}")
                    elif stage == "complete":
                        st.markdown(f"✅ `{ts_str}` **{stage}** — {run['exec_time']}s / ${run['cost_usd']:.4f}")
                    elif stage:
                        extra = ""
                        if stage == "assets_fetched":
                            extra = f" — repo: {ev.get('repo_bytes',0)//1024}KB, activities: {ev.get('ticket_activities',0)}"
                        elif stage == "files_uploaded":
                            extra = f" — {ev.get('fetched_paths', [])}"
                        st.markdown(f"▸ `{ts_str}` **{stage}**{extra}")

                # Claude trace
                claude_path = LOG_DIR / run["claude_log"]
                if claude_path.exists():
                    with st.expander("🤖 Claude trace"):
                        try:
                            tool_events = []
                            for line in claude_path.read_text(encoding="utf-8", errors="replace").splitlines():
                                try:
                                    ev = json.loads(line)
                                except Exception:
                                    continue
                                if ev.get("type") == "assistant":
                                    for block in ev.get("message", {}).get("content", []):
                                        if block.get("type") == "tool_use":
                                            name = block["name"]
                                            inp  = block.get("input", {})
                                            if name == "Bash":
                                                cmd = inp.get("command", "")[:200]
                                                tool_events.append(f"**Bash** `{cmd}`")
                                            elif name in ("Read", "Write", "Edit"):
                                                fp = inp.get("file_path", inp.get("path", ""))
                                                tool_events.append(f"**{name}** `{fp}`")
                                            elif name == "Grep":
                                                tool_events.append(f"**Grep** `{inp.get('pattern','')}` in `{inp.get('path','')}`")
                                            else:
                                                tool_events.append(f"**{name}**")
                                        elif block.get("type") == "text" and block.get("text","").strip():
                                            snippet = block["text"].strip()[:120].replace("\n", " ")
                                            tool_events.append(f"*{snippet}*")
                            if tool_events:
                                for t in tool_events:
                                    st.markdown(f"— {t}")
                            else:
                                st.caption("No tool calls found — log may still be raw PTY output.")
                        except Exception as e:
                            st.error(f"Could not read Claude log: {e}")
                else:
                    st.caption("Claude log not found for this run.")
