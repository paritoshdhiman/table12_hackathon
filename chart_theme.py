import streamlit as st
import plotly.io as pio
import plotly.graph_objects as go

DARK_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#FAFAFA"),
)

COLORS = {
    "RHEIN_CCGT": "#DC2626",
    "ISAR_OCGT": "#9CA3AF",
    "NORDSEE_WIND": "#EF4444",
    "BAYERN_SOLAR": "#6B7280",
    "primary": "#DC2626",
    "secondary": "#9CA3AF",
    "danger": "#DC2626",
    "warning": "#F59E0B",
}


def apply_dark_theme(fig: go.Figure) -> go.Figure:
    fig.update_layout(**DARK_LAYOUT)
    return fig


GLOBAL_CSS = """
<style>
    .stMetric {
        background: #1C1C1C;
        padding: 14px 16px;
        border-radius: 8px;
        border: 1px solid #2A2A2A;
    }
    .stMetric label { font-size: 0.82rem !important; color: #9CA3AF !important; }
    .stMetric [data-testid="stMetricValue"] { font-size: 1.6rem !important; }

    div[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0A0A0A 0%, #1C1C1C 100%);
    }

    .finding-box, .insight-box, .agent-route {
        background: #1C1C1C;
        border: 1px solid #2A2A2A;
        border-radius: 8px;
    }
    .finding-box { padding: 20px; }
    .finding-box h4 { margin: 0 0 8px 0; }
    .finding-box p { color: #D1D5DB; font-size: 0.9rem; line-height: 1.55; margin: 0 0 8px 0; }
    .finding-box .source { color: #6B7280; font-size: 0.78rem; font-style: italic; }

    .insight-box { padding: 16px; margin: 10px 0; }
    .insight-box.warning { border-color: #F59E0B44; }
    .insight-box.danger { border-color: #DC262644; }
    .insight-box strong { color: #F3F4F6; }
    .insight-box em { color: #6B7280; font-size: 0.82rem; }

    .agent-route { padding: 10px 14px; margin: 4px 0; font-size: 0.85rem; color: #9CA3AF; }
    .agent-route.active { border-color: #DC262644; color: #FAFAFA; }
    .specialist-tag {
        display: inline-block; padding: 2px 8px; border-radius: 4px;
        font-size: 0.72rem; font-weight: 600; margin-right: 4px;
    }
    .tag-market { background: #DC262622; color: #DC2626; }
    .tag-dispatch { background: #9CA3AF22; color: #9CA3AF; }
    .tag-compliance { background: #F59E0B22; color: #F59E0B; }
    .tag-risk { background: #EF444422; color: #EF4444; }

    .status-badge {
        display: inline-block; padding: 3px 10px; border-radius: 4px;
        font-size: 0.75rem; font-weight: 600;
    }
    .badge-live { background: #DC262622; color: #DC2626; border: 1px solid #DC262644; }
    .badge-warn { background: #F59E0B22; color: #F59E0B; border: 1px solid #F59E0B44; }

    .nav-item { color: #D1D5DB; font-size: 0.9rem; line-height: 1.5; margin-bottom: 6px; }
    .nav-label { color: #F3F4F6; font-weight: 600; }

    div[data-testid="stSidebarNav"] li:first-child span {
        visibility: hidden; position: relative;
    }
    div[data-testid="stSidebarNav"] li:first-child span::after {
        content: "Home"; visibility: visible; position: absolute; left: 0;
    }
</style>
"""


def apply_sidebar_branding():
    st.sidebar.markdown("""
<div style="padding: 12px 0 18px 0; border-bottom: 1px solid #2A2A2A; margin-bottom: 12px;">
    <span style="font-size: 1.8rem; font-weight: 700; letter-spacing: 0.04em;">
        <span style="color: #DC2626;">▲</span>
        <span style="color: #FFFFFF;"> DELTA</span>
    </span>
    <div style="color: #6B7280; font-size: 0.7rem; margin-top: 2px; letter-spacing: 0.02em;">
        Dynamic Energy Load & Trading Analytics
    </div>
</div>
""", unsafe_allow_html=True)
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
    st.components.v1.html("""
<script>
function renameAppToHome() {
    const sidebar = window.parent.document.querySelector('[data-testid="stSidebarNav"]');
    if (!sidebar) return false;
    const links = sidebar.querySelectorAll('a span');
    for (const span of links) {
        if (span.textContent.trim() === 'app') {
            span.textContent = 'Home';
            return true;
        }
    }
    return false;
}
if (!renameAppToHome()) {
    const obs = new MutationObserver(() => { if (renameAppToHome()) obs.disconnect(); });
    obs.observe(window.parent.document.body, {childList: true, subtree: true});
    setTimeout(() => obs.disconnect(), 5000);
}
</script>
""", height=0)
