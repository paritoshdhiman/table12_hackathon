#!/usr/bin/env python3
"""Trading Strategy Orchestrator — multi-agent system using Strands SDK.

Three sub-agents (Market, Dispatch, Risk) run on Sonnet for speed.
The orchestrator runs on Opus for synthesis and final recommendations.
"""

import os
import json
import concurrent.futures

import pandas as pd
import numpy as np
from strands import Agent
from strands.models.bedrock import BedrockModel
from strands.tools import tool

from domain import (
    compute_srmc, compute_srmc_at_load, part_load_efficiency,
    temp_corrected_efficiency, temp_corrected_capacity,
    clean_spark_spread, build_merit_order, get_start_cost,
    start_justified, get_start_type,
)
from dispatch import optimize_dispatch_for_date, summarize_dispatch
from compliance import (
    check_remit_compliance, check_contract_obligations,
    analyze_imbalance_exposure,
)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

SONNET = "us.anthropic.claude-sonnet-4-20250514-v1:0"
OPUS = "us.anthropic.claude-opus-4-6-v1"
REGION = os.environ.get("AWS_REGION", "us-east-1")

# ---------------------------------------------------------------------------
# Data loading (shared cache)
# ---------------------------------------------------------------------------
_cache = {}


def _load(name: str, subdir: str, **kwargs) -> pd.DataFrame:
    key = f"{subdir}/{name}"
    if key not in _cache:
        _cache[key] = pd.read_csv(os.path.join(DATA_DIR, subdir, name), **kwargs)
    return _cache[key]


def _intraday():
    return _load("intraday_prices_epex.csv", "market_prices", parse_dates=["timestamp_utc"])


def _day_ahead():
    return _load("day_ahead_prices.csv", "market_prices", parse_dates=["delivery_date"])


def _fuel():
    return _load("fuel_prices.csv", "market_prices", parse_dates=["date"])


def _renewable():
    return _load("renewable_forecast.csv", "market_prices", parse_dates=["timestamp_utc"])


def _imbalance():
    return _load("imbalance_prices.csv", "market_prices", parse_dates=["timestamp_utc"])


def _weather():
    return _load("weather_actuals_forecast.csv", "market_prices", parse_dates=["timestamp_utc"])


def _plants():
    return _load("plant_portfolio.csv", "plant_portfolio")


def _contracts():
    return _load("contract_obligations.csv", "plant_portfolio", parse_dates=["start_date", "end_date"])


def _trades():
    return _load("trade_blotter.csv", "market_prices", parse_dates=["timestamp_executed"])


def _remit():
    return _load("remit_transactions.csv", "market_prices")


def _mc_curves():
    return _load("marginal_cost_curves.csv", "plant_portfolio")


# ===================================================================
# SUB-AGENT 1: MARKET ANALYST
# ===================================================================

@tool
def market_get_intraday_prices(date: str, hour: int = -1) -> str:
    """Get intraday EPEX SPOT prices for a date (YYYY-MM-DD). Optionally filter by hour (0-23). Source: intraday_prices_epex.csv"""
    df = _intraday()
    day = df[df["timestamp_utc"].dt.date == pd.Timestamp(date).date()]
    if hour >= 0:
        day = day[day["timestamp_utc"].dt.hour == hour]
    if day.empty:
        return f"No intraday data for {date}"

    head = day.head(5).to_string(index=False)
    return (
        f"Intraday prices for {date} — {len(day)} periods (intraday_prices_epex.csv)\n"
        f"  Mean VWAP: EUR {day['vwap_eur_mwh'].mean():.2f}/MWh\n"
        f"  Range: EUR {day['vwap_eur_mwh'].min():.2f} to EUR {day['vwap_eur_mwh'].max():.2f}\n"
        f"  Total volume: {day['volume_mwh'].sum():,.1f} MWh\n"
        f"  Avg DA spread: EUR {day['spread_id_vs_da_eur_mwh'].mean():.2f}/MWh\n\n"
        f"First 5 rows:\n{head}"
    )


