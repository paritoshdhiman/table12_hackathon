import plotly.io as pio
import plotly.graph_objects as go

DARK_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#FAFAFA"),
)

COLORS = {
    "RHEIN_CCGT": "#636EFA",
    "ISAR_OCGT": "#EF553B",
    "NORDSEE_WIND": "#00D4AA",
    "BAYERN_SOLAR": "#FFA15A",
    "primary": "#00D4AA",
    "secondary": "#00A3FF",
    "danger": "#FF4B4B",
    "warning": "#FFB02E",
}


def apply_dark_theme(fig: go.Figure) -> go.Figure:
    fig.update_layout(**DARK_LAYOUT)
    return fig
