import streamlit as st

# Brand colour constants — mirrors .streamlit/config.toml so CSS components stay in sync
_PRIMARY   = "#2e3192"
_SECONDARY = "#02a699"
_SUCCESS   = "#059669"
_WARNING   = "#d97706"
_DANGER    = "#dc2626"
_INFO      = "#2483d4"

_STRUCTURAL_CSS = f"""
<style>
/* ── Chrome ────────────────────────────────────────────────────── */
#MainMenu {{ visibility: hidden; }}
footer    {{ visibility: hidden; }}
.stDeployButton {{ display: none; }}

/* ── Brand CSS variables (mirrors config.toml) ──────────────────── */
:root {{
  --primary:         {_PRIMARY};
  --primary-light:   #ecedf8;
  --primary-hover:   #23267a;
  --secondary:       {_SECONDARY};
  --secondary-light: #d4f4f2;
  --success:         {_SUCCESS};
  --warning:         {_WARNING};
  --destructive:     {_DANGER};
  --info:            {_INFO};
  --neutral-900:     #0f172a;
  --neutral-700:     #334155;
  --neutral-600:     #64748b;
  --neutral-400:     #94a3b8;
  --neutral-300:     #cbd5e1;
  --neutral-200:     #e2e8f0;
  --neutral-bg:      #f1f5fb;
  --card:            #ffffff;
  --border:          #e2e8f0;
  --dark:            #0f172a;
  --shadow-1:        0 1px 3px rgba(30,42,58,0.06);
  --shadow-2:        0 4px 12px rgba(30,42,58,0.08);
}}

/* ── Top nav ────────────────────────────────────────────────────── */
.im-topnav {{
  background: var(--dark);
  padding: 0 24px;
  height: 52px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: sticky;
  top: 0;
  z-index: 999;
  box-shadow: var(--shadow-2);
  margin: -1rem -1rem 1.5rem -1rem;
}}
.im-topnav-brand     {{ color: #fff; font-size: 15px; font-weight: 700; letter-spacing: -0.02em; }}
.im-topnav-brand span{{ color: var(--secondary); }}
.im-topnav-right     {{ display: flex; align-items: center; gap: 14px; }}
.im-topnav-role      {{ color: rgba(255,255,255,0.5); font-size: 12px; }}
.im-topnav-avatar    {{
  width: 30px; height: 30px; border-radius: 9999px;
  background: var(--primary); color: #fff;
  display: flex; align-items: center; justify-content: center;
  font-size: 12px; font-weight: 700;
}}

/* ── Hero banner ────────────────────────────────────────────────── */
.im-hero {{
  background: linear-gradient(135deg, #2e3192 0%, #1e226a 55%, #02a699 100%);
  border-radius: 12px;
  padding: 24px 28px;
  margin-bottom: 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: #fff;
}}
.im-hero-title       {{ font-size: 18px; font-weight: 700; margin-bottom: 4px; }}
.im-hero-sub         {{ font-size: 13px; color: rgba(255,255,255,0.7); }}
.im-hero-kpi         {{ text-align: right; }}
.im-hero-val         {{ font-size: 34px; font-weight: 800; color: #02a699; font-variant-numeric: tabular-nums; }}
.im-hero-kpi-label   {{ font-size: 12px; color: rgba(255,255,255,0.65); margin-top: 3px; }}

/* ── Generic card ───────────────────────────────────────────────── */
.im-card {{
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 16px;
  box-shadow: var(--shadow-1);
  margin-bottom: 12px;
  transition: box-shadow 0.2s ease, border-color 0.2s ease;
}}
.im-card:hover {{ box-shadow: var(--shadow-2); border-color: var(--secondary); }}

/* ── Metric card ────────────────────────────────────────────────── */
.im-metric-card {{
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 18px 14px;
  text-align: center;
  box-shadow: var(--shadow-1);
}}
.im-metric-value {{ font-size: 26px; font-weight: 700; color: var(--primary); font-variant-numeric: tabular-nums; }}
.im-metric-label {{ font-size: 12px; color: var(--neutral-600); margin-top: 4px; }}

/* ── Badges ─────────────────────────────────────────────────────── */
.im-badge {{
  display: inline-flex; align-items: center;
  padding: 3px 8px; border-radius: 9999px;
  font-size: 11px; font-weight: 600; line-height: 1.4;
  white-space: nowrap;
}}
.im-badge-primary  {{ background: rgba(46,49,146,0.10); color: var(--primary); }}
.im-badge-secondary{{ background: rgba(2,166,153,0.10);  color: var(--secondary); }}
.im-badge-success  {{ background: rgba(5,150,105,0.10);  color: var(--success); }}
.im-badge-warning  {{ background: rgba(215,119,6,0.12);  color: var(--warning); }}
.im-badge-danger   {{ background: rgba(220,38,38,0.10);  color: var(--destructive); }}
.im-badge-info     {{ background: rgba(36,131,212,0.10); color: var(--info); }}
.im-badge-neutral  {{ background: var(--neutral-200);    color: var(--neutral-600); }}
.im-badge-gold     {{ background: rgba(217,119,6,0.12);  color: #b45309; }}

/* ── Step indicator ─────────────────────────────────────────────── */
.im-steps        {{ display: flex; align-items: center; margin-bottom: 24px; }}
.im-step         {{ display: flex; align-items: center; gap: 8px; font-size: 12px; font-weight: 500; color: var(--neutral-400); }}
.im-step.active  {{ color: var(--primary); }}
.im-step.done    {{ color: var(--success); }}
.im-step-num     {{
  width: 22px; height: 22px; border-radius: 9999px;
  display: flex; align-items: center; justify-content: center;
  font-size: 11px; font-weight: 700;
  background: var(--neutral-200); color: var(--neutral-600);
}}
.im-step.active .im-step-num {{ background: var(--primary); color: #fff; }}
.im-step.done   .im-step-num {{ background: var(--success); color: #fff; }}
.im-step-divider {{ flex: 1; height: 1px; background: var(--border); margin: 0 8px; }}

/* ── Announcements ──────────────────────────────────────────────── */
.im-announcement         {{ border-radius: 8px; padding: 12px 16px; margin-bottom: 10px; font-size: 13px; border-left: 3px solid; }}
.im-announcement-info    {{ background: rgba(36,131,212,0.07); border-color: var(--info);        color: var(--neutral-700); }}
.im-announcement-success {{ background: rgba(5,150,105,0.07);  border-color: var(--success);     color: var(--neutral-700); }}
.im-announcement-warning {{ background: rgba(215,119,6,0.09);  border-color: var(--warning);     color: var(--neutral-700); }}
.im-announcement-critical{{ background: rgba(220,38,38,0.07);  border-color: var(--destructive); color: var(--neutral-700); }}

/* ── Output panel ───────────────────────────────────────────────── */
.im-output-panel  {{ border: 1px solid var(--border); border-radius: 10px; overflow: hidden; margin-top: 20px; box-shadow: var(--shadow-2); }}
.im-output-header {{ background: var(--dark); padding: 10px 16px; display: flex; justify-content: space-between; align-items: center; }}
.im-output-header-title {{ color: #fff; font-size: 13px; font-weight: 600; }}
.im-output-header-meta  {{ color: rgba(255,255,255,0.45); font-size: 12px; }}
.im-output-body   {{ padding: 20px; }}

/* ── Loading animation ──────────────────────────────────────────── */
.im-loading {{ width: 100%; padding: 36px 0; text-align: center; }}
.im-loading-bar {{ width: 100%; height: 3px; background: var(--neutral-200); border-radius: 2px; overflow: hidden; margin-bottom: 14px; }}
.im-loading-bar-fill {{
  height: 100%;
  background: linear-gradient(90deg, var(--primary), var(--secondary));
  border-radius: 2px;
  animation: im-slide 1.5s ease-in-out infinite;
}}
@keyframes im-slide {{
  0%   {{ width: 0%;  margin-left: 0%; }}
  50%  {{ width: 60%; margin-left: 20%; }}
  100% {{ width: 0%;  margin-left: 100%; }}
}}
.im-loading-text {{ font-size: 13px; color: var(--neutral-600); animation: im-pulse 1.5s ease-in-out infinite; }}
@keyframes im-pulse {{ 0%,100% {{ opacity: 1; }} 50% {{ opacity: 0.45; }} }}

@media (prefers-reduced-motion: reduce) {{
  .im-loading-bar-fill, .im-loading-text {{ animation: none; }}
  .im-loading-bar-fill {{ width: 100%; margin-left: 0; }}
}}

/* ── Empty state ────────────────────────────────────────────────── */
.im-empty       {{ text-align: center; padding: 48px 24px; color: var(--neutral-400); }}
.im-empty-icon  {{ font-size: 40px; margin-bottom: 12px; }}
.im-empty-title {{ font-size: 16px; font-weight: 600; color: var(--neutral-600); margin-bottom: 6px; }}
.im-empty-sub   {{ font-size: 13px; }}

/* ── Divider ────────────────────────────────────────────────────── */
.im-divider {{ height: 1px; background: var(--border); margin: 14px 0; }}

/* ── Stars ──────────────────────────────────────────────────────── */
.im-stars {{ color: var(--secondary); }}

/* ── Helper text ────────────────────────────────────────────────── */
.im-form-helper {{ font-size: 11px; color: var(--neutral-400); margin-top: 3px; }}
</style>
"""