@tool
def market_get_day_ahead_prices(date: str) -> str:
    """Get day-ahead auction prices for a date. Source: day_ahead_prices.csv"""
    df = _day_ahead()
    day = df[df["delivery_date"].dt.date == pd.Timestamp(date).date()]
    if day.empty:
        return f"No day-ahead data for {date}"

    head = day.head(5).to_string(index=False)
    return (
        f"Day-ahead prices for {date} — {len(day)} hours (day_ahead_prices.csv)\n"
        f"  Mean: EUR {day['price_eur_mwh'].mean():.2f}/MWh\n"
        f"  Range: EUR {day['price_eur_mwh'].min():.2f} to EUR {day['price_eur_mwh'].max():.2f}\n"
        f"  Peak (8-20): EUR {day[(day['delivery_hour'] >= 8) & (day['delivery_hour'] < 20)]['price_eur_mwh'].mean():.2f}/MWh\n"
        f"  Off-peak: EUR {day[(day['delivery_hour'] < 8) | (day['delivery_hour'] >= 20)]['price_eur_mwh'].mean():.2f}/MWh\n\n"
        f"First 5 rows:\n{head}"
    )


@tool
def market_get_fuel_prices(date: str = "") -> str:
    """Get TTF gas, EU ETS carbon, coal, oil prices. No date = latest + 90-day summary. Source: fuel_prices.csv"""
    df = _fuel()
    if date:
        day = df[df["date"].dt.date == pd.Timestamp(date).date()]
        if day.empty:
            return f"No fuel data for {date}"
        r = day.iloc[0]
        return (
            f"Fuel prices for {date} (fuel_prices.csv):\n"
            f"  TTF front-month: EUR {r['ttf_front_month_eur_mwh']:.2f}/MWh\n"
            f"  TTF spot: EUR {r['ttf_spot_eur_mwh']:.2f}/MWh\n"
            f"  EU ETS: EUR {r['eu_ets_eur_tco2']:.2f}/tCO2\n"
            f"  Coal API2: USD {r['coal_api2_usd_t']:.2f}/t\n"
            f"  Brent: USD {r['brent_usd_bbl']:.2f}/bbl"
        )
    last = df.iloc[-1]
    head = df.head(5).to_string(index=False)
    return (
        f"Fuel prices — 90 days (fuel_prices.csv)\n"
        f"  Latest ({last['date'].date()}): TTF={last['ttf_front_month_eur_mwh']:.2f}, ETS={last['eu_ets_eur_tco2']:.2f}\n"
        f"  TTF avg: EUR {df['ttf_front_month_eur_mwh'].mean():.2f} (range {df['ttf_front_month_eur_mwh'].min():.2f}–{df['ttf_front_month_eur_mwh'].max():.2f})\n"
        f"  ETS avg: EUR {df['eu_ets_eur_tco2'].mean():.2f} (range {df['eu_ets_eur_tco2'].min():.2f}–{df['eu_ets_eur_tco2'].max():.2f})\n\n"
        f"First 5 rows:\n{head}"
    )


@tool
def market_get_renewable_forecast(date: str) -> str:
    """Get wind and solar forecasts with P10/P90 uncertainty bands. Source: renewable_forecast.csv"""
    df = _renewable()
    day = df[df["timestamp_utc"].dt.date == pd.Timestamp(date).date()]
    if day.empty:
        return f"No forecast data for {date}"

    head = day.head(5).to_string(index=False)
    return (
        f"Renewable forecast for {date} — {len(day)} periods (renewable_forecast.csv)\n"
        f"  Wind: avg {day['wind_forecast_mw'].mean():.0f} MW (P10={day['wind_p10_mw'].mean():.0f}, P90={day['wind_p90_mw'].mean():.0f})\n"
        f"  Solar: avg {day['solar_forecast_mw'].mean():.0f} MW (P10={day['solar_p10_mw'].mean():.0f}, P90={day['solar_p90_mw'].mean():.0f})\n"
        f"  Forecast error: mean {day['forecast_error_mw'].mean():.1f} MW, std {day['forecast_error_mw'].std():.1f} MW\n\n"
        f"First 5 rows:\n{head}"
    )


@tool
def market_get_weather(date: str, location: str = "") -> str:
    """Get weather data for plant locations. Locations: Karlsruhe_CCGT, Nordsee_Wind, Augsburg_Solar, Landshut_OCGT. Source: weather_actuals_forecast.csv"""
    df = _weather()
    day = df[df["timestamp_utc"].dt.date == pd.Timestamp(date).date()]
    if location:
        day = day[day["location"] == location]
    if day.empty:
        return f"No weather data for {date}"

    head = day.head(5).to_string(index=False)
    summary_lines = []
    for loc in day["location"].unique():
        loc_data = day[day["location"] == loc]
        summary_lines.append(
            f"  {loc}: temp={loc_data['temperature_c'].mean():.1f}C, "
            f"wind={loc_data['wind_speed_ms'].mean():.1f}m/s, "
            f"solar={loc_data['solar_irradiance_wm2'].mean():.0f}W/m2"
        )

    return (
        f"Weather for {date} (weather_actuals_forecast.csv)\n"
        + "\n".join(summary_lines)
        + f"\n\nFirst 5 rows:\n{head}"
    )


