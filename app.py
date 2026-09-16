import streamlit as st
from data_loader import extract_data_if_needed

st.set_page_config(
    page_title="Energy Trading Optimizer",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

extract_data_if_needed()

st.markdown("""
<style>
    /* Trading desk styling */
    .stMetric {
        background: linear-gradient(135deg, #1a1f2e 0%, #252b3b 100%);
        padding: 15px;
        border-radius: 10px;
        border-left: 4px solid #00D4AA;
    }
    .stMetric label { font-size: 0.85rem !important; color: #8892a0 !important; }
    .stMetric [data-testid="stMetricValue"] { font-size: 1.8rem !important; }

    div[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0a0e17 0%, #131929 100%);
    }

    .hero-title {
        font-size: 2.8rem;
        font-weight: 800;
        background: linear-gradient(90deg, #00D4AA, #00A3FF);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0;
    }
    .hero-sub {
        font-size: 1.1rem;
        color: #8892a0;
        margin-top: -10px;
    }
    .agent-card {
        background: linear-gradient(135deg, #1a1f2e 0%, #252b3b 100%);
        border: 1px solid #2a3040;
        border-radius: 12px;
        padding: 20px;
        margin: 8px 0;
        transition: border-color 0.3s;
    }
    .agent-card:hover { border-color: #00D4AA; }
    .agent-card h4 { color: #00D4AA; margin: 0 0 8px 0; }
    .agent-card p { color: #8892a0; font-size: 0.9rem; margin: 0; }

    .status-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    .badge-live { background: #00D4AA22; color: #00D4AA; border: 1px solid #00D4AA; }
    .badge-warn { background: #FFB02E22; color: #FFB02E; border: 1px solid #FFB02E; }
    .badge-danger { background: #FF4B4B22; color: #FF4B4B; border: 1px solid #FF4B4B; }

    .tech-stack {
        background: #1a1f2e;
        border: 1px solid #2a3040;
        border-radius: 8px;
        padding: 12px 16px;
        font-family: monospace;
        font-size: 0.85rem;
        color: #8892a0;
    }
</style>
""", unsafe_allow_html=True)

# ── Hero Section ─────────────────────────────────────────────────────────────
st.markdown('<p class="hero-title">⚡ Intraday Energy Trading Optimizer</p>', unsafe_allow_html=True)
st.markdown('<p class="hero-sub">DE-LU Bidding Zone &nbsp;|&nbsp; EPEX SPOT Continuous Market &nbsp;|&nbsp; Quarter-Hourly Trading &nbsp;|&nbsp; 90-Day Analysis</p>', unsafe_allow_html=True)
st.markdown("")

# ── Live Status Bar ──────────────────────────────────────────────────────────
from data_loader import load_trade_blotter, load_remit_transactions, load_intraday_prices, load_fuel_prices
trades = load_trade_blotter()
remit = load_remit_transactions()
intraday = load_intraday_prices()
fuel = load_fuel_prices()

total_pnl = trades["pnl_eur"].sum()
accepted = len(remit[remit["status"] == "ACCEPTED"])
compliance_rate = accepted / len(trades) * 100
missing_remit = len(set(trades["trade_id"]) - set(remit["trade_id"]))
latest_price = intraday["vwap_eur_mwh"].iloc[-1]
latest_gas = fuel["ttf_front_month_eur_mwh"].iloc[-1]

s1, s2, s3, s4, s5 = st.columns(5)
s1.metric("Portfolio P&L", f"€{total_pnl:,.0f}", delta=f"{len(trades)} trades")
s2.metric("Latest VWAP", f"€{latest_price:.1f}/MWh")
s3.metric("TTF Gas", f"€{latest_gas:.1f}/MWh")
s4.metric("REMIT Compliance", f"{compliance_rate:.1f}%",
          delta=f"-{missing_remit} unreported", delta_color="inverse")
s5.metric("Data Coverage", "90 Days", delta="8,640 periods")

st.markdown("---")

# ── Multi-Agent Architecture ─────────────────────────────────────────────────
st.markdown("### 🧠 Multi-Agent Architecture")
st.markdown("*Powered by Claude Opus 4.6 on Amazon Bedrock via Strands Agents SDK*")

a1, a2, a3, a4 = st.columns(4)
with a1:
    st.markdown("""
    <div class="agent-card">
        <h4>📊 Market Analyst</h4>
        <p>Analyzes 8,640 quarter-hourly price periods, identifies spread opportunities,
        tracks renewable forecast accuracy, monitors price spikes and negative prices.</p>
    </div>
    """, unsafe_allow_html=True)

with a2:
    st.markdown("""
    <div class="agent-card">
        <h4>🏭 Dispatch Optimizer</h4>
        <p>Merit-order dispatch across 4 plants respecting ramp constraints, min stable load,
        start-up costs (hot/warm/cold), and temperature-corrected efficiency curves.</p>
    </div>
    """, unsafe_allow_html=True)

with a3:
    st.markdown("""
    <div class="agent-card">
        <h4>🛡️ Compliance Officer</h4>
        <p>REMIT II monitoring: 457 unreported trades detected, 55 rejected reports,
        contract tolerance tracking. Penalties up to €500K/violation.</p>
    </div>
    """, unsafe_allow_html=True)

with a4:
    st.markdown("""
    <div class="agent-card">
        <h4>⚠️ Risk Manager</h4>
        <p>Imbalance exposure analysis, contract overcommitment detection (CCGT 450MW peak
        vs 430MW capacity), scenario stress testing with what-if parameters.</p>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# ── Critical Findings ────────────────────────────────────────────────────────
st.markdown("### 🔍 Critical Findings Detected by AI")

f1, f2 = st.columns(2)
with f1:
    st.error("""
    **CCGT Overcommitment Risk**

    Peak-hour contract obligations total **450 MW** (BL-001: 200MW + PK-001: 150MW + BL-002: 100MW)
    but RHEIN_CCGT maximum capacity is **430 MW**.

    *Source: contract_obligations.csv rows 4-6, plant_portfolio.csv row 2*

    **Recommended action:** Curtail BL-001 within 3% tolerance (194 MW) or procure 20 MW shortfall from market.
    """)

with f2:
    st.warning(f"""
    **REMIT Compliance Gap**

    **{missing_remit} trades** have no REMIT report filed — this violates EU Regulation 2024/1106
    requiring T+1 business day reporting to ACER.

    *Source: trade_blotter.csv (2,689 trades) cross-referenced with remit_transactions.csv (2,554 reports)*

    **Potential penalty exposure:** Up to €{missing_remit * 500:,}K (€500K per violation)
    """)

st.markdown("---")

# ── Navigation Guide ─────────────────────────────────────────────────────────
st.markdown("### 📌 Dashboard Navigation")

n1, n2, n3 = st.columns(3)
with n1:
    st.markdown("""
    **📊 Portfolio Overview** — Plant fleet, KPIs, P&L breakdown by strategy

    **📈 Market Analysis** — Price time series, spread analysis, fuel trends, renewable forecasts, price heatmaps
    """)
with n2:
    st.markdown("""
    **🏭 Plant Dispatch** — Optimal dispatch for any date with marginal cost curves and ramp constraints

    **🔬 Scenario Simulator** — What-if analysis: adjust gas, carbon, wind, solar, demand
    """)
with n3:
    st.markdown("""
    **🛡️ Compliance & Risk** — REMIT gaps, contract tracking, imbalance exposure

    **🤖 AI Chat** — Ask anything about the portfolio — every answer cites its source
    """)

st.markdown("---")

# ── Tech Stack ───────────────────────────────────────────────────────────────
st.markdown("### ⚙️ Technology Stack")
st.markdown("""
<div class="tech-stack">
<strong>AI Model:</strong> Claude Opus 4.6 via Amazon Bedrock (us.anthropic.claude-opus-4-6-v1)<br>
<strong>Agent Framework:</strong> Strands Agents SDK 1.56 → 10 specialized data-query tools<br>
<strong>Orchestration:</strong> Amazon Bedrock AgentCore compatible runtime<br>
<strong>Frontend:</strong> Streamlit 1.64 + Plotly interactive charts<br>
<strong>Data:</strong> 12 CSVs (55,060 rows) + 4 reference documents covering 90 days of EPEX SPOT DE-LU<br>
<strong>Grounding:</strong> Every number traces to source file and row — no hallucinated claims
</div>
""", unsafe_allow_html=True)
