import io
import streamlit as st
import json, uuid, zipfile, shutil, requests
import pandas as pd
from pathlib import Path
from datetime import datetime

from components.design_system import inject_css, topnav, badge, section_heading, stars, empty_state, loading_animation, metric_card
from components.auth import require_role, get_current_user, logout
from components.sandbox_client import run_skill, create_skill as api_create_skill, update_skill as api_update_skill, list_all_skills
from components.hours_counter import compute_hours_saved, format_hours
from scripts.fetch_data import fetch_creator_skills

st.set_page_config(page_title="IM Agentic OS — Skill Creator", page_icon=":material/build:", layout="wide")
inject_css()
require_role(["creator", "admin"])
user = get_current_user()

def load_json(path): return json.loads(Path(path).read_text()) if Path(path).exists() else []
def save_json(path, data): Path(path).write_text(json.dumps(data, indent=2))

def load_teams():
    try:
        df = pd.read_excel("assets/config.xlsx", sheet_name="Teams")
        return [r["team_name"] for _, r in df.iterrows() if r.get("is_active")]
    except: return ["Catalog Team","Product Team","QA Team"]

def load_categories(team=None):
    try:
        df = pd.read_excel("assets/config.xlsx", sheet_name="Categories")
        if team:
            df_t = pd.read_excel("assets/config.xlsx", sheet_name="Teams")
            matches = df_t[df_t["team_name"] == team]["team_id"]
            if not matches.empty:
                df = df[df["team_id"] == matches.iloc[0]]
        return [r["category_name"] for _, r in df.iterrows() if r.get("is_active")]
    except: return ["SRS & Docs","Test Cases","Listing Quality"]

def log_audit(actor, action, target, details):
    audit = load_json("data/audit_log.json")
    audit.append({"log_id": f"log{str(uuid.uuid4())[:6]}", "actor": actor,
                  "action": action, "target": target, "details": details,
                  "created_at": datetime.now().isoformat()})
    save_json("data/audit_log.json", audit)

def validate_zip(uploaded_file) -> tuple[bool, list, list, str]:
    """Returns (ok, names, issues, skill_md_content)."""
    issues = []
    skill_md = ""
    try:
        data = uploaded_file.read()
        uploaded_file.seek(0)
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = zf.namelist()
            skill_md_entries = [n for n in names if n.endswith("SKILL.md")]
            if not skill_md_entries:
                issues.append("Missing SKILL.md")
            else:
                skill_md = zf.read(skill_md_entries[0]).decode("utf-8", errors="replace")
            return len(issues) == 0, names, issues, skill_md
    except Exception as e:
        return False, [], [f"Invalid zip file: {e}"], ""