MARKET_AGENT_PROMPT = """You are a Market Analyst for the DE-LU intraday electricity market.
Your job: analyze price patterns, spreads, renewable forecasts, weather, and fuel costs.
Always cite the source file and show numbers from the data. Be concise — traders need fast answers."""


def _create_market_agent() -> Agent:
    return Agent(
        model=BedrockModel(model_id=SONNET, region_name=REGION),
        tools=[
            market_get_intraday_prices,
            market_get_day_ahead_prices,
            market_get_fuel_prices,
            market_get_renewable_forecast,
            market_get_weather,
        ],
        system_prompt=MARKET_AGENT_PROMPT,
    )


# ===================================================================
# SUB-AGENT 2: DISPATCH OPTIMIZER
# ===================================================================

@tool
def dispatch_get_plant_info(plant_id: str = "") -> str:
    """Get plant specs. Leave empty for all 4 plants. Source: plant_portfolio.csv"""
    df = _plants()
    if plant_id:
        df = df[df["plant_id"] == plant_id]
    if df.empty:
        return f"Plant '{plant_id}' not found."

    head = df.head(5).to_string(index=False)
    lines = []
    for _, p in df.iterrows():
        lines.append(
            f"{p['plant_id']} ({p['technology']}): {p['capacity_mw']}MW, "
            f"eff={p['efficiency_pct']}%, ramp={p['max_ramp_up_mw_min']}MW/min, "
            f"min_stable={p['min_stable_load_mw']}MW, "
            f"start_hot=EUR{p['start_cost_hot_eur']:,.0f}"
        )
    return (
        f"Plant portfolio (plant_portfolio.csv):\n"
        + "\n".join(lines)
        + f"\n\nFull data:\n{head}"
    )


@tool
def dispatch_compute_marginal_cost(plant_id: str, load_mw: float,
                                   gas_price: float = 0, co2_price: float = 0,
                                   temperature_c: float = 15.0) -> str:
    """Compute SRMC for RHEIN_CCGT or ISAR_OCGT at a given load and temperature.
    If gas/co2 = 0, uses latest from fuel_prices.csv. Source: plant_portfolio.csv, fuel_prices.csv"""
    plants = _plants()
    p = plants[plants["plant_id"] == plant_id]
    if p.empty:
        return f"Unknown plant: {plant_id}"
    p = p.iloc[0]

    if gas_price == 0 or co2_price == 0:
        fuel = _fuel()
        last = fuel.iloc[-1]
        if gas_price == 0:
            gas_price = last["ttf_front_month_eur_mwh"]
        if co2_price == 0:
            co2_price = last["eu_ets_eur_tco2"]

    srmc = compute_srmc_at_load(plant_id, load_mw, gas_price, co2_price, plants, temperature_c)
    eta = part_load_efficiency(p["efficiency_pct"] / 100, load_mw, p["capacity_mw"])
    eta = temp_corrected_efficiency(eta, temperature_c)

    return (
        f"SRMC for {plant_id} at {load_mw}MW, {temperature_c}C:\n"
        f"  Efficiency: {eta*100:.1f}%\n"
        f"  Gas component: EUR {gas_price/eta:.2f}/MWh\n"
        f"  CO2 component: EUR {co2_price * p['co2_intensity_tco2_mwh']:.2f}/MWh\n"
        f"  VOM: EUR {p['variable_om_eur_mwh']:.2f}/MWh\n"
        f"  SRMC = EUR {srmc:.2f}/MWh\n"
        f"  Inputs: gas={gas_price:.2f} (fuel_prices.csv), co2={co2_price:.2f} (fuel_prices.csv)"
    )


