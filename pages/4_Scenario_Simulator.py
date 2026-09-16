import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from data_loader import (
    load_intraday_prices, load_fuel_prices, load_renewable_forecast,
    load_weather, load_plant_portfolio, load_contract_obligations,
)
from dispatch import optimize_dispatch_for_date, summarize_dispatch
from chart_theme import apply_dark_theme

st.set_page_config(page_title="Scenario Simulator", page_icon="🔬", layout="wide")
st.title("Scenario Simulator")

intraday = load_intraday_prices()
fuel = load_fuel_prices()
renew = load_renewable_forecast()
weather = load_weather()
plants = load_plant_portfolio()
contracts = load_contract_obligations()

all_dates = sorted(intraday["date"].unique())
selected_date = st.date_input(
    "Select date", value=all_dates[0],
    min_value=all_dates[0], max_value=all_dates[-1],
)

day_fuel = fuel[fuel["date"].dt.date == pd.Timestamp(selected_date).date()]
if day_fuel.empty:
    day_fuel = fuel.iloc[[-1]]
actual_gas = float(day_fuel.iloc[0]["ttf_front_month_eur_mwh"])
actual_co2 = float(day_fuel.iloc[0]["eu_ets_eur_tco2"])

st.sidebar.header("Scenario Parameters")
gas_price = st.sidebar.slider("Gas Price (€/MWh)", 15.0, 60.0, actual_gas, 0.5,
                               help=f"Actual: €{actual_gas:.1f}")
co2_price = st.sidebar.slider("Carbon Price (€/tCO2)", 30.0, 120.0, actual_co2, 1.0,
                                help=f"Actual: €{actual_co2:.1f}")
wind_factor = st.sidebar.slider("Wind Capacity Factor", 0.0, 1.5, 1.0, 0.05,
                                 help="1.0 = actual forecast")
solar_factor = st.sidebar.slider("Solar Capacity Factor", 0.0, 1.5, 1.0, 0.05,
                                  help="1.0 = actual forecast")
demand_factor = st.sidebar.slider("Demand / Obligation Factor", 0.8, 1.2, 1.0, 0.05,
                                   help="Scales contract obligations")

