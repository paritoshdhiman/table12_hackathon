import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from data_loader import (
    load_plant_portfolio, load_trade_blotter, load_fuel_prices,
    load_contract_obligations, load_remit_transactions, load_intraday_prices,
)
from domain import clean_spark_spread
from chart_theme import apply_dark_theme

st.set_page_config(page_title="Portfolio Overview", page_icon="⚡", layout="wide")
st.title("Portfolio Overview")

plants = load_plant_portfolio()
trades = load_trade_blotter()
fuel = load_fuel_prices()
contracts = load_contract_obligations()
remit = load_remit_transactions()
intraday = load_intraday_prices()

# ── Plant Fleet ──────────────────────────────────────────────────────────────
st.header("Plant Fleet")
cols = st.columns(4)
tech_icons = {"CCGT": "🔥", "OCGT": "⚡", "Wind": "💨", "Solar": "☀️"}
for i, (_, p) in enumerate(plants.iterrows()):
    with cols[i]:
        icon = tech_icons.get(p["technology"], "🏭")
        st.metric(
            label=f"{icon} {p['plant_name']}",
            value=f"{p['capacity_mw']:.0f} MW",
            delta=p["technology"],
        )
        st.caption(f"Efficiency: {p['efficiency_pct']}% | Min load: {p['min_stable_load_mw']} MW")
st.caption("Source: data/plant_portfolio/plant_portfolio.csv")

# ── Key Performance Indicators ───────────────────────────────────────────────
st.header("90-Day Key Metrics")
total_pnl = trades["pnl_eur"].sum()
total_trades = len(trades)
total_volume_mwh = (trades["volume_mw"] * 0.25).sum()

avg_gas = fuel["ttf_front_month_eur_mwh"].mean()
avg_co2 = fuel["eu_ets_eur_tco2"].mean()
avg_price = intraday["vwap_eur_mwh"].mean()
avg_css = clean_spark_spread(avg_price, avg_gas, 0.58, avg_co2, 0.349)

trades_with_remit = set(remit["trade_id"].unique())
all_trade_ids = set(trades["trade_id"].unique())
accepted = len(remit[remit["status"] == "ACCEPTED"])
compliance_rate = accepted / total_trades * 100

k1, k2, k3, k4 = st.columns(4)
k1.metric("Total P&L", f"€{total_pnl:,.0f}")
k2.metric("Avg Clean Spark Spread", f"€{avg_css:.1f}/MWh")
k3.metric("REMIT Compliance Rate", f"{compliance_rate:.1f}%")
k4.metric("Total Traded Volume", f"{total_volume_mwh:,.0f} MWh")

st.caption(
    f"P&L source: trade_blotter.csv ({total_trades} trades) | "
    f"CSS inputs: avg VWAP €{avg_price:.1f}, TTF €{avg_gas:.1f}, ETS €{avg_co2:.1f} "
    f"(fuel_prices.csv, intraday_prices_epex.csv) | "
    f"REMIT: {accepted} accepted of {total_trades} trades (remit_transactions.csv)"
)

# ── P&L by Strategy ──────────────────────────────────────────────────────────
st.header("P&L by Trading Strategy")
col_left, col_right = st.columns(2)

with col_left:
    pnl_by_strategy = trades.groupby("strategy")["pnl_eur"].sum().reset_index()
    pnl_by_strategy.columns = ["Strategy", "P&L (€)"]
    fig = px.bar(
        pnl_by_strategy, x="Strategy", y="P&L (€)",
        color="Strategy",
        title="Total P&L by Strategy (90 days)",
        color_discrete_sequence=px.colors.qualitative.Set2,
    )
    fig.update_layout(showlegend=False)
    apply_dark_theme(fig)
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Source: trade_blotter.csv, grouped by strategy column")

with col_right:
    trades_by_dir = trades.groupby(["strategy", "direction"])["pnl_eur"].agg(["sum", "count"]).reset_index()
    trades_by_dir.columns = ["Strategy", "Direction", "P&L (€)", "Count"]
    fig2 = px.bar(
        trades_by_dir, x="Strategy", y="Count", color="Direction",
        barmode="group",
        title="Trade Count by Strategy & Direction",
        color_discrete_map={"BUY": "#9CA3AF", "SELL": "#DC2626"},
    )
    apply_dark_theme(fig2)
    st.plotly_chart(fig2, use_container_width=True)
    st.caption("Source: trade_blotter.csv")

# ── P&L Over Time ────────────────────────────────────────────────────────────
st.header("Cumulative P&L Over Time")
trades_sorted = trades.sort_values("timestamp_executed").copy()
trades_sorted["cumulative_pnl"] = trades_sorted["pnl_eur"].cumsum()
fig3 = px.line(
    trades_sorted, x="timestamp_executed", y="cumulative_pnl",
    title="Cumulative Portfolio P&L",
    labels={"timestamp_executed": "Date", "cumulative_pnl": "Cumulative P&L (€)"},
)
fig3.update_traces(line_color="#DC2626", fill="tozeroy", fillcolor="rgba(220, 38, 38, 0.1)")
apply_dark_theme(fig3)
st.plotly_chart(fig3, use_container_width=True)
st.caption("Source: trade_blotter.csv, pnl_eur cumulative sum ordered by timestamp_executed")

# ── Contract Obligations ─────────────────────────────────────────────────────
st.header("Active Contract Obligations")
contracts_display = contracts[["contract_id", "counterparty", "contract_type",
                               "volume_mw", "price_eur_mwh", "delivery_profile",
                               "tolerance_pct", "penalty_eur_mwh", "plant_id"]].copy()
st.dataframe(contracts_display, use_container_width=True, hide_index=True)

ccgt_contracts = contracts[contracts["plant_id"] == "RHEIN_CCGT"]
peak_commitment = ccgt_contracts[ccgt_contracts["delivery_profile"].isin(["BASELOAD", "PEAK"])]["volume_mw"].sum()
if peak_commitment > 430:
    st.warning(
        f"⚠️ **CCGT Overcommitment Detected:** Peak-hour contract obligations total "
        f"**{peak_commitment:.0f} MW** but Rheinhafen CCGT max capacity is **430 MW**. "
        f"Contracts: {', '.join(ccgt_contracts['contract_id'].tolist())}. "
        f"Resolution: curtail within tolerance bands or procure shortfall from market."
    )
st.caption("Source: data/plant_portfolio/contract_obligations.csv")

# ── Fuel Price Summary ───────────────────────────────────────────────────────
st.header("Fuel & Carbon Price Summary (90-Day)")
f1, f2, f3 = st.columns(3)
f1.metric("Avg TTF Gas", f"€{avg_gas:.2f}/MWh", delta=f"Range: €{fuel['ttf_front_month_eur_mwh'].min():.1f}–€{fuel['ttf_front_month_eur_mwh'].max():.1f}")
f2.metric("Avg EU ETS Carbon", f"€{avg_co2:.2f}/tCO2", delta=f"Range: €{fuel['eu_ets_eur_tco2'].min():.1f}–€{fuel['eu_ets_eur_tco2'].max():.1f}")
f3.metric("Avg Intraday VWAP", f"€{avg_price:.2f}/MWh", delta=f"Range: €{intraday['vwap_eur_mwh'].min():.1f}–€{intraday['vwap_eur_mwh'].max():.1f}")
st.caption("Source: fuel_prices.csv (90 rows), intraday_prices_epex.csv (8,640 rows)")