@tool
def dispatch_get_merit_order(date: str = "") -> str:
    """Build the merit order for thermal plants at current fuel prices. Source: plant_portfolio.csv, fuel_prices.csv"""
    fuel = _fuel()
    if date:
        day = fuel[fuel["date"].dt.date == pd.Timestamp(date).date()]
        if not day.empty:
            fuel_row = day.iloc[0]
        else:
            fuel_row = fuel.iloc[-1]
    else:
        fuel_row = fuel.iloc[-1]

    gas = fuel_row["ttf_front_month_eur_mwh"]
    co2 = fuel_row["eu_ets_eur_tco2"]

    order = build_merit_order(gas, co2, _plants())
    lines = [f"Merit order (gas=EUR{gas:.2f}, co2=EUR{co2:.2f}):"]
    for i, entry in enumerate(order, 1):
        lines.append(
            f"  {i}. {entry['plant_id']} — SRMC: EUR {entry['srmc_eur_mwh']:.2f}/MWh, "
            f"capacity: {entry['capacity_mw']}MW (min {entry['min_stable_load_mw']}MW)"
        )
    return "\n".join(lines)


@tool
def dispatch_run_optimization(date: str) -> str:
    """Run full dispatch optimization for a date. Returns generation schedule, revenue, costs, margins per plant. Source: all market + plant data"""
    intraday = _intraday()
    intraday["date"] = intraday["timestamp_utc"].dt.date
    fuel = _fuel()
    fuel["date"] = pd.to_datetime(fuel["date"])
    renewable = _renewable()
    weather = _weather()
    plants = _plants()
    contracts = _contracts()

    result = optimize_dispatch_for_date(
        date, intraday, fuel, renewable, weather, plants, contracts
    )
    if result.empty:
        return f"No data available for dispatch on {date}"

    summary = summarize_dispatch(result)
    by_plant = summary["by_plant"]

    head = result.head(5).to_string(index=False)
    lines = [
        f"Dispatch optimization for {date}:",
        f"  Total generation: {summary['total_generation_mwh']:,.1f} MWh",
        f"  Total revenue: EUR {summary['total_revenue']:,.2f}",
        f"  Total cost: EUR {summary['total_cost']:,.2f}",
        f"  Total margin: EUR {summary['total_margin']:,.2f}",
        f"  Avg clean spark spread: EUR {summary['avg_css']:.2f}/MWh\n",
        "  By plant:",
    ]
    for plant_id, row in by_plant.iterrows():
        lines.append(
            f"    {plant_id}: gen={row['total_gen_mwh']:,.0f}MWh, "
            f"revenue=EUR{row['total_revenue']:,.0f}, margin=EUR{row['total_margin']:,.0f}, "
            f"avg_dispatch={row['avg_dispatch_mw']:.0f}MW"
        )
    lines.append(f"\nFirst 5 rows:\n{head}")
    return "\n".join(lines)


@tool
def dispatch_evaluate_startup(plant_id: str, hours_offline: float,
                              expected_price: float, run_hours: float,
                              gas_price: float = 0, co2_price: float = 0) -> str:
    """Evaluate whether starting a plant is economically justified.
    Source: plant_portfolio.csv, fuel_prices.csv"""
    plants = _plants()
    p = plants[plants["plant_id"] == plant_id]
    if p.empty:
        return f"Unknown plant: {plant_id}"
    p = p.iloc[0]

    if gas_price == 0 or co2_price == 0:
        fuel = _fuel()
        last = fuel.iloc[-1]
        if gas_price == 0:
            gas_price = last["ttf_front_month_eur_mwh"]
        if co2_price == 0:
            co2_price = last["eu_ets_eur_tco2"]

    start_type = get_start_type(hours_offline)
    s_cost = get_start_cost(p, hours_offline)
    srmc = compute_srmc_at_load(plant_id, p["capacity_mw"], gas_price, co2_price, plants)
    margin = expected_price - srmc
    justified = start_justified(margin, run_hours, s_cost, p["min_run_time_hrs"], p["variable_om_eur_mwh"])

    return (
        f"Start-up evaluation for {plant_id}:\n"
        f"  Offline: {hours_offline}h → {start_type} start\n"
        f"  Start cost: EUR {s_cost:,.0f}\n"
        f"  SRMC at full load: EUR {srmc:.2f}/MWh\n"
        f"  Expected margin: EUR {margin:.2f}/MWh × {run_hours}h = EUR {margin * run_hours:,.0f}\n"
        f"  Min run time: {p['min_run_time_hrs']}h\n"
        f"  JUSTIFIED: {'YES' if justified else 'NO'}\n"
        f"  Formula: margin×hours ({margin:.2f}×{run_hours}={margin*run_hours:.0f}) "
        f"{'>' if justified else '<='} start_cost + min_run×VOM ({s_cost:.0f}+{p['min_run_time_hrs']}×{p['variable_om_eur_mwh']}={s_cost + p['min_run_time_hrs'] * p['variable_om_eur_mwh']:.0f})"
    )


