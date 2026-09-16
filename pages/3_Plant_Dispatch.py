import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from data_loader import (
    load_intraday_prices, load_fuel_prices, load_renewable_forecast,
    load_weather, load_plant_portfolio, load_contract_obligations,
    load_marginal_cost_curves,
)
from dispatch import optimize_dispatch_for_date, summarize_dispatch
from domain import compute_srmc_at_load
from chart_theme import apply_dark_theme, apply_sidebar_branding

st.set_page_config(page_title="DELTA Dispatch", page_icon="▲", layout="wide")
apply_sidebar_branding()
st.title("Plant Dispatch Optimizer")

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

        st.header("Dispatch Schedule")
        pivot = dispatch.pivot_table(
            index="delivery_start", columns="plant_id",
            values="dispatch_mw", aggfunc="first",
        ).fillna(0)

        color_map = {
            "RHEIN_CCGT": "#DC2626",
            "ISAR_OCGT": "#9CA3AF",
            "NORDSEE_WIND": "#EF4444",
            "BAYERN_SOLAR": "#6B7280",
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
            line=dict(color="white", width=1.5, dash="dot"),
        ))

        fig.update_layout(
            title=f"Generation Dispatch — {selected_date}",
            yaxis=dict(title="Generation (MW)"),
            yaxis2=dict(title="Price (€/MWh)", overlaying="y", side="right"),
            hovermode="x unified", height=500,
        )
        apply_dark_theme(fig)
        st.plotly_chart(fig, use_container_width=True)

        st.header("Profit Waterfall")
        by_plant = summary["by_plant"].copy()
        waterfall_plants = by_plant.index.tolist()
        waterfall_margins = by_plant["total_margin"].tolist()
        fig_wf = go.Figure(go.Waterfall(
            x=waterfall_plants + ["Total"],
            y=waterfall_margins + [sum(waterfall_margins)],
            measure=["relative"] * len(waterfall_plants) + ["total"],
            connector={"line": {"color": "#444"}},
            increasing={"marker": {"color": "#9CA3AF"}},
            decreasing={"marker": {"color": "#DC2626"}},
            totals={"marker": {"color": "#111111"}},
            textposition="outside",
            text=[f"€{v:,.0f}" for v in waterfall_margins] + [f"€{sum(waterfall_margins):,.0f}"],
        ))
        fig_wf.update_layout(
            title="Margin Contribution by Plant (Waterfall)",
            yaxis_title="Margin (€)", height=400,
        )
        apply_dark_theme(fig_wf)
        st.plotly_chart(fig_wf, use_container_width=True)
        st.caption("Source: dispatch optimization output — revenue minus SRMC cost per plant")

        st.header("Per-Plant Summary")
        st.dataframe(summary["by_plant"], use_container_width=True)

        st.header("Merit-Order Stack (at today's fuel prices)")
        day_fuel = fuel[fuel["date"].dt.date == pd.Timestamp(selected_date).date()]
        if not day_fuel.empty:
            gas_p_mo = day_fuel.iloc[0]["ttf_front_month_eur_mwh"]
            co2_p_mo = day_fuel.iloc[0]["eu_ets_eur_tco2"]
        else:
            gas_p_mo = fuel.iloc[-1]["ttf_front_month_eur_mwh"]
            co2_p_mo = fuel.iloc[-1]["eu_ets_eur_tco2"]

        from domain import compute_srmc
        stack = []
        for _, p in plants.iterrows():
            if p["technology"] in ("Wind", "Solar"):
                stack.append({"plant": p["plant_id"], "capacity": p["capacity_mw"],
                              "mc": 0, "color": color_map.get(p["plant_id"], "#999")})
            else:
                mc = compute_srmc(gas_p_mo, p["efficiency_pct"]/100, co2_p_mo, p["co2_intensity_tco2_mwh"], p["variable_om_eur_mwh"])
                stack.append({"plant": p["plant_id"], "capacity": p["capacity_mw"],
                              "mc": mc, "color": color_map.get(p["plant_id"], "#999")})
        stack.sort(key=lambda x: x["mc"])

        fig_stack = go.Figure()
        cum_cap = 0
        for s in stack:
            fig_stack.add_trace(go.Scatter(
                x=[cum_cap, cum_cap, cum_cap + s["capacity"], cum_cap + s["capacity"]],
                y=[0, s["mc"], s["mc"], 0],
                fill="toself", fillcolor=s["color"],
                line=dict(color=s["color"], width=1),
                name=f"{s['plant']} ({s['capacity']}MW, €{s['mc']:.0f}/MWh)",
                mode="lines",
                opacity=0.8,
            ))
            fig_stack.add_annotation(
                x=cum_cap + s["capacity"]/2, y=s["mc"]/2 if s["mc"] > 10 else 5,
                text=f"<b>{s['plant']}</b><br>€{s['mc']:.0f}/MWh",
                showarrow=False, font=dict(color="white", size=10),
            )
            cum_cap += s["capacity"]

        avg_price = dispatch["market_price"].mean()
        fig_stack.add_hline(y=avg_price, line_dash="dash", line_color="white",
                           annotation_text=f"Avg Market Price €{avg_price:.0f}/MWh",
                           annotation_font_color="white")
        fig_stack.update_layout(
            title="Merit-Order Stack — Cheapest Generation First",
            xaxis_title="Cumulative Capacity (MW)",
            yaxis_title="Marginal Cost (€/MWh)",
            height=400,
            xaxis=dict(range=[0, cum_cap + 50]),
        )
        apply_dark_theme(fig_stack)
        st.plotly_chart(fig_stack, use_container_width=True)
        st.caption(f"Source: plant_portfolio.csv capacities + fuel_prices.csv (TTF €{gas_p_mo:.2f}, ETS €{co2_p_mo:.2f})")

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
        apply_dark_theme(fig_mc)
        st.plotly_chart(fig_mc, use_container_width=True)
        st.caption("Source: marginal_cost_curves.csv structure, recalculated with fuel_prices.csv inputs")

        ccgt_contracts = contracts[contracts["plant_id"] == "RHEIN_CCGT"]
        peak_mw = ccgt_contracts[
            ccgt_contracts["delivery_profile"].isin(["BASELOAD", "PEAK"])
        ]["volume_mw"].sum()
        ccgt_capacity = plants[plants["plant_id"] == "RHEIN_CCGT"]["capacity_mw"].iloc[0]
        if peak_mw > ccgt_capacity:
            st.warning(
                f"⚠️ **Peak-hour overcommitment:** CCGT contracts total {peak_mw:.0f} MW "
                f"vs plant capacity {ccgt_capacity:.0f} MW. Optimizer capped dispatch and flagged shortfall."
            )

        with st.expander("Detailed Dispatch Table (with source citations)"):
            st.dataframe(
                dispatch[["delivery_start", "plant_id", "dispatch_mw",
                          "marginal_cost", "market_price", "margin_eur", "source_citation"]],
                use_container_width=True, hide_index=True, height=400,
            )

from chat_panel import render_chat_panel
render_chat_panel()
