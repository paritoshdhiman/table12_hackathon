import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from data_loader import (
    load_intraday_prices, load_day_ahead_prices, load_fuel_prices,
    load_renewable_forecast,
)

st.set_page_config(page_title="Market Analysis", page_icon="📈", layout="wide")
st.title("📈 Market Analysis")

intraday = load_intraday_prices()
da = load_day_ahead_prices()
fuel = load_fuel_prices()
renew = load_renewable_forecast()

# ── Date range selector ──────────────────────────────────────────────────────
all_dates = sorted(intraday["date"].unique())
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("Start date", value=all_dates[0], min_value=all_dates[0], max_value=all_dates[-1])
with col2:
    end_date = st.date_input("End date", value=all_dates[-1], min_value=all_dates[0], max_value=all_dates[-1])

mask = (intraday["date"] >= start_date) & (intraday["date"] <= end_date)
filtered = intraday[mask]

tab1, tab2, tab3, tab4, tab5 = st.tabs(["Prices", "Spreads", "Fuel & Carbon", "Renewables", "Distribution"])

# ── Tab 1: Prices ────────────────────────────────────────────────────────────
with tab1:
    st.subheader("Intraday VWAP vs Day-Ahead Price")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=filtered["timestamp_utc"], y=filtered["vwap_eur_mwh"],
        name="Intraday VWAP", line=dict(color="#636EFA", width=1),
    ))
    fig.add_trace(go.Scatter(
        x=filtered["timestamp_utc"], y=filtered["high_eur_mwh"],
        name="High", line=dict(width=0), showlegend=False,
    ))
    fig.add_trace(go.Scatter(
        x=filtered["timestamp_utc"], y=filtered["low_eur_mwh"],
        name="Low", line=dict(width=0), fill="tonexty",
        fillcolor="rgba(99, 110, 250, 0.1)", showlegend=False,
    ))
    fig.add_trace(go.Scatter(
        x=filtered["timestamp_utc"], y=filtered["day_ahead_price_eur_mwh"],
        name="Day-Ahead", line=dict(color="#EF553B", width=1, dash="dot"),
    ))
    fig.update_layout(
        title="Electricity Prices (€/MWh)",
        yaxis_title="€/MWh", xaxis_title="",
        hovermode="x unified", height=500,
    )
    st.plotly_chart(fig, use_container_width=True)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Mean VWAP", f"€{filtered['vwap_eur_mwh'].mean():.2f}")
    m2.metric("Std Dev", f"€{filtered['vwap_eur_mwh'].std():.2f}")
    m3.metric("Min", f"€{filtered['vwap_eur_mwh'].min():.2f}")
    m4.metric("Max", f"€{filtered['vwap_eur_mwh'].max():.2f}")
    st.caption(f"Source: intraday_prices_epex.csv ({len(filtered)} rows in selected range)")

# ── Tab 2: Spreads ───────────────────────────────────────────────────────────
with tab2:
    st.subheader("Intraday vs Day-Ahead Spread")

    col_l, col_r = st.columns(2)
    with col_l:
        fig_hist = px.histogram(
            filtered, x="spread_id_vs_da_eur_mwh", nbins=80,
            title="Spread Distribution (ID - DA)",
            labels={"spread_id_vs_da_eur_mwh": "Spread (€/MWh)"},
            color_discrete_sequence=["#636EFA"],
        )
        fig_hist.add_vline(x=0, line_dash="dash", line_color="red")
        st.plotly_chart(fig_hist, use_container_width=True)

    with col_r:
        daily_spread = filtered.groupby("date")["spread_id_vs_da_eur_mwh"].mean().reset_index()
        daily_spread.columns = ["Date", "Avg Spread"]
        fig_spread = px.bar(
            daily_spread, x="Date", y="Avg Spread",
            title="Daily Average Spread (ID - DA)",
            color="Avg Spread",
            color_continuous_scale="RdBu_r",
            color_continuous_midpoint=0,
        )
        st.plotly_chart(fig_spread, use_container_width=True)

    s1, s2, s3 = st.columns(3)
    spread = filtered["spread_id_vs_da_eur_mwh"]
    s1.metric("Mean Spread", f"€{spread.mean():.2f}/MWh")
    s2.metric("Positive Spreads", f"{(spread > 0).sum()} ({(spread > 0).mean()*100:.1f}%)")
    s3.metric("Negative Spreads", f"{(spread < 0).sum()} ({(spread < 0).mean()*100:.1f}%)")
    st.caption("Source: intraday_prices_epex.csv, spread_id_vs_da_eur_mwh column")