# ── Shared wizard renderer (used for both create and edit) ────────────────────
def _render_skill_wizard():
    if "submit_step" not in st.session_state:
        st.session_state["submit_step"] = 1
    if "skill_draft" not in st.session_state:
        st.session_state["skill_draft"] = {}

    step = st.session_state["submit_step"]
    editing_id = st.session_state.get("editing_skill")

    steps = ["Source", "Metadata", "Input Fields", "Projection & Submit"]
    step_html = ""
    for i, s in enumerate(steps, 1):
        cls = "active" if i == step else ("done" if i < step else "")
        step_html += f'<div class="im-step {cls}"><div class="im-step-num">{"✓" if i < step else i}</div>{s}</div>'
        if i < len(steps): step_html += '<div class="im-step-divider"></div>'
    st.markdown(f'<div class="im-steps">{step_html}</div>', unsafe_allow_html=True)

    draft = st.session_state["skill_draft"]

    # ── STEP 1: SOURCE ────────────────────────────────────────────────────────
    if step == 1:
        source_type = st.radio("How will you provide the skill?", ["📁 Upload ZIP folder", "🔗 Git Repo URL"], horizontal=True)

        if "ZIP" in source_type:
            if editing_id:
                st.markdown(f'<div class="im-form-helper">Current source: <code>{draft.get("source_ref","(unknown)")}</code> — upload a new ZIP to replace SKILL.md, or skip to keep the existing one.</div>', unsafe_allow_html=True)
            uploaded = st.file_uploader("Upload your skill folder as a .zip file", type=["zip"])
            st.markdown('<div class="im-form-helper">Your zip must contain SKILL.md at the root. A scripts/ folder is optional.</div>', unsafe_allow_html=True)
            if uploaded:
                if uploaded.size > 50 * 1024 * 1024:
                    st.error("File exceeds 50MB limit.")
                else:
                    ok, names, issues, skill_md = validate_zip(uploaded)
                    if ok:
                        st.success(f"✅ Valid skill folder detected ({len(names)} files)")
                        with st.expander("View folder contents"):
                            for n in names: st.code(n)
                        draft["source_type"] = "zip"
                        draft["source_ref"] = uploaded.name
                        draft["skill_md"] = skill_md
                    else:
                        st.error("❌ Validation failed:")
                        for issue in issues: st.markdown(f"- {issue}")
        else:
            repo_url = st.text_input("Git Repo URL", placeholder="https://github.com/org/repo",
                                     value=draft.get("source_ref","") if draft.get("source_type") == "repo" else "")
            if repo_url:
                draft["source_ref"] = repo_url
                draft["source_type"] = "repo"
                if st.button("🔍 Validate Repo"):
                    try:
                        r = requests.get(repo_url, timeout=5)
                        if r.status_code < 400:
                            st.success("✅ Repository is accessible")
                        else:
                            st.error("Could not reach this repository. Check the URL or access permissions.")
                    except:
                        st.error("Could not reach this repository. Check the URL or access permissions.")

        # In edit mode the source already exists, so allow proceeding without re-uploading
        can_proceed = bool(draft.get("source_ref")) or bool(editing_id)
        if st.button("Next: Metadata →", type="primary", disabled=not can_proceed):
            st.session_state["submit_step"] = 2
            st.rerun()

    # ── STEP 2: METADATA ──────────────────────────────────────────────────────
    elif step == 2:
        teams = load_teams()

        skill_name = st.text_input("Skill Name *", value=draft.get("name",""), max_chars=60,
                                   help="Alphanumeric, spaces and hyphens only")
        st.markdown(f'<div class="im-form-helper">{len(skill_name)}/60 characters</div>', unsafe_allow_html=True)

        desc = st.text_area("Description *", value=draft.get("description",""), max_chars=300,
                             help='Must start with "Use this skill when..."')
        st.markdown(f'<div class="im-form-helper">{len(desc)}/300 characters · Must start with "Use this skill when..."</div>', unsafe_allow_html=True)

        sel_team = st.selectbox("Team *", teams, index=teams.index(draft["team"]) if draft.get("team") in teams else 0)
        cats = load_categories(sel_team)
        sel_cat = st.selectbox("Category *", cats, index=cats.index(draft["category"]) if draft.get("category") in cats else 0)
        tags_raw = st.text_input("Tags (comma-separated, max 5)", value=",".join(draft.get("tags",[])))

        col_back, col_next = st.columns(2)
        with col_back:
            if st.button("← Back"): st.session_state["submit_step"] = 1; st.rerun()
        with col_next:
            if st.button("Next: Input Fields →", type="primary"):
                tags = [t.strip() for t in tags_raw.split(",") if t.strip()][:5]
                errors = []
                if not skill_name: errors.append("Skill name is required.")
                elif not all(c.isalnum() or c in " -" for c in skill_name): errors.append("Skill name: alphanumeric, spaces, hyphens only.")
                if not desc.startswith("Use this skill when"): errors.append('Description must start with "Use this skill when".')

                # Duplicate name check — allow same name when editing
                existing = list_all_skills()
                existing_names = [s["name"].lower() for s in existing if s.get("skill_id") != editing_id]
                if skill_name.lower() in existing_names:
                    errors.append("A skill with this name already exists.")

                if errors:
                    for e in errors: st.error(e)
                else:
                    draft.update({"name": skill_name, "description": desc,
                                  "team": sel_team, "category": sel_cat, "tags": tags})
                    st.session_state["submit_step"] = 3
                    st.rerun()

    # ── STEP 3: INPUT FIELDS ──────────────────────────────────────────────────
    elif step == 3:
        st.markdown("**Define the inputs users will see when running this skill.**")

        if "input_fields_draft" not in st.session_state:
            st.session_state["input_fields_draft"] = draft.get("input_fields", [
                {"key": "input_1", "label": "Input 1", "type": "text", "required": True, "placeholder": ""}
            ])

        fields = st.session_state["input_fields_draft"]
        field_types = ["text", "textarea", "number", "dropdown", "file_upload", "date"]

        for idx, field in enumerate(fields):
            with st.expander(f"Field {idx+1}: {field.get('label','')}", expanded=True):
                c1, c2, c3 = st.columns([3, 2, 1])
                with c1:
                    field["label"] = st.text_input("Label", value=field.get("label",""), key=f"fl_{idx}")
                    field["key"] = field["label"].lower().replace(" ","_").replace("-","_")
                    field["placeholder"] = st.text_input("Placeholder text", value=field.get("placeholder",""), key=f"fp_{idx}")
                with c2:
                    field["type"] = st.selectbox("Type", field_types, index=field_types.index(field.get("type","text")), key=f"ft_{idx}")
                    field["required"] = st.checkbox("Required", value=field.get("required", True), key=f"fr_{idx}")
                with c3:
                    if st.button("🗑", key=f"del_{idx}", help="Remove field") and len(fields) > 1:
                        fields.pop(idx); st.rerun()

                if field["type"] == "dropdown":
                    opts_raw = st.text_area("Options (one per line)", value="\n".join(field.get("options",[])), key=f"fo_{idx}")
                    field["options"] = [o.strip() for o in opts_raw.split("\n") if o.strip()]
                    st.caption("'Other — enter manually' is automatically appended.")

                if field["type"] == "file_upload":
                    try:
                        df_ft = pd.read_excel("assets/config.xlsx", sheet_name="FileTypes")
                        all_exts = [r["extension"] for _, r in df_ft.iterrows() if r.get("is_active")]
                    except: all_exts = [".pdf",".docx",".xlsx",".csv",".txt",".png",".jpg",".json",".xml"]
                    field["allowed_file_types"] = st.multiselect("Allowed file types", all_exts,
                                                                   default=field.get("allowed_file_types",[".pdf",".txt"]), key=f"fft_{idx}")
                    field["max_file_size"] = st.select_slider("Max file size", ["1MB","5MB","10MB","25MB"],
                                                               value=field.get("max_file_size","10MB"), key=f"ffs_{idx}")

        if st.button("➕ Add Input Field"):
            n = len(fields)+1
            fields.append({"key":f"input_{n}","label":f"Input {n}","type":"text","required":True,"placeholder":""})
            st.rerun()

        show_preview = st.toggle("👁 Preview skill as users will see it", value=st.session_state.get("show_preview", False))
        st.session_state["show_preview"] = show_preview
        if show_preview:
            st.markdown('<div class="im-card" style="border:2px dashed var(--secondary);">', unsafe_allow_html=True)
            st.markdown(f'<div style="font-size:11px;color:var(--secondary);font-weight:600;margin-bottom:12px;">👁 PREVIEW MODE — this is how users will see your skill</div>', unsafe_allow_html=True)
            st.markdown(f"""
            <div class="im-skill-card" style="margin-bottom:16px;">
              <div class="im-skill-name">{draft.get('name','Skill Name')}</div>
              <div style="margin-bottom:8px;">
                {badge(draft.get('team','Team'),'primary')} {badge(draft.get('category','Category'),'secondary')}
              </div>
              <div class="im-skill-desc">{draft.get('description','Skill description...')}</div>
            </div>
            """, unsafe_allow_html=True)
            st.markdown("**Input form preview:**")
            for f in fields:
                lbl = f["label"] + (" *" if f.get("required") else "")
                if f["type"] == "text": st.text_input(lbl, disabled=True, key=f"prev_text_{f['key']}")
                elif f["type"] == "textarea": st.text_area(lbl, disabled=True, key=f"prev_ta_{f['key']}")
                elif f["type"] == "number": st.number_input(lbl, disabled=True, key=f"prev_num_{f['key']}")
                elif f["type"] == "dropdown":
                    opts = f.get("options",[]) + ["Other — enter manually"]
                    st.selectbox(lbl, opts, disabled=True, key=f"prev_dd_{f['key']}")
                elif f["type"] == "file_upload":
                    exts = f.get("allowed_file_types",[])
                    st.file_uploader(lbl + f" ({', '.join(exts)})", disabled=True, key=f"prev_fu_{f['key']}")
            st.button("▶ Run Skill", disabled=True, key="prev_run_btn")
            st.markdown('</div>', unsafe_allow_html=True)

        col_back, col_next = st.columns(2)
        with col_back:
            if st.button("← Back"): st.session_state["submit_step"] = 2; st.rerun()
        with col_next:
            if st.button("Next: Projection & Submit →", type="primary"):
                if len(fields) < 1: st.error("At least 1 input field is required.")
                else:
                    for f in fields:
                        if f["type"] == "dropdown" and not f.get("options"):
                            st.error(f"Field '{f['label']}' (dropdown) needs at least 1 option.")
                            st.stop()
                    draft["input_fields"] = fields
                    st.session_state["submit_step"] = 4; st.rerun()

    # ── STEP 4: PROJECTION & SUBMIT ───────────────────────────────────────────
    elif step == 4:
        section_heading("Adoption Projection", "📈")
        st.markdown("Help judges and admins understand the impact of your skill.")

        c1, c2, c3 = st.columns(3)
        with c1: x_mins = st.number_input("⏱ Minutes per occurrence (X)", min_value=1, value=int(draft.get("adoption_projection",{}).get("x_mins",4)))
        with c2: y_occ = st.number_input("🔄 Occurrences per day per user (Y)", min_value=1, value=int(draft.get("adoption_projection",{}).get("y_occurrences_per_day",3)))
        with c3: n_adopt = st.number_input("👥 Estimated adopters (N)", min_value=1, value=int(draft.get("adoption_projection",{}).get("n_adopters",50)))

        total_mins_day = x_mins * y_occ * n_adopt
        hours_month = round(total_mins_day * 22 / 60, 1)

        st.markdown(f"""
        <div class="im-card" style="background:var(--primary-light);border-color:var(--primary);">
          <div style="font-size:13px;color:var(--primary);font-weight:600;">Projected Impact</div>
          <div style="font-size:22px;font-weight:700;color:var(--primary);margin-top:8px;">
            {total_mins_day:,} min/day = <span style="color:var(--secondary)">{hours_month:,} hours/month</span>
          </div>
          <div style="font-size:13px;color:var(--neutral-600);margin-top:4px;">
            {x_mins} min × {y_occ} runs/day × {n_adopt} users × 22 working days
          </div>
        </div>
        """, unsafe_allow_html=True)

        col_back, col_sub = st.columns(2)
        with col_back:
            if st.button("← Back"): st.session_state["submit_step"] = 3; st.rerun()
        with col_sub:
            btn_label = "💾 Submit Changes for Re-review" if editing_id else "📤 Submit Skill for Approval"
            if st.button(btn_label, type="primary", use_container_width=True):
                draft["adoption_projection"] = {
                    "x_mins": x_mins, "y_occurrences_per_day": y_occ,
                    "n_adopters": n_adopt, "hours_saved_per_month": hours_month
                }
                new_meta = {
                    "skill_id": editing_id if editing_id else draft["name"].lower().replace(" ","-"),
                    "name": draft["name"], "description": draft["description"],
                    "team": draft["team"], "category": draft["category"],
                    "tags": draft.get("tags",[]),
                    "creator_id": user["username"],
                    "version": draft.get("version", 1),
                    "is_featured": draft.get("is_featured", False),
                    "source_type": draft.get("source_type","zip"),
                    "source_ref": draft.get("source_ref",""),
                    "input_fields": draft.get("input_fields",[]),
                    "adoption_projection": draft["adoption_projection"],
                }
                if editing_id:
                    resp = api_update_skill(editing_id, new_meta, skill_md=draft.get("skill_md", ""))
                    action, past = "skill_updated", "Updated"
                else:
                    resp = api_create_skill(new_meta, skill_md=draft.get("skill_md", ""))
                    action, past = "skill_submitted", "Submitted"

                if resp.get("status") != "success":
                    st.error(f"❌ {resp.get('error','Unknown error')}")
                else:
                    log_audit(user["username"], action, new_meta["skill_id"], f"{past} skill: {new_meta['name']}")
                    st.success(f"✅ Skill {past.lower()}! Pending admin approval.")
                    for k in ["submit_step", "skill_draft", "input_fields_draft", "editing_skill"]:
                        st.session_state.pop(k, None)
                    st.rerun()


