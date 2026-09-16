import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from data_loader import (
    load_intraday_prices, load_fuel_prices, load_renewable_forecast,
    load_weather, load_plant_portfolio, load_contract_obligations,
    load_marginal_cost_curves,
)
from dispatch import optimize_dispatch_for_date, summarize_dispatch
from domain import compute_srmc_at_load
import numpy as np

st.set_page_config(page_title="Plant Dispatch", page_icon="🏭", layout="wide")
st.title("🏭 Plant Dispatch Optimizer")

intraday = load_intraday_prices()
fuel = load_fuel_prices()
renew = load_renewable_forecast()
weather = load_weather()
plants = load_plant_portfolio()
contracts = load_contract_obligations()
mc_curves = load_marginal_cost_curves()

all_dates = sorted(intraday["date"].unique())
selected_date = st.date_input(
    "Select date to optimize",
    value=all_dates[0],
    min_value=all_dates[0],
    max_value=all_dates[-1],
)

if st.button("⚡ Optimize Dispatch", type="primary"):
    with st.spinner("Running merit-order dispatch optimization..."):
        dispatch = optimize_dispatch_for_date(
            date=selected_date,
            intraday_prices=intraday,
            fuel_prices=fuel,
            renewable_forecast=renew,
            weather=weather,
            plants=plants,
            contracts=contracts,
        )

    if dispatch.empty:
        st.error("No data found for the selected date.")
    else:
        summary = summarize_dispatch(dispatch)

        # ── Summary Metrics ──────────────────────────────────────────────
        st.header("Dispatch Summary")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Generation", f"{summary['total_generation_mwh']:,.0f} MWh")
        m2.metric("Total Revenue", f"€{summary['total_revenue']:,.0f}")
        m3.metric("Total Cost", f"€{summary['total_cost']:,.0f}")
        m4.metric("Total Margin", f"€{summary['total_margin']:,.0f}")

        day_fuel = fuel[fuel["date"].dt.date == pd.Timestamp(selected_date).date()]
        if not day_fuel.empty:
            fr = day_fuel.iloc[0]
            st.caption(
                f"Fuel inputs: TTF €{fr['ttf_front_month_eur_mwh']:.2f}/MWh, "
                f"EU ETS €{fr['eu_ets_eur_tco2']:.2f}/tCO2 "
                f"(fuel_prices.csv) | Avg CSS: €{summary['avg_css']:.2f}/MWh"
            )

        # ── Stacked Area Chart ───────────────────────────────────────────
        st.header("Dispatch Schedule")
        pivot = dispatch.pivot_table(
            index="delivery_start", columns="plant_id",
            values="dispatch_mw", aggfunc="first",
        ).fillna(0)

        color_map = {
            "RHEIN_CCGT": "#636EFA",
            "ISAR_OCGT": "#EF553B",
            "NORDSEE_WIND": "#00CC96",
            "BAYERN_SOLAR": "#FFA15A",
        }
        fig = go.Figure()
        for plant_id in ["BAYERN_SOLAR", "NORDSEE_WIND", "RHEIN_CCGT", "ISAR_OCGT"]:
            if plant_id in pivot.columns:
                fig.add_trace(go.Scatter(
                    x=pivot.index, y=pivot[plant_id],
                    name=plant_id, stackgroup="one",
                    fillcolor=color_map.get(plant_id, "#999"),
                    line=dict(width=0.5, color=color_map.get(plant_id, "#999")),
                ))

        price_data = dispatch[dispatch["plant_id"] == "RHEIN_CCGT"][["delivery_start", "market_price"]]
        fig.add_trace(go.Scatter(
            x=price_data["delivery_start"], y=price_data["market_price"],
            name="Market Price (€/MWh)", yaxis="y2",
            line=dict(color="black", width=1.5, dash="dot"),
        ))

        fig.update_layout(
            title=f"Generation Dispatch — {selected_date}",
            yaxis=dict(title="Generation (MW)"),
            yaxis2=dict(title="Price (€/MWh)", overlaying="y", side="right"),
            hovermode="x unified", height=500,
        )
        st.plotly_chart(fig, use_container_width=True)

        # ── Per-Plant Summary Table ──────────────────────────────────────
        st.header("Per-Plant Summary")
        st.dataframe(summary["by_plant"], use_container_width=True)

        # ── Marginal Cost Curves ─────────────────────────────────────────
        st.header("Marginal Cost Curves (at today's fuel prices)")
        if not day_fuel.empty:
            gas_p = day_fuel.iloc[0]["ttf_front_month_eur_mwh"]
            co2_p = day_fuel.iloc[0]["eu_ets_eur_tco2"]
        else:
            gas_p = fuel.iloc[-1]["ttf_front_month_eur_mwh"]
            co2_p = fuel.iloc[-1]["eu_ets_eur_tco2"]

        fig_mc = go.Figure()
        for pid in ["RHEIN_CCGT", "ISAR_OCGT"]:
            plant_curves = mc_curves[mc_curves["plant_id"] == pid]
            loads = plant_curves["load_mw"].values
            mcs = [compute_srmc_at_load(pid, l, gas_p, co2_p, plants) for l in loads]
            fig_mc.add_trace(go.Scatter(
                x=loads, y=mcs, name=pid, mode="lines+markers",
                line=dict(color=color_map.get(pid, "#999")),
            ))

        fig_mc.update_layout(
            title=f"Marginal Cost vs Load (Gas €{gas_p:.1f}, Carbon €{co2_p:.1f})",
            xaxis_title="Load (MW)", yaxis_title="Marginal Cost (€/MWh)",
            height=400,
        )
        st.plotly_chart(fig_mc, use_container_width=True)
        st.caption("Source: marginal_cost_curves.csv structure, recalculated with fuel_prices.csv inputs")

        # ── Contract Overcommitment Check ────────────────────────────────
        ccgt_contracts = contracts[contracts["plant_id"] == "RHEIN_CCGT"]
        peak_mw = ccgt_contracts[
            ccgt_contracts["delivery_profile"].isin(["BASELOAD", "PEAK"])
        ]["volume_mw"].sum()
        if peak_mw > 430:
            st.warning(
                f"⚠️ **Peak-hour overcommitment:** CCGT contracts total {peak_mw:.0f} MW "
                f"vs plant capacity 430 MW. Optimizer capped dispatch and flagged shortfall."
            )

        # ── Detailed Table ───────────────────────────────────────────────
        with st.expander("Detailed Dispatch Table (with source citations)"):
            st.dataframe(
                dispatch[["delivery_start", "plant_id", "dispatch_mw",
                          "marginal_cost", "market_price", "margin_eur", "source_citation"]],
                use_container_width=True, hide_index=True, height=400,
            )
