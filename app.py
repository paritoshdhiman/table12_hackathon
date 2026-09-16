import streamlit as st
from data_loader import extract_data_if_needed
from chart_theme import apply_sidebar_branding

st.set_page_config(
    page_title="DELTA — Dynamic Energy Load & Trading Analytics",
    page_icon="▲",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_sidebar_branding()

extract_data_if_needed()

from chart_theme import GLOBAL_CSS
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

# ── Header ──────────────────────────────────────────────────────────────────
st.markdown("# ▲ DELTA")
st.caption("Dynamic Energy Load & Trading Analytics · DE-LU Bidding Zone · EPEX SPOT Continuous Market · Quarter-Hourly · 90-Day Analysis Window")

# ── Live Status ─────────────────────────────────────────────────────────────
from data_loader import load_trade_blotter, load_remit_transactions, load_intraday_prices, load_fuel_prices, load_contract_obligations, load_plant_portfolio
trades = load_trade_blotter()
remit = load_remit_transactions()
intraday = load_intraday_prices()
fuel = load_fuel_prices()
contracts = load_contract_obligations()
plants = load_plant_portfolio()

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
s5.metric("Data Coverage", "90 Days", delta=f"{len(intraday):,} periods")

st.markdown("")

# ── Critical Findings ────────────────────────────────────────────────────────
col_l, col_r = st.columns(2)

ccgt_contracts = contracts[contracts["plant_id"] == "RHEIN_CCGT"]
ccgt_peak_contracts = ccgt_contracts[ccgt_contracts["delivery_profile"].isin(["BASELOAD", "PEAK"])]
ccgt_peak_mw = ccgt_peak_contracts["volume_mw"].sum()
ccgt_capacity = plants[plants["plant_id"] == "RHEIN_CCGT"]["capacity_mw"].iloc[0]
ccgt_breakdown = " + ".join(
    f"{row['contract_id']}: {row['volume_mw']:.0f} MW"
    for _, row in ccgt_peak_contracts.iterrows()
)
ccgt_shortfall = ccgt_peak_mw - ccgt_capacity

with col_l:
    st.markdown(f"""
    <div class="finding-box">
        <h4 style="color: #DC2626;">CCGT Overcommitment Risk</h4>
        <p>Peak-hour contract obligations total <strong>{ccgt_peak_mw:.0f} MW</strong>
        ({ccgt_breakdown})
        but RHEIN_CCGT maximum capacity is <strong>{ccgt_capacity:.0f} MW</strong>.</p>
        <p><strong>Action:</strong> Curtail within tolerance bands or procure {ccgt_shortfall:.0f} MW shortfall from market.</p>
        <p class="source">contract_obligations.csv · plant_portfolio.csv</p>
    </div>
    """, unsafe_allow_html=True)

with col_r:
    st.markdown(f"""
    <div class="finding-box">
        <h4 style="color: #F59E0B;">REMIT Compliance Gap</h4>
        <p><strong>{missing_remit} trades</strong> have no REMIT report filed — violates EU Regulation 2024/1106
        requiring T+1 business day reporting to ACER.</p>
        <p><strong>Penalty exposure:</strong> up to €{missing_remit * 500:,}K (€500K per violation)</p>
        <p class="source">trade_blotter.csv ({len(trades):,} trades) cross-referenced with remit_transactions.csv ({len(remit):,} reports)</p>
    </div>
    """, unsafe_allow_html=True)

st.markdown("")

# ── Architecture ────────────────────────────────────────────────────────────
st.markdown("### Multi-Agent Architecture")
st.markdown(
    "**5 Claude Opus 4.6 agents** on Amazon Bedrock via Strands Agents SDK, "
    "deployed on **Amazon Bedrock AgentCore** — "
    "1 orchestrator routes queries to 4 specialist agents, each with dedicated tools and domain expertise. "
    "Greedy merit-order dispatch optimizer with Willans-line part-load efficiency, "
    "temperature-corrected capacity derating, and start-up cost economics."
)

arch_l, arch_r = st.columns(2)
with arch_l:
    st.markdown("""
**Specialist agents** (each a separate Claude instance)
- **Market Analyst** — prices, spreads, fuel trends, renewable forecasts (4 tools)
- **Dispatch Optimizer** — SRMC, merit-order, start-up costs, ramp constraints (5 tools)
- **Compliance Officer** — REMIT reporting, contract tolerances, penalties (4 tools)
- **Risk Manager** — P&L, imbalance exposure, strategy performance (4 tools)
""")
with arch_r:
    st.markdown(f"""
**Analytical capabilities**
- Merit-order dispatch optimization with Willans-line part-load efficiency
- Scenario simulation: 5x5 gas/carbon sensitivity grid
- Value-at-Risk (95%/99%) with drawdown and rolling breach detection
- CCGT overcommitment detection ({ccgt_peak_mw:.0f} MW contracted vs {ccgt_capacity:.0f} MW capacity)
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
    "AI: 5 Claude Opus 4.6 agents via Amazon Bedrock (1 orchestrator + 4 specialists) · "
    "Deployment: Amazon Bedrock AgentCore · "
    "Framework: Strands Agents SDK 1.56 · "
    "Frontend: Streamlit + Plotly · "
    f"Data: 12 CSVs, 90 days EPEX SPOT DE-LU · "
    "Grounding: every number traces to source file and row"
)
