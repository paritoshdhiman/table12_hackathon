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
    .stMetric {
        background: #1a1f2e;
        padding: 14px 16px;
        border-radius: 8px;
        border: 1px solid #2a3040;
    }
    .stMetric label { font-size: 0.82rem !important; color: #8892a0 !important; }
    .stMetric [data-testid="stMetricValue"] { font-size: 1.6rem !important; }

    div[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0a0e17 0%, #131929 100%);
    }

    .status-badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    .badge-live { background: #00D4AA22; color: #00D4AA; border: 1px solid #00D4AA44; }
    .badge-warn { background: #FFB02E22; color: #FFB02E; border: 1px solid #FFB02E44; }
    .badge-danger { background: #FF4B4B22; color: #FF4B4B; border: 1px solid #FF4B4B44; }

    .finding-box {
        background: #1a1f2e;
        border: 1px solid #2a3040;
        border-radius: 8px;
        padding: 20px;
    }
    .finding-box h4 { margin: 0 0 8px 0; }
    .finding-box p { color: #c0c8d4; font-size: 0.9rem; line-height: 1.55; margin: 0 0 8px 0; }
    .finding-box .source { color: #666e7a; font-size: 0.78rem; font-style: italic; }

    .nav-item { color: #c0c8d4; font-size: 0.9rem; line-height: 1.5; margin-bottom: 6px; }
    .nav-label { color: #e0e4ea; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# ── Header ──────────────────────────────────────────────────────────────────
st.markdown("# Intraday Energy Trading Optimizer")
st.caption("DE-LU Bidding Zone · EPEX SPOT Continuous Market · Quarter-Hourly · 90-Day Analysis Window")

# ── Live Status ─────────────────────────────────────────────────────────────
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

st.markdown("")

# ── Critical Findings ────────────────────────────────────────────────────────
col_l, col_r = st.columns(2)

with col_l:
    st.markdown("""
    <div class="finding-box">
        <h4 style="color: #FF4B4B;">CCGT Overcommitment Risk</h4>
        <p>Peak-hour contract obligations total <strong>450 MW</strong>
        (BL-001: 200 MW + PK-001: 150 MW + BL-002: 100 MW)
        but RHEIN_CCGT maximum capacity is <strong>430 MW</strong>.</p>
        <p><strong>Action:</strong> Curtail BL-001 within 3% tolerance (194 MW) or procure 20 MW shortfall.</p>
        <p class="source">contract_obligations.csv rows 4-6 · plant_portfolio.csv row 2</p>
    </div>
    """, unsafe_allow_html=True)

with col_r:
    st.markdown(f"""
    <div class="finding-box">
        <h4 style="color: #FFB02E;">REMIT Compliance Gap</h4>
        <p><strong>{missing_remit} trades</strong> have no REMIT report filed — violates EU Regulation 2024/1106
        requiring T+1 business day reporting to ACER.</p>
        <p><strong>Penalty exposure:</strong> up to €{missing_remit * 500:,}K (€500K per violation)</p>
        <p class="source">trade_blotter.csv ({len(trades):,} trades) cross-referenced with remit_transactions.csv ({len(remit):,} reports)</p>
    </div>
    """, unsafe_allow_html=True)

st.markdown("")

# ── Architecture ────────────────────────────────────────────────────────────
st.markdown("### System Architecture")
st.markdown(
    "Claude Opus 4.6 on Amazon Bedrock via Strands Agents SDK — "
    "10 specialized data-query tools, each returning source-cited answers. "
    "Greedy merit-order dispatch optimizer with Willans-line part-load efficiency, "
    "temperature-corrected capacity derating, and start-up cost economics."
)

arch_l, arch_r = st.columns(2)
with arch_l:
    st.markdown("""
**Analysis capabilities**
- Market analysis across 8,640 quarter-hourly price periods
- Merit-order dispatch optimization with ramp and min-load constraints
- Scenario simulation: gas, carbon, wind, solar, demand parameters
- REMIT II compliance monitoring with gap detection
""")
with arch_r:
    st.markdown("""
**Risk and compliance**
- Value-at-Risk (95%/99%) with historical simulation
- Contract overcommitment detection (450 MW peak vs 430 MW capacity)
- Imbalance exposure tracking — short/long price spread analysis
- Renewable forecast error quantification (RMSE, bias)
""")

st.markdown("")

# ── Navigation ──────────────────────────────────────────────────────────────
st.markdown("### Pages")

n1, n2, n3 = st.columns(3)
with n1:
    st.markdown("""
<div class="nav-item"><span class="nav-label">AI Daily Briefing</span> — Claude-generated market analysis for any trading day</div>
<div class="nav-item"><span class="nav-label">Portfolio Overview</span> — Plant fleet, KPIs, P&L by strategy</div>
""", unsafe_allow_html=True)
with n2:
    st.markdown("""
<div class="nav-item"><span class="nav-label">Market Analysis</span> — Prices, spreads, fuel, renewables, distribution</div>
<div class="nav-item"><span class="nav-label">Plant Dispatch</span> — Optimal dispatch with merit-order stack and cost curves</div>
""", unsafe_allow_html=True)
with n3:
    st.markdown("""
<div class="nav-item"><span class="nav-label">Scenario Simulator</span> — What-if with sensitivity heatmaps</div>
<div class="nav-item"><span class="nav-label">Compliance & Risk</span> — REMIT, contracts, imbalance, VaR</div>
""", unsafe_allow_html=True)

st.caption(
    "AI Model: Claude Opus 4.6 via Amazon Bedrock · "
    "Agent: Strands SDK 1.56 · "
    "Frontend: Streamlit + Plotly · "
    "Data: 12 CSVs, 55,060 rows, 90 days EPEX SPOT DE-LU · "
    "Grounding: every number traces to source file and row"
)
