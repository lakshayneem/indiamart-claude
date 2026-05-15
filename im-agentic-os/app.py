import streamlit as st
from components.auth import login, is_authenticated

st.set_page_config(
    page_title="IM Agentic OS",
    page_icon=":material/robot_2:",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Minimal chrome-hiding CSS only — theme colours come from config.toml
st.markdown("""
<style>
  header[data-testid="stHeader"]    { display: none !important; }
  section[data-testid="stSidebar"]  { display: none !important; }
  div[data-testid="stDecoration"]   { display: none !important; }
  .block-container { padding-top: 0 !important; padding-bottom: 0 !important; max-width: 100% !important; }

  /* Left brand panel */
  .login-panel {
    background: linear-gradient(145deg, #2e3192 0%, #1a1d6e 55%, #02a699 100%);
    min-height: 100vh;
    padding: 52px 44px;
    color: #fff;
    display: flex;
    flex-direction: column;
    justify-content: center;
  }
  .login-feature { display: flex; align-items: flex-start; gap: 14px; margin-bottom: 18px; }
  .login-feature-icon { font-size: 22px; min-width: 30px; line-height: 1.4; }
  .login-feature-body { font-size: 13px; }
  .login-feature-title { font-weight: 700; font-size: 14px; margin-bottom: 2px; }
  .login-feature-sub   { opacity: 0.72; }
  .cred-table { width: 100%; border-collapse: collapse; margin-top: 8px; }
  .cred-table td { padding: 5px 8px; font-size: 12px; }
  .cred-mono  { font-family: 'Courier New', monospace; background: rgba(255,255,255,0.12);
                border-radius: 4px; padding: 2px 6px; }
  .cred-label { opacity: 0.65; }
</style>
""", unsafe_allow_html=True)

# Route away if already signed in
if is_authenticated():
    role = st.session_state.get("role", "user")
    if role == "admin":
        st.switch_page("pages/3_admin.py")
    elif role == "creator":
        st.switch_page("pages/2_skill_creator.py")
    else:
        st.switch_page("pages/1_user_dashboard.py")

left, right = st.columns([1, 1])

# ── Left: brand panel ─────────────────────────────────────────────────────────
with left:
    st.markdown("""
    <div class="login-panel">
      <div style="margin-bottom:40px;">
        <div style="font-size:36px;margin-bottom:10px;">🤖</div>
        <div style="font-size:26px;font-weight:800;letter-spacing:-0.03em;line-height:1.2;margin-bottom:10px;">
          IM Agentic OS
        </div>
        <div style="font-size:14px;opacity:0.8;max-width:340px;line-height:1.6;">
          IndiaMART's internal AI skills platform — publish, discover, and run
          automation skills in one click. No terminal needed.
        </div>
      </div>

      <div style="margin-bottom:36px;">
        <div class="login-feature">
          <div class="login-feature-icon">⚡</div>
          <div class="login-feature-body">
            <div class="login-feature-title">One-click execution</div>
            <div class="login-feature-sub">Any team, any skill — no code required.</div>
          </div>
        </div>
        <div class="login-feature">
          <div class="login-feature-icon">🛡️</div>
          <div class="login-feature-body">
            <div class="login-feature-title">Admin-governed library</div>
            <div class="login-feature-sub">Every skill reviewed before going live.</div>
          </div>
        </div>
        <div class="login-feature">
          <div class="login-feature-icon">📊</div>
          <div class="login-feature-body">
            <div class="login-feature-title">Measurable impact</div>
            <div class="login-feature-sub">Track hours saved across every team.</div>
          </div>
        </div>
      </div>

      <div style="border-top:1px solid rgba(255,255,255,0.18);padding-top:18px;">
        <div style="font-size:11px;text-transform:uppercase;letter-spacing:0.08em;opacity:0.55;margin-bottom:10px;">
          Demo credentials
        </div>
        <table class="cred-table">
          <tr>
            <td class="cred-label">👤 Employee</td>
            <td><span class="cred-mono">im_user</span></td>
            <td><span class="cred-mono">User@1234</span></td>
          </tr>
          <tr>
            <td class="cred-label">🛠 Creator</td>
            <td><span class="cred-mono">im_creator</span></td>
            <td><span class="cred-mono">Creator@1234</span></td>
          </tr>
          <tr>
            <td class="cred-label">⚙️ Admin</td>
            <td><span class="cred-mono">im_admin</span></td>
            <td><span class="cred-mono">Admin@1234</span></td>
          </tr>
        </table>
      </div>
    </div>
    """, unsafe_allow_html=True)

# ── Right: login form ─────────────────────────────────────────────────────────
with right:
    col_pad, col_form, col_pad2 = st.columns([1, 3, 1])
    with col_form:
        # vertical centering via empty space
        for _ in range(6):
            st.write("")

        st.markdown("### Welcome back")
        st.caption("Sign in to access your IM Agentic OS workspace.")
        st.write("")

        with st.form("login_form"):
            username = st.text_input(
                "Username",
                placeholder="e.g. im_user",
                key="login_username",
            )
            password = st.text_input(
                "Password",
                type="password",
                placeholder="Enter your password",
                key="login_password",
            )
            st.write("")
            submitted = st.form_submit_button(
                ":material/login: Sign in",
                type="primary",
                use_container_width=True,
            )

        if submitted:
            if not username or not password:
                st.error("Please enter both username and password.")
            else:
                result = login(username.strip(), password)
                if result is None:
                    st.error("Invalid username or password.")
                elif isinstance(result, dict) and result.get("error") == "disabled":
                    st.error("Your account is disabled. Contact an admin.")
                else:
                    st.session_state["username"] = result["username"]
                    st.session_state["name"]     = result["name"]
                    st.session_state["role"]     = result["role"]
                    st.session_state["team"]     = result["team"]
                    st.session_state["dismissed_announcements"] = set()
                    st.rerun()

        st.write("")
        st.caption("IndiaMART Hackathon 2026 · IM Agentic OS · Built with Claude Code")