DISPATCH_AGENT_PROMPT = """You are a Dispatch Optimizer for a 4-plant German power portfolio.
Your job: determine optimal generation schedules, evaluate start-up decisions, and compute marginal costs.
Always show the formula, inputs, and source data. Consider ramp constraints and minimum stable load."""


def _create_dispatch_agent() -> Agent:
    return Agent(
        model=BedrockModel(model_id=SONNET, region_name=REGION),
        tools=[
            dispatch_get_plant_info,
            dispatch_compute_marginal_cost,
            dispatch_get_merit_order,
            dispatch_run_optimization,
            dispatch_evaluate_startup,
        ],
        system_prompt=DISPATCH_AGENT_PROMPT,
    )


# ===================================================================
# SUB-AGENT 3: RISK & COMPLIANCE
# ===================================================================

@tool
def risk_check_remit(trade_id: str = "", status_filter: str = "") -> str:
    """Check REMIT II compliance status. Filter by trade_id or status (ACCEPTED/REJECTED/PENDING). Source: remit_transactions.csv, trade_blotter.csv"""
    trades = _trades()
    remit = _remit()

    if trade_id:
        r = remit[remit["trade_id"] == trade_id]
        if r.empty:
            return f"NO REMIT RECORD for {trade_id} — potentially unreported trade!"
        row = r.iloc[0]
        return (
            f"REMIT: {trade_id} — status={row['status']}, "
            f"submitted={row['submission_timestamp']}, deadline={row['reporting_deadline']}"
        )

    result = check_remit_compliance(trades, remit)
    head = remit.head(5).to_string(index=False)
    return (
        f"REMIT Compliance Overview (remit_transactions.csv):\n"
        f"  Total trades: {result['total_trades']}\n"
        f"  REMIT reports: {result['total_remit_reports']}\n"
        f"  Missing reports: {result['missing_count']}\n"
        f"  Status: {result['status_counts']}\n"
        f"  Compliance rate: {result['compliance_rate']:.1f}%\n"
        f"  Rejected: {len(result['rejected_reports'])}\n"
        f"  Pending: {len(result['pending_reports'])}\n"
        f"  Overdue: {len(result['overdue_reports'])}\n\n"
        f"First 5 rows:\n{head}"
    )


@tool
def risk_check_contracts(date_start: str = "", date_end: str = "") -> str:
    """Check delivery vs contracted obligations. Source: contract_obligations.csv, trade_blotter.csv"""
    contracts = _contracts()
    trades = _trades()

    date_range = None
    if date_start and date_end:
        date_range = (pd.Timestamp(date_start).date(), pd.Timestamp(date_end).date())

    result = check_contract_obligations(contracts, trades, date_range)
    head = result.head(5).to_string(index=False)

    total_penalty = result["penalty_exposure_eur"].sum()
    breaches = result[~result["within_tolerance"]]

    return (
        f"Contract Obligations ({len(result)} contracts, contract_obligations.csv):\n"
        f"  Breaches: {len(breaches)} of {len(result)}\n"
        f"  Total penalty exposure: EUR {total_penalty:,.0f}\n\n"
        f"Details:\n{head}"
    )


@tool
def risk_check_imbalance(date: str = "") -> str:
    """Analyze imbalance exposure and settlement risk. Source: imbalance_prices.csv"""
    df = _imbalance()
    if date:
        df = df[df["timestamp_utc"].dt.date == pd.Timestamp(date).date()]
    if df.empty:
        return f"No imbalance data for {date}"

    result = analyze_imbalance_exposure(df)
    head = df.head(5).to_string(index=False)

    worst = result["worst_events"]
    worst_lines = []
    for _, w in worst.head(3).iterrows():
        worst_lines.append(
            f"    {w['timestamp_utc']}: spread=EUR{w['spread']:.2f}, "
            f"balance={w['system_balance_mw']:.0f}MW ({w['regulation_state']})"
        )

    return (
        f"Imbalance Analysis (imbalance_prices.csv):\n"
        f"  Regulation states: {result['state_counts']}\n"
        f"  Avg long price: EUR {result['avg_long_price']:.2f}/MWh\n"
        f"  Avg short price: EUR {result['avg_short_price']:.2f}/MWh\n"
        f"  Avg spread: EUR {result['avg_spread']:.2f}/MWh\n"
        f"  Max spread: EUR {result['max_spread']:.2f}/MWh\n"
        f"  Worst events:\n" + "\n".join(worst_lines) +
        f"\n\nFirst 5 rows:\n{head}"
    )