# ── Top Nav & Logout ──────────────────────────────────────────────────────────
topnav(user["name"], user["role"])
if st.sidebar.button(":material/logout: Sign out"):
    logout(); st.switch_page("app.py")

with st.sidebar:
    st.caption("Skill Creator Portal")
    st.markdown(f"**{user['name']}** · {user['team']}")


# ── Page-level edit mode (overrides tabs so no tab-switching needed) ──────────
_editing_id = st.session_state.get("editing_skill")
if _editing_id:
    col_info, col_cancel = st.columns([5, 1])
    with col_info:
        st.info(f"✏️ **Edit mode** — updating **{_editing_id}**. Changes will go back to pending for admin re-review.")
    with col_cancel:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("✕ Cancel", use_container_width=True):
            for k in ["editing_skill", "skill_draft", "input_fields_draft", "submit_step"]:
                st.session_state.pop(k, None)
            st.rerun()
    section_heading("Edit Skill", "✏️")
    _render_skill_wizard()
    st.stop()


# ── Normal tabs (shown only when not editing) ─────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    ":material/upload: Submit skill",
    ":material/list: My skills",
    ":material/chat: Feedback & ratings",
    ":material/analytics: Analytics",
])

# ════════════════════════════════════════════════════════════════════════════
# TAB 1: SUBMIT SKILL
# ════════════════════════════════════════════════════════════════════════════
with tab1:
    section_heading("Submit a New Skill", "📤")
    _render_skill_wizard()

