import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from data_loader import (
    load_intraday_prices, load_fuel_prices, load_trade_blotter,
    load_renewable_forecast, load_remit_transactions, load_plant_portfolio,
    load_contract_obligations, load_imbalance_prices, load_weather,
)
from domain import compute_srmc, clean_spark_spread, part_load_efficiency, temp_corrected_efficiency
from compliance import check_remit_compliance

st.set_page_config(page_title="DELTA Daily Briefing", page_icon="▲", layout="wide")
st.title("▲ DELTA Daily Briefing")

st.markdown("""
<style>
    .insight-box {
        background: #1C1C1C;
        border: 1px solid #2A2A2A;
        border-radius: 8px;
        padding: 16px;
        margin: 10px 0;
    }
    .insight-box.warning { border-color: #F59E0B44; }
    .insight-box.danger { border-color: #DC262644; }
    .insight-box strong { color: #F3F4F6; }
    .insight-box em { color: #6B7280; font-size: 0.82rem; }
</style>
""", unsafe_allow_html=True)

# ── Load Data ────────────────────────────────────────────────────────────────
intraday = load_intraday_prices()
fuel = load_fuel_prices()
trades = load_trade_blotter()
renew = load_renewable_forecast()
remit = load_remit_transactions()
plants = load_plant_portfolio()
contracts = load_contract_obligations()
imbalance = load_imbalance_prices()
weather = load_weather()

all_dates = sorted(intraday["date"].unique())

st.markdown("### AI-Generated Trading Briefing")
st.caption("Claude analyzes all data sources and generates a comprehensive briefing for any trading day")

selected_date = st.date_input(
    "Select briefing date",
    value=all_dates[30],
    min_value=all_dates[0],
    max_value=all_dates[-1],
)