@tool
def risk_get_portfolio_position(date: str) -> str:
    """Get net portfolio position for a date: contracts + existing trades + renewable forecast. Source: contract_obligations.csv, trade_blotter.csv, renewable_forecast.csv"""
    contracts = _contracts()
    trades = _trades()
    renewable = _renewable()

    d = pd.Timestamp(date).date()

    contract_mw = 0.0
    for _, c in contracts.iterrows():
        if c["start_date"].date() <= d <= c["end_date"].date():
            contract_mw += c["volume_mw"]

    day_trades = trades[trades["timestamp_executed"].dt.date == d]
    sell_mw = day_trades[day_trades["direction"] == "SELL"]["volume_mw"].sum()
    buy_mw = day_trades[day_trades["direction"] == "BUY"]["volume_mw"].sum()
    trade_pnl = day_trades["pnl_eur"].sum()

    day_renew = renewable[renewable["timestamp_utc"].dt.date == d]
    wind_avg = day_renew["wind_forecast_mw"].mean() if not day_renew.empty else 0
    solar_avg = day_renew["solar_forecast_mw"].mean() if not day_renew.empty else 0

    return (
        f"Portfolio position for {date}:\n"
        f"  Contract commitments: {contract_mw:.0f} MW (contract_obligations.csv)\n"
        f"  Day's trades: {len(day_trades)} (SELL: {sell_mw:.0f}MW, BUY: {buy_mw:.0f}MW)\n"
        f"  Day's trade P&L: EUR {trade_pnl:,.2f} (trade_blotter.csv)\n"
        f"  Renewable forecast: wind={wind_avg:.0f}MW, solar={solar_avg:.0f}MW (renewable_forecast.csv)\n"
        f"  Net generation capacity: {contract_mw + wind_avg + solar_avg:.0f} MW (committed + renewables)"
    )


@tool
def risk_get_trade_blotter(date: str = "", plant_id: str = "",
                           strategy: str = "", limit: int = 10) -> str:
    """Query trade blotter. Filter by date, plant, strategy (DA_HEDGE/ID_OPTIM/BALANCING/SPREAD). Source: trade_blotter.csv"""
    df = _trades()
    if date:
        df = df[df["timestamp_executed"].dt.date == pd.Timestamp(date).date()]
    if plant_id:
        df = df[df["plant_id"] == plant_id]
    if strategy:
        df = df[df["strategy"] == strategy]

    total_pnl = df["pnl_eur"].sum()
    head = df.head(5).to_string(index=False)

    return (
        f"Trade blotter: {len(df)} trades, total P&L: EUR {total_pnl:,.2f} (trade_blotter.csv)\n"
        f"  By strategy: {df['strategy'].value_counts().to_dict()}\n"
        f"  By direction: {df['direction'].value_counts().to_dict()}\n\n"
        f"First 5 rows:\n{head}"
    )


RISK_AGENT_PROMPT = """You are a Risk & Compliance Officer for a German power utility.
Your job: monitor REMIT compliance, contract obligations, imbalance exposure, and trading risk.
Flag violations, quantify penalty exposure in EUR, and cite specific data sources.
Prioritize issues by financial impact."""


def _create_risk_agent() -> Agent:
    return Agent(
        model=BedrockModel(model_id=SONNET, region_name=REGION),
        tools=[
            risk_check_remit,
            risk_check_contracts,
            risk_check_imbalance,
            risk_get_portfolio_position,
            risk_get_trade_blotter,
        ],
        system_prompt=RISK_AGENT_PROMPT,
    )


# ===================================================================
# ORCHESTRATOR — delegates to sub-agents, synthesizes recommendations
# ===================================================================

@tool
def ask_market_analyst(question: str) -> str:
    """Ask the Market Analyst sub-agent about prices, spreads, forecasts, weather, or fuel costs. It has access to: intraday_prices_epex.csv, day_ahead_prices.csv, fuel_prices.csv, renewable_forecast.csv, weather_actuals_forecast.csv."""
    agent = _create_market_agent()
    result = agent(question)
    return str(result)