# ════════════════════════════════════════════════════════════════════════════
# TAB 2: MY SKILLS
# ════════════════════════════════════════════════════════════════════════════
with tab2:
    section_heading("My Skills", "📋")
    my_skills = fetch_creator_skills(user["username"])

    if not my_skills:
        empty_state("🛠", "No skills yet", "Submit your first skill in the 'Submit Skill' tab.")
    else:
        status_color = {"approved":"success","pending":"warning","pending_update":"warning","rejected":"danger"}
        for sk in my_skills:
            stat = sk.get("status","pending")
            col1, col2, col3, col4 = st.columns([4, 2, 2, 2])
            with col1: st.markdown(f"**{sk['name']}** v{sk.get('version',1)}")
            with col2: st.markdown(badge(stat.replace("_"," ").title(), status_color.get(stat,"neutral")), unsafe_allow_html=True)
            with col3: st.markdown(f"<span style='font-size:12px;color:var(--neutral-600);'>{sk.get('created_at','')[:10]}</span>", unsafe_allow_html=True)
            with col4:
                if stat == "approved":
                    if st.button("🧪 Test", key=f"test_{sk['skill_id']}"):
                        st.session_state[f"testing_{sk['skill_id']}"] = True
                if stat in ("approved", "pending"):
                    if st.button("✏️ Edit", key=f"edit_{sk['skill_id']}"):
                        st.session_state["submit_step"] = 1
                        st.session_state["skill_draft"] = dict(sk)
                        st.session_state["editing_skill"] = sk["skill_id"]
                        st.session_state.pop("input_fields_draft", None)
                        st.rerun()
                elif stat == "rejected":
                    if st.button("✏️ Edit & Resubmit", key=f"resub_{sk['skill_id']}"):
                        st.session_state["submit_step"] = 1
                        st.session_state["skill_draft"] = dict(sk)
                        st.session_state["editing_skill"] = sk["skill_id"]
                        st.session_state.pop("input_fields_draft", None)
                        st.rerun()

            if stat == "rejected" and sk.get("rejection_reason"):
                st.warning(f"⚠️ Rejection reason: {sk['rejection_reason']}")

            # Test panel
            if st.session_state.get(f"testing_{sk['skill_id']}"):
                st.markdown(f'<div class="im-announcement im-announcement-warning">🧪 TEST MODE — This run is a test and not counted in adoption stats</div>', unsafe_allow_html=True)
                test_inputs = {}
                with st.form(f"test_form_{sk['skill_id']}"):
                    for f in sk.get("input_fields",[]):
                        if f["type"] == "textarea":
                            test_inputs[f["key"]] = st.text_area(f["label"], key=f"tinp_{sk['skill_id']}_{f['key']}")
                        else:
                            test_inputs[f["key"]] = st.text_input(f["label"], key=f"tinp_{sk['skill_id']}_{f['key']}")
                    if st.form_submit_button("▶ Run Test"):
                        ph = st.empty()
                        ph.markdown(loading_animation(), unsafe_allow_html=True)
                        result = run_skill(sk["skill_id"], test_inputs)
                        ph.empty()
                        if result["status"] == "success":
                            st.success(f"✅ Skill working correctly (completed in {result.get('execution_time_seconds',0):.1f}s)")
                            st.markdown(result["output"][:500] + "...")
                        else:
                            st.error(f"❌ Skill execution failed: {result.get('error','Unknown error')}.")
                if st.button("Close Test", key=f"close_test_{sk['skill_id']}"):
                    del st.session_state[f"testing_{sk['skill_id']}"]
                    st.rerun()

            st.markdown('<div class="im-divider"></div>', unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════
# TAB 3: FEEDBACK & RATINGS
# ════════════════════════════════════════════════════════════════════════════
with tab3:
    section_heading("Feedback & Ratings", "💬")
    my_approved = [s for s in fetch_creator_skills(user["username"]) if s.get("status") == "approved"]

    if not my_approved:
        empty_state("💬", "No approved skills yet", "Get your skills approved to see feedback.")
    else:
        skill_names = [s["name"] for s in my_approved]
        sel_idx = st.selectbox("Select Skill", range(len(skill_names)), format_func=lambda i: skill_names[i])
        sel_skill = my_approved[sel_idx]
        all_feedback = load_json("data/feedback.json")
        skill_fb = [f for f in all_feedback if f["skill_id"] == sel_skill["skill_id"]]

        if not skill_fb:
            empty_state("⭐", "No feedback yet", "Users will leave feedback after running your skill.")
        else:
            ratings = [f["rating"] for f in skill_fb]
            avg = round(sum(ratings)/len(ratings),1)
            c1, c2, c3 = st.columns(3)
            with c1: st.metric("Avg rating", f"{avg}/5 {'★'*int(round(avg))}", border=True)
            with c2: st.metric("Total ratings", len(skill_fb), border=True)
            with c3:
                star_counts = {i: ratings.count(i) for i in range(5,0,-1)}
                st.markdown("**Rating distribution:**")
                for star, count in star_counts.items():
                    bar = "█" * count + "░" * max(0, 5-count)
                    st.markdown(f"{'★'*star} {bar} {count}", unsafe_allow_html=True)

            st.markdown('<div class="im-divider"></div>', unsafe_allow_html=True)
            for fb in sorted(skill_fb, key=lambda x: x["created_at"], reverse=True):
                initials = fb["username"][:2].upper()
                days_ago = max(0,(datetime.now()-datetime.fromisoformat(fb["created_at"])).days)
                st.markdown(f"""
                <div class="im-card">
                  <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">
                    <div class="im-topnav-avatar" style="width:28px;height:28px;font-size:11px;">{initials}</div>
                    <span class="im-stars">{"★"*fb['rating']}{"☆"*(5-fb['rating'])}</span>
                    <span style="font-size:12px;color:var(--neutral-400);">{days_ago}d ago</span>
                  </div>
                  <div style="font-size:14px;color:var(--neutral-700);">{fb.get('comment','No comment.')}</div>
                </div>
                """, unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════
# TAB 4: ADOPTION ANALYTICS
# ════════════════════════════════════════════════════════════════════════════
with tab4:
    section_heading("Adoption Analytics", "📊")
    stats = compute_hours_saved(creator_id=user["username"], period="month")

    with st.container(horizontal=True):
        st.metric("Total runs", stats["runs"], border=True)
        st.metric("Unique users", stats["unique_users"], border=True)
        st.metric("Hours saved (month)", f"{format_hours(stats['hours'])}h", border=True)

    adoptions = load_json("data/adoptions.json")
    my_skill_ids = {s["skill_id"] for s in fetch_creator_skills(user["username"]) if s.get("status")=="approved"}
    my_adoptions = [a for a in adoptions if a["skill_id"] in my_skill_ids]

    if my_adoptions:
        df = pd.DataFrame(my_adoptions)
        df["date"] = pd.to_datetime(df["ran_at"], format="ISO8601").dt.date
        daily = df.groupby("date").size().reset_index(name="runs")
        st.markdown("**Runs per day (last 30 days):**")
        st.bar_chart(daily.set_index("date")["runs"])
    else:
        empty_state("📊", "No usage data yet", "Data appears once users start running your skills.")
