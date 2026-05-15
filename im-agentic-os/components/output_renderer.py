import streamlit as st
from datetime import datetime

def render_output(output: str, execution_time: float = None, skill_name: str = "", source: str = "live"):
    now = datetime.now().strftime("%d %b %Y, %H:%M")
    time_info = f"Completed in {execution_time:.1f}s" if execution_time else ""
    source_tag = " · Mock Mode" if source == "mock" else ""

    st.markdown(f"""
    <div class="im-output-panel">
      <div class="im-output-header">
        <span class="im-output-header-title">✅ Skill Output — {skill_name}</span>
        <span class="im-output-header-meta">{time_info}{source_tag} · {now}</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

    with st.container():
        st.markdown(output)

def render_error(error_msg: str):
    st.markdown(f"""
    <div class="im-card" style="border-color:var(--destructive);background:rgba(220,53,69,0.04)">
      <strong style="color:var(--destructive)">❌ Something went wrong</strong><br>
      <span style="color:var(--neutral-700);font-size:13px">{error_msg}</span>
    </div>
    """, unsafe_allow_html=True)