@tool
def ask_dispatch_optimizer(question: str) -> str:
    """Ask the Dispatch Optimizer sub-agent about plant operations, marginal costs, merit order, generation schedules, or start-up decisions. It has access to: plant_portfolio.csv, fuel_prices.csv, and runs the dispatch optimization engine."""
    agent = _create_dispatch_agent()
    result = agent(question)
    return str(result)


@tool
def ask_risk_officer(question: str) -> str:
    """Ask the Risk & Compliance sub-agent about REMIT status, contract obligations, imbalance exposure, portfolio positions, or trade history. It has access to: remit_transactions.csv, contract_obligations.csv, imbalance_prices.csv, trade_blotter.csv."""
    agent = _create_risk_agent()
    result = agent(question)
    return str(result)


@tool
def search_reference_docs(query: str) -> str:
    """Search the 4 reference documents: EPEX SPOT market rules, CCGT operating manual, REMIT II compliance guide, German balancing framework. Source: data/reference_docs/"""
    docs = {
        "epex_spot_market_rules.md": "EPEX SPOT market rules",
        "ccgt_plant_operating_manual.md": "CCGT operating manual",
        "remit_compliance_guide.md": "REMIT II compliance",
        "balancing_imbalance_settlement.md": "German balancing framework",
    }

    query_lower = query.lower()
    results = []
    for filename, label in docs.items():
        path = os.path.join(DATA_DIR, "reference_docs", filename)
        if not os.path.exists(path):
            continue
        with open(path) as f:
            content = f.read()

        if query_lower in content.lower():
            idx = content.lower().index(query_lower)
            start = max(0, idx - 100)
            end = min(len(content), idx + 500)
            results.append(f"[{label} — {filename}]:\n  ...{content[start:end]}...")

    if results:
        return f"Found {len(results)} passage(s):\n\n" + "\n\n".join(results)
    return f"No passages found matching '{query}'."


ORCHESTRATOR_PROMPT = """You are the Head Trader / Chief Strategist for a German power utility's intraday trading desk.

You have 3 specialist sub-agents and a reference doc search tool:
1. **Market Analyst** — prices, spreads, forecasts, weather, fuel costs
2. **Dispatch Optimizer** — plant operations, marginal costs, generation schedules, start-up decisions
3. **Risk & Compliance Officer** — REMIT, contracts, imbalance exposure, portfolio positions

WORKFLOW:
- For complex questions, delegate to the relevant sub-agents.
- For trading decisions, consult ALL THREE agents to get a complete picture.
- Synthesize their responses into a clear, actionable recommendation.

OUTPUT FORMAT for trading recommendations:
1. **Market Context** — current prices, spreads, forecasts
2. **Dispatch Recommendation** — which plants to run, at what load
3. **Risk Assessment** — compliance status, contract coverage, imbalance exposure
4. **Trade Actions** — specific BUY/SELL recommendations with volume, target price, timing
5. **Data Sources** — cite specific CSV files and row numbers

RULES:
- Every number must trace to a data source.
- If sub-agents disagree, explain the conflict and your resolution.
- Quantify financial impact of recommendations in EUR.
- Flag any compliance risks before recommending trades.
- Be decisive — traders need clear recommendations, not options lists."""


def create_orchestrator() -> Agent:
    return Agent(
        model=BedrockModel(model_id=OPUS, region_name=REGION),
        tools=[
            ask_market_analyst,
            ask_dispatch_optimizer,
            ask_risk_officer,
            search_reference_docs,
        ],
        system_prompt=ORCHESTRATOR_PROMPT,
    )


# ===================================================================
# CLI
# ===================================================================

def main():
    print("=" * 64)
    print("  Trading Strategy Orchestrator")
    print("  Opus orchestrator + 3 Sonnet sub-agents")
    print("  Type 'quit' to exit")
    print("=" * 64)

    orchestrator = create_orchestrator()

    while True:
        try:
            question = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not question:
            continue
        if question.lower() in ("quit", "exit", "q"):
            print("Goodbye!")
            break

        try:
            print(f"\n  [Orchestrator processing...]\n")
            result = orchestrator(question)
            print(f"\nChief Strategist:\n{result}\n")
        except Exception as e:
            print(f"\nError: {e}\n")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