if st.button("🚀 Run Scenario Comparison", type="primary"):
    with st.spinner("Running base case dispatch..."):
        base = optimize_dispatch_for_date(
            selected_date, intraday, fuel, renew, weather, plants, contracts,
        )
        base_summary = summarize_dispatch(base)

    with st.spinner("Running scenario dispatch..."):
        scenario = optimize_dispatch_for_date(
            selected_date, intraday, fuel, renew, weather, plants, contracts,
            scenario_overrides={
                "gas_price": gas_price,
                "co2_price": co2_price,
                "wind_factor": wind_factor,
                "solar_factor": solar_factor,
                "demand_factor": demand_factor,
            },
        )
        scen_summary = summarize_dispatch(scenario)

    if base.empty or scenario.empty:
        st.error("No data for selected date.")
    else:
        st.header("Scenario Impact")
        d1, d2, d3, d4 = st.columns(4)
        delta_gen = scen_summary["total_generation_mwh"] - base_summary["total_generation_mwh"]
        delta_rev = scen_summary["total_revenue"] - base_summary["total_revenue"]
        delta_cost = scen_summary["total_cost"] - base_summary["total_cost"]
        delta_margin = scen_summary["total_margin"] - base_summary["total_margin"]

        d1.metric("Generation", f"{scen_summary['total_generation_mwh']:,.0f} MWh",
                  delta=f"{delta_gen:+,.0f} MWh")
        d2.metric("Revenue", f"€{scen_summary['total_revenue']:,.0f}",
                  delta=f"€{delta_rev:+,.0f}")
        d3.metric("Cost", f"€{scen_summary['total_cost']:,.0f}",
                  delta=f"€{delta_cost:+,.0f}", delta_color="inverse")
        d4.metric("Margin", f"€{scen_summary['total_margin']:,.0f}",
                  delta=f"€{delta_margin:+,.0f}")

        st.header("Dispatch Comparison")
        color_map = {
            "RHEIN_CCGT": "#636EFA", "ISAR_OCGT": "#EF553B",
            "NORDSEE_WIND": "#00D4AA", "BAYERN_SOLAR": "#FFA15A",
        }
        plant_order = ["BAYERN_SOLAR", "NORDSEE_WIND", "RHEIN_CCGT", "ISAR_OCGT"]

        fig = make_subplots(rows=1, cols=2, subplot_titles=["Base Case", "Scenario"],
                            shared_yaxes=True)

        for col_idx, (df, label) in enumerate([(base, "Base"), (scenario, "Scenario")], 1):
            pivot = df.pivot_table(
                index="delivery_start", columns="plant_id",
                values="dispatch_mw", aggfunc="first",
            ).fillna(0)
            for pid in plant_order:
                if pid in pivot.columns:
                    fig.add_trace(go.Scatter(
                        x=pivot.index, y=pivot[pid],
                        name=pid if col_idx == 1 else None,
                        stackgroup=label,
                        fillcolor=color_map.get(pid),
                        line=dict(width=0.5, color=color_map.get(pid)),
                        showlegend=(col_idx == 1),
                    ), row=1, col=col_idx)

        fig.update_layout(height=450, yaxis_title="Generation (MW)")
        apply_dark_theme(fig)
        st.plotly_chart(fig, use_container_width=True)

        st.header("Per-Plant Comparison")
        comp = base_summary["by_plant"][["total_gen_mwh", "total_margin"]].copy()
        comp.columns = ["Base Gen (MWh)", "Base Margin (€)"]
        scen_pp = scen_summary["by_plant"][["total_gen_mwh", "total_margin"]].copy()
        scen_pp.columns = ["Scenario Gen (MWh)", "Scenario Margin (€)"]
        comparison = comp.join(scen_pp)
        comparison["Δ Margin (€)"] = comparison["Scenario Margin (€)"] - comparison["Base Margin (€)"]
        st.dataframe(comparison, use_container_width=True)

        st.header("Analysis")
        changes = []
        if gas_price != actual_gas:
            direction = "increase" if gas_price > actual_gas else "decrease"
            changes.append(
                f"Gas price {direction} from €{actual_gas:.1f} to €{gas_price:.1f}/MWh "
                f"{'raises' if gas_price > actual_gas else 'lowers'} CCGT SRMC, "
                f"{'reducing' if gas_price > actual_gas else 'increasing'} thermal dispatch profitability."
            )
        if co2_price != actual_co2:
            direction = "increase" if co2_price > actual_co2 else "decrease"
            changes.append(
                f"Carbon price {direction} from €{actual_co2:.1f} to €{co2_price:.1f}/tCO2 "
                f"affects thermal generation costs (CCGT: 0.349 tCO2/MWh, OCGT: 0.545 tCO2/MWh)."
            )
        if wind_factor != 1.0:
            changes.append(
                f"Wind output scaled to {wind_factor*100:.0f}% of forecast — "
                f"{'more' if wind_factor > 1 else 'less'} zero-marginal-cost generation available."
            )
        if solar_factor != 1.0:
            changes.append(
                f"Solar output scaled to {solar_factor*100:.0f}% of forecast."
            )
        if demand_factor != 1.0:
            changes.append(
                f"Contract obligations scaled to {demand_factor*100:.0f}% "
                f"{'increasing' if demand_factor > 1 else 'decreasing'} must-run generation."
            )
        if changes:
            for c in changes:
                st.markdown(f"- {c}")
        else:
            st.info("No scenario changes applied — both cases are identical.")

        st.caption(
            f"Base case: fuel_prices.csv (gas=€{actual_gas:.2f}, ets=€{actual_co2:.2f}) | "
            f"Scenario: gas=€{gas_price:.2f}, ets=€{co2_price:.2f}, "
            f"wind={wind_factor:.0%}, solar={solar_factor:.0%}, demand={demand_factor:.0%}"
        )

        st.header("Sensitivity Heatmap: Gas × Carbon → Margin")
        with st.spinner("Running sensitivity grid (5×5 = 25 scenarios)..."):
            gas_range = np.linspace(max(15, actual_gas - 10), min(60, actual_gas + 10), 5)
            co2_range = np.linspace(max(30, actual_co2 - 15), min(120, actual_co2 + 15), 5)
            margin_grid = np.zeros((len(co2_range), len(gas_range)))

            for i, co2_v in enumerate(co2_range):
                for j, gas_v in enumerate(gas_range):
                    r = optimize_dispatch_for_date(
                        selected_date, intraday, fuel, renew, weather, plants, contracts,
                        scenario_overrides={"gas_price": gas_v, "co2_price": co2_v,
                                            "wind_factor": wind_factor, "solar_factor": solar_factor,
                                            "demand_factor": demand_factor},
                    )
                    if not r.empty:
                        margin_grid[i, j] = r["margin_eur"].sum()

        fig_heat = px.imshow(
            margin_grid, aspect="auto",
            x=[f"€{g:.0f}" for g in gas_range],
            y=[f"€{c:.0f}" for c in co2_range],
            labels=dict(x="Gas Price (€/MWh)", y="Carbon Price (€/tCO2)", color="Margin (€)"),
            title="Portfolio Margin Sensitivity to Gas & Carbon Prices",
            color_continuous_scale="RdYlGn",
            text_auto=".0f",
        )
        fig_heat.update_traces(textfont_size=11)
        apply_dark_theme(fig_heat)
        st.plotly_chart(fig_heat, use_container_width=True)
        st.caption("Source: 25 dispatch optimizations across gas/carbon price grid | "
                   f"Wind factor: {wind_factor:.0%}, Solar: {solar_factor:.0%}")
