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
