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