# ── Tab 3: Fuel & Carbon ────────────────────────────────────────────────────
with tab3:
    st.subheader("Fuel & Carbon Prices (90 Days)")

    fuel_mask = (fuel["date"].dt.date >= start_date) & (fuel["date"].dt.date <= end_date)
    fuel_f = fuel[fuel_mask]

    fig_fuel = make_subplots(specs=[[{"secondary_y": True}]])
    fig_fuel.add_trace(
        go.Scatter(x=fuel_f["date"], y=fuel_f["ttf_front_month_eur_mwh"],
                   name="TTF Gas (€/MWh)", line=dict(color="#FF6692")),
        secondary_y=False,
    )
    fig_fuel.add_trace(
        go.Scatter(x=fuel_f["date"], y=fuel_f["ttf_spot_eur_mwh"],
                   name="TTF Spot (€/MWh)", line=dict(color="#FF6692", dash="dot")),
        secondary_y=False,
    )
    fig_fuel.add_trace(
        go.Scatter(x=fuel_f["date"], y=fuel_f["eu_ets_eur_tco2"],
                   name="EU ETS (€/tCO2)", line=dict(color="#00CC96")),
        secondary_y=True,
    )
    fig_fuel.update_layout(title="TTF Gas & EU ETS Carbon Prices", height=450)
    fig_fuel.update_yaxes(title_text="Gas Price (€/MWh)", secondary_y=False)
    fig_fuel.update_yaxes(title_text="Carbon Price (€/tCO2)", secondary_y=True)
    st.plotly_chart(fig_fuel, use_container_width=True)
    st.caption(f"Source: fuel_prices.csv ({len(fuel_f)} rows in range)")

# ── Tab 4: Renewables ────────────────────────────────────────────────────────
with tab4:
    st.subheader("Renewable Generation Forecasts")

    renew["date"] = renew["timestamp_utc"].dt.date
    renew_mask = (renew["date"] >= start_date) & (renew["date"] <= end_date)
    renew_f = renew[renew_mask]

    re_type = st.radio("Resource", ["Wind", "Solar"], horizontal=True)

    if re_type == "Wind":
        fig_re = go.Figure()
        fig_re.add_trace(go.Scatter(
            x=renew_f["timestamp_utc"], y=renew_f["wind_p90_mw"],
            name="P90", line=dict(width=0), showlegend=True,
        ))
        fig_re.add_trace(go.Scatter(
            x=renew_f["timestamp_utc"], y=renew_f["wind_p10_mw"],
            name="P10", line=dict(width=0), fill="tonexty",
            fillcolor="rgba(99, 110, 250, 0.15)",
        ))
        fig_re.add_trace(go.Scatter(
            x=renew_f["timestamp_utc"], y=renew_f["wind_forecast_mw"],
            name="Forecast", line=dict(color="#636EFA", width=1.5),
        ))
        fig_re.update_layout(title="Wind Generation Forecast (MW)", height=450, yaxis_title="MW")
    else:
        fig_re = go.Figure()
        fig_re.add_trace(go.Scatter(
            x=renew_f["timestamp_utc"], y=renew_f["solar_p90_mw"],
            name="P90", line=dict(width=0), showlegend=True,
        ))
        fig_re.add_trace(go.Scatter(
            x=renew_f["timestamp_utc"], y=renew_f["solar_p10_mw"],
            name="P10", line=dict(width=0), fill="tonexty",
            fillcolor="rgba(255, 165, 0, 0.15)",
        ))
        fig_re.add_trace(go.Scatter(
            x=renew_f["timestamp_utc"], y=renew_f["solar_forecast_mw"],
            name="Forecast", line=dict(color="#FFA500", width=1.5),
        ))
        fig_re.update_layout(title="Solar Generation Forecast (MW)", height=450, yaxis_title="MW")
    st.plotly_chart(fig_re, use_container_width=True)

    col_fe1, col_fe2 = st.columns(2)
    with col_fe1:
        fig_err = px.histogram(
            renew_f, x="forecast_error_mw", nbins=60,
            title="Forecast Error Distribution (Actual − Forecast)",
            labels={"forecast_error_mw": "Error (MW)"},
            color_discrete_sequence=["#AB63FA"],
        )
        fig_err.add_vline(x=0, line_dash="dash", line_color="red")
        st.plotly_chart(fig_err, use_container_width=True)
    with col_fe2:
        st.metric("Mean Forecast Error", f"{renew_f['forecast_error_mw'].mean():.1f} MW")
        st.metric("RMSE", f"{np.sqrt((renew_f['forecast_error_mw']**2).mean()):.1f} MW")
        st.metric("Mean Abs Error", f"{renew_f['forecast_error_mw'].abs().mean():.1f} MW")
    st.caption("Source: renewable_forecast.csv")

# ── Tab 5: Distribution ──────────────────────────────────────────────────────
with tab5:
    st.subheader("Price Distribution by Hour of Day")

    fig_box = px.box(
        filtered, x="hour", y="vwap_eur_mwh",
        title="VWAP Distribution by Hour",
        labels={"hour": "Hour of Day (CET)", "vwap_eur_mwh": "VWAP (€/MWh)"},
        color_discrete_sequence=["#636EFA"],
    )
    st.plotly_chart(fig_box, use_container_width=True)

    st.subheader("Price Heatmap: Hour × Day of Week")
    filtered_copy = filtered.copy()
    filtered_copy["dow"] = pd.to_datetime(filtered_copy["timestamp_utc"]).dt.day_name()
    dow_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    pivot = filtered_copy.groupby(["dow", "hour"])["vwap_eur_mwh"].mean().reset_index()
    pivot_wide = pivot.pivot(index="dow", columns="hour", values="vwap_eur_mwh")
    pivot_wide = pivot_wide.reindex(dow_order)

    fig_hm = px.imshow(
        pivot_wide, aspect="auto",
        title="Average VWAP (€/MWh) by Hour and Day of Week",
        labels=dict(x="Hour", y="Day", color="€/MWh"),
        color_continuous_scale="YlOrRd",
    )
    st.plotly_chart(fig_hm, use_container_width=True)
    st.caption("Source: intraday_prices_epex.csv")