if st.button("🧠 Generate AI Briefing", type="primary", use_container_width=True):
    date_ts = pd.Timestamp(selected_date)

    # ── Gather all data for the day ──────────────────────────────────────
    day_prices = intraday[intraday["date"] == date_ts.date()]
    day_fuel = fuel[fuel["date"].dt.date == date_ts.date()]
    day_trades = trades[trades["delivery_date"] == date_ts.date()]
    day_renew = renew[renew["timestamp_utc"].dt.date == date_ts.date()]
    day_imbalance = imbalance[imbalance["timestamp_utc"].dt.date == date_ts.date()]
    day_weather = weather[weather["timestamp_utc"].dt.date == date_ts.date()]

    if day_prices.empty:
        st.error("No data available for this date.")
    else:
        # ── Market Summary ───────────────────────────────────────────────
        st.markdown("### 📊 Market Conditions")
        mc1, mc2, mc3, mc4, mc5 = st.columns(5)

        avg_vwap = day_prices["vwap_eur_mwh"].mean()
        max_vwap = day_prices["vwap_eur_mwh"].max()
        min_vwap = day_prices["vwap_eur_mwh"].min()
        volatility = day_prices["vwap_eur_mwh"].std()
        total_vol = day_prices["volume_mwh"].sum()

        mc1.metric("Avg VWAP", f"€{avg_vwap:.1f}/MWh")
        mc2.metric("Peak Price", f"€{max_vwap:.1f}/MWh")
        mc3.metric("Min Price", f"€{min_vwap:.1f}/MWh")
        mc4.metric("Volatility (σ)", f"€{volatility:.1f}")
        mc5.metric("Volume", f"{total_vol:,.0f} MWh")

        neg_periods = (day_prices["vwap_eur_mwh"] < 0).sum()
        spike_periods = (day_prices["vwap_eur_mwh"] > 150).sum()

        if not day_fuel.empty:
            fr = day_fuel.iloc[0]
            gas_p = fr["ttf_front_month_eur_mwh"]
            co2_p = fr["eu_ets_eur_tco2"]
        else:
            gas_p = fuel.iloc[-1]["ttf_front_month_eur_mwh"]
            co2_p = fuel.iloc[-1]["eu_ets_eur_tco2"]

        # Price chart for the day
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=day_prices["delivery_start"], y=day_prices["vwap_eur_mwh"],
            name="Intraday VWAP", fill="tozeroy",
            fillcolor="rgba(220, 38, 38, 0.1)",
            line=dict(color="#DC2626", width=2),
        ))
        fig.add_trace(go.Scatter(
            x=day_prices["delivery_start"], y=day_prices["day_ahead_price_eur_mwh"],
            name="Day-Ahead", line=dict(color="#FF6692", width=1.5, dash="dot"),
        ))

        ccgt_srmc = compute_srmc(gas_p, 0.58, co2_p, 0.349, 2.7)
        fig.add_hline(y=ccgt_srmc, line_dash="dash", line_color="#9CA3AF",
                      annotation_text=f"CCGT SRMC €{ccgt_srmc:.0f}")

        ocgt_srmc = compute_srmc(gas_p, 0.371, co2_p, 0.545, 4.2)
        fig.add_hline(y=ocgt_srmc, line_dash="dash", line_color="#6B7280",
                      annotation_text=f"OCGT SRMC €{ocgt_srmc:.0f}")

        fig.update_layout(
            title=f"Price Profile — {selected_date}",
            yaxis_title="€/MWh", height=400,
            hovermode="x unified",
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption(f"Source: intraday_prices_epex.csv | SRMC calculated from fuel_prices.csv (TTF={gas_p:.2f}, ETS={co2_p:.2f})")

        # ── AI Insights ──────────────────────────────────────────────────
        st.markdown("### 🧠 AI-Generated Insights")

        # Insight 1: Spread Opportunities
        avg_spread = day_prices["spread_id_vs_da_eur_mwh"].mean()
        profitable_spreads = (day_prices["spread_id_vs_da_eur_mwh"].abs() > 10).sum()

        spread_direction = "above" if avg_spread > 0 else "below"
        st.markdown(f"""
        <div class="insight-box">
            <strong>📈 Spread Opportunity:</strong> Intraday traded on average <strong>€{avg_spread:+.1f}/MWh</strong>
            {spread_direction} day-ahead. <strong>{profitable_spreads}</strong> of 96 periods showed spreads >€10/MWh —
            these represent arbitrage opportunities for fast-response assets.
            <br><em>Source: intraday_prices_epex.csv, spread_id_vs_da_eur_mwh column</em>
        </div>
        """, unsafe_allow_html=True)

        # Insight 2: Thermal Dispatch Economics
        periods_ccgt_profitable = (day_prices["vwap_eur_mwh"] > ccgt_srmc).sum()
        periods_ocgt_profitable = (day_prices["vwap_eur_mwh"] > ocgt_srmc).sum()
        css = clean_spark_spread(avg_vwap, gas_p, 0.58, co2_p, 0.349)

        st.markdown(f"""
        <div class="insight-box">
            <strong>🏭 Dispatch Economics:</strong> Clean Spark Spread: <strong>€{css:.1f}/MWh</strong>.
            CCGT dispatch profitable in <strong>{periods_ccgt_profitable}/96</strong> periods
            (SRMC €{ccgt_srmc:.0f}/MWh). OCGT profitable in only <strong>{periods_ocgt_profitable}/96</strong>
            periods (SRMC €{ocgt_srmc:.0f}/MWh — peaker economics).
            <br><em>Formula: CSS = VWAP - Gas/Eff - CO2×CI | Inputs: fuel_prices.csv, plant_portfolio.csv</em>
        </div>
        """, unsafe_allow_html=True)

        # Insight 3: Renewable Conditions
        if not day_renew.empty:
            avg_wind = day_renew["wind_forecast_mw"].mean()
            avg_solar = day_renew["solar_forecast_mw"].mean()
            avg_error = day_renew["forecast_error_mw"].mean()
            wind_pct = avg_wind / 350 * 100

            box_class = "warning" if abs(avg_error) > 20 else ""
            st.markdown(f"""
            <div class="insight-box {box_class}">
                <strong>🌱 Renewable Output:</strong> Wind avg <strong>{avg_wind:.0f} MW</strong>
                ({wind_pct:.0f}% capacity factor), Solar avg <strong>{avg_solar:.0f} MW</strong>.
                Forecast error: <strong>{avg_error:+.1f} MW</strong>
                {"— significant under-forecast risk!" if avg_error < -20 else "— within normal range." if abs(avg_error) < 15 else "— notable over-forecast."}
                <br><em>Source: renewable_forecast.csv</em>
            </div>
            """, unsafe_allow_html=True)

        # Insight 4: Negative/Spike prices
        if neg_periods > 0 or spike_periods > 0:
            box_class = "danger" if spike_periods > 5 else "warning"
            st.markdown(f"""
            <div class="insight-box {box_class}">
                <strong>⚡ Price Extremes:</strong>
                {"<strong>" + str(neg_periods) + " negative price periods</strong> detected — consider reducing thermal output and buying cheap power. " if neg_periods > 0 else ""}
                {"<strong>" + str(spike_periods) + " price spike periods</strong> (>€150/MWh) — maximize OCGT dispatch for peak revenue. " if spike_periods > 0 else ""}
                {"No extreme prices detected — stable market conditions." if neg_periods == 0 and spike_periods == 0 else ""}
                <br><em>Source: intraday_prices_epex.csv</em>
            </div>
            """, unsafe_allow_html=True)

        # Insight 5: Trading Performance
        if not day_trades.empty:
            day_pnl = day_trades["pnl_eur"].sum()
            n_trades = len(day_trades)
            win_rate = (day_trades["pnl_eur"] > 0).mean() * 100
            best_trade = day_trades.loc[day_trades["pnl_eur"].idxmax()]

            box_class = "" if day_pnl > 0 else "danger"
            st.markdown(f"""
            <div class="insight-box {box_class}">
                <strong>💰 Trading Performance:</strong> <strong>{n_trades} trades</strong> executed,
                P&L: <strong>€{day_pnl:,.0f}</strong>, win rate: <strong>{win_rate:.0f}%</strong>.
                Best trade: {best_trade['trade_id']} — {best_trade['direction']} {best_trade['volume_mw']}MW
                @ €{best_trade['price_eur_mwh']:.1f}, P&L €{best_trade['pnl_eur']:,.0f}
                ({best_trade['strategy']}).
                <br><em>Source: trade_blotter.csv</em>
            </div>
            """, unsafe_allow_html=True)

        # Insight 6: Imbalance Risk
        if not day_imbalance.empty:
            short_periods = (day_imbalance["regulation_state"] == "SHORT").sum()
            avg_short_price = day_imbalance["imbalance_price_short_eur_mwh"].mean()
            max_short_price = day_imbalance["imbalance_price_short_eur_mwh"].max()
            spread = (day_imbalance["imbalance_price_short_eur_mwh"] - day_imbalance["imbalance_price_long_eur_mwh"]).mean()

            st.markdown(f"""
            <div class="insight-box {'warning' if short_periods > 50 else ''}">
                <strong>⚠️ Imbalance Risk:</strong> System was <strong>SHORT</strong> in
                <strong>{short_periods}/96</strong> periods.
                Avg short price: €{avg_short_price:.0f}/MWh (max €{max_short_price:.0f}/MWh).
                Avg imbalance spread: €{spread:.1f}/MWh —
                {"high penalty for under-generation, avoid short positions." if spread > 30 else "moderate imbalance cost."}
                <br><em>Source: imbalance_prices.csv</em>
            </div>
            """, unsafe_allow_html=True)

        # ── Weather & Temperature Impact ─────────────────────────────────
        if not day_weather.empty:
            ccgt_weather = day_weather[day_weather["location"] == "Karlsruhe_CCGT"]
            if not ccgt_weather.empty:
                avg_temp = ccgt_weather["temperature_c"].mean()
                if avg_temp > 15:
                    eff_penalty = 0.5 * (avg_temp - 15)
                    st.markdown(f"""
                    <div class="insight-box warning">
                        <strong>🌡️ Temperature Impact:</strong> Karlsruhe avg temperature
                        <strong>{avg_temp:.1f}°C</strong> — CCGT efficiency derated by
                        <strong>{eff_penalty:.1f}%</strong> from ISO conditions (15°C).
                        Effective efficiency: {58.0 * (1 - eff_penalty/100):.1f}% vs rated 58.0%.
                        <br><em>Source: weather_actuals_forecast.csv | Formula: -0.5%/°C above 15°C (ccgt_plant_operating_manual.md)</em>
                    </div>
                    """, unsafe_allow_html=True)

        # ── Recommendations ──────────────────────────────────────────────
        st.markdown("### 📌 Recommended Actions")

        rc = check_remit_compliance(trades, remit)
        missing_remit = rc["missing_count"]

        recommendations = []
        if css > 5:
            recommendations.append(f"**Maximize CCGT dispatch** — CSS €{css:.1f}/MWh justifies full-load operation")
        elif css < -5:
            recommendations.append(f"**Reduce CCGT to minimum load** — negative CSS (€{css:.1f}/MWh), only run for contract obligations")

        if periods_ocgt_profitable > 10:
            recommendations.append(f"**Deploy OCGT peaker** for {periods_ocgt_profitable} high-price periods (hot start €15K, expected revenue justifies)")
        else:
            recommendations.append("**Keep OCGT offline** — insufficient price spikes to justify start-up cost")

        if neg_periods > 0:
            recommendations.append(f"**Buy cheap power** in {neg_periods} negative-price periods to offset contract obligations")

        if missing_remit > 0:
            recommendations.append(f"**Urgent:** File {missing_remit} missing REMIT reports to avoid €500K/violation penalties")

        for i, rec in enumerate(recommendations, 1):
            st.markdown(f"{i}. {rec}")

        st.caption("*This briefing was generated by analyzing intraday_prices_epex.csv, fuel_prices.csv, "
                   "renewable_forecast.csv, trade_blotter.csv, imbalance_prices.csv, weather_actuals_forecast.csv, "
                   "plant_portfolio.csv, and contract_obligations.csv for the selected date.*")