def inject_css():
    st.markdown(_STRUCTURAL_CSS, unsafe_allow_html=True)

def topnav(user_name: str, role: str):
    initials   = "".join(p[0].upper() for p in user_name.split()[:2])
    role_label = {"user": "Employee", "creator": "Skill Creator", "admin": "Admin"}.get(role, role)
    st.markdown(f"""
    <div class="im-topnav">
      <div class="im-topnav-brand">IM <span>Agentic OS</span></div>
      <div class="im-topnav-right">
        <span class="im-topnav-role">{role_label}</span>
        <div class="im-topnav-avatar">{initials}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

def hero_banner(title: str, subtitle: str, kpi_value: str, kpi_label: str):
    st.markdown(f"""
    <div class="im-hero">
      <div>
        <div class="im-hero-title">{title}</div>
        <div class="im-hero-sub">{subtitle}</div>
      </div>
      <div class="im-hero-kpi">
        <div class="im-hero-val">{kpi_value}</div>
        <div class="im-hero-kpi-label">{kpi_label}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

def badge(text: str, variant: str = "neutral") -> str:
    """Return an inline HTML badge span. Embed inside st.markdown(..., unsafe_allow_html=True)."""
    return f'<span class="im-badge im-badge-{variant}">{text}</span>'

def section_heading(title: str, icon: str = ""):
    st.markdown(f"#### {icon} {title}" if icon else f"#### {title}")

def metric_card(value, label: str, icon: str = ""):
    st.markdown(f"""
    <div class="im-metric-card">
      <div class="im-metric-value">{icon} {value}</div>
      <div class="im-metric-label">{label}</div>
    </div>
    """, unsafe_allow_html=True)

def stars(rating: float, max_stars: int = 5) -> str:
    filled = int(round(rating))
    return "★" * filled + "☆" * (max_stars - filled)

def empty_state(icon: str, title: str, subtitle: str = ""):
    st.markdown(f"""
    <div class="im-empty">
      <div class="im-empty-icon">{icon}</div>
      <div class="im-empty-title">{title}</div>
      <div class="im-empty-sub">{subtitle}</div>
    </div>
    """, unsafe_allow_html=True)

def loading_animation():
    return """
    <div class="im-loading">
      <div class="im-loading-bar"><div class="im-loading-bar-fill"></div></div>
      <div class="im-loading-text">⚙️ Processing your request…</div>
    </div>
    """

def announcement_banner(ann: dict) -> str:
    t = ann.get("type", "info")
    icon_map = {"info": "ℹ️", "success": "✅", "warning": "⚠️", "critical": "🚨"}
    return f"""
    <div class="im-announcement im-announcement-{t}">
      <strong>{icon_map.get(t, '')} {ann['title']}</strong> — {ann['message']}
    </div>
    """
