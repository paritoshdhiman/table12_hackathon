#!/usr/bin/env python3
"""Trading Strategy Orchestrator — enhanced multi-agent system.

Builds on multi_agent.py's shared tools and specialist agents, adding:
- Sonnet sub-agents for speed (Opus only for orchestrator synthesis)
- Dispatch optimization engine (merit order, full-day dispatch, start-up eval)
- Portfolio position tracking
- Contract compliance checking with penalty quantification

Can be used standalone (CLI) or imported alongside multi_agent.py.
"""

import os

import pandas as pd
from strands import Agent
from strands.models.bedrock import BedrockModel
from strands.tools import tool

from domain import (
    compute_srmc_at_load, part_load_efficiency,
    temp_corrected_efficiency, clean_spark_spread,
    build_merit_order, get_start_cost, start_justified, get_start_type,
)
from dispatch import optimize_dispatch_for_date, summarize_dispatch
from compliance import (
    check_remit_compliance, check_contract_obligations,
    analyze_imbalance_exposure,
)

# Reuse the shared data cache from multi_agent
from multi_agent import (
    _load, _intraday, _fuel, _plants, _contracts, _trades, _remit,
    _renewable, _imbalance,
    # Reuse shared data-query tools
    query_intraday_prices as _shared_query_intraday_prices,
    query_fuel_prices as _shared_query_fuel_prices,
    query_renewable_forecast as _shared_query_renewable_forecast,
    query_plant_info as _shared_query_plant_info,
    compute_marginal_cost as _shared_compute_marginal_cost,
    query_remit_status as _shared_query_remit_status,
    query_contract_obligations as _shared_query_contract_obligations,
    query_imbalance_data as _shared_query_imbalance_data,
    query_trade_blotter as _shared_query_trade_blotter,
    search_reference_docs as _shared_search_reference_docs,
)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

SONNET = "us.anthropic.claude-sonnet-4-20250514-v1:0"
OPUS = "us.anthropic.claude-opus-4-6-v1"
REGION = os.environ.get("AWS_REGION", "us-east-1")


# ===================================================================
# ENHANCED TOOLS — capabilities not in multi_agent.py
# ===================================================================

@tool
def run_merit_order(date: str = "") -> str:
    """Build the merit order for thermal plants at current or date-specific fuel prices. Source: plant_portfolio.csv, fuel_prices.csv"""
    fuel = _fuel()
    if date:
        day = fuel[fuel["date"].dt.date == pd.Timestamp(date).date()]
        fuel_row = day.iloc[0] if not day.empty else fuel.iloc[-1]
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
def run_dispatch_optimization(date: str) -> str:
    """Run full-day dispatch optimization for all 96 quarter-hours. Returns generation, revenue, costs, margins per plant. Source: all market + plant data"""
    intraday = _intraday().copy()
    intraday["date"] = intraday["timestamp_utc"].dt.date
    fuel = _fuel().copy()
    fuel["date"] = pd.to_datetime(fuel["date"])

    result = optimize_dispatch_for_date(
        date, intraday, fuel, _renewable(), _load("weather_actuals_forecast.csv", "market_prices", parse_dates=["timestamp_utc"]),
        _plants(), _contracts(),
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
def evaluate_plant_startup(plant_id: str, hours_offline: float,
                           expected_price: float, run_hours: float,
                           gas_price: float = 0, co2_price: float = 0) -> str:
    """Evaluate whether starting a plant is economically justified. Source: plant_portfolio.csv, fuel_prices.csv"""
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
        f"{'>' if justified else '<='} start_cost+min_run×VOM "
        f"({s_cost:.0f}+{p['min_run_time_hrs']}×{p['variable_om_eur_mwh']}="
        f"{s_cost + p['min_run_time_hrs'] * p['variable_om_eur_mwh']:.0f})"
    )


@tool
def get_portfolio_position(date: str) -> str:
    """Get net portfolio position: contracts + existing trades + renewable forecast. Source: contract_obligations.csv, trade_blotter.csv, renewable_forecast.csv"""
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
def check_contract_compliance(date_start: str = "", date_end: str = "") -> str:
    """Check delivery vs contracted obligations with penalty exposure. Source: contract_obligations.csv, trade_blotter.csv"""
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
def check_imbalance_exposure(date: str = "") -> str:
    """Analyze imbalance exposure with worst events. Source: imbalance_prices.csv"""
    df = _imbalance()
    if date:
        df = df[df["timestamp_utc"].dt.date == pd.Timestamp(date).date()]
    if df.empty:
        return f"No imbalance data for {date}"

    result = analyze_imbalance_exposure(df)

    worst_lines = []
    for _, w in result["worst_events"].head(3).iterrows():
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
        f"  Worst events:\n" + "\n".join(worst_lines)
    )


# ===================================================================
# SUB-AGENTS (Sonnet for speed)
# ===================================================================

_sonnet_model = None
_opus_model = None


def _get_sonnet():
    global _sonnet_model
    if _sonnet_model is None:
        _sonnet_model = BedrockModel(model_id=SONNET, region_name=REGION)
    return _sonnet_model


def _get_opus():
    global _opus_model
    if _opus_model is None:
        _opus_model = BedrockModel(model_id=OPUS, region_name=REGION)
    return _opus_model


MARKET_PROMPT = """You are a Market Analyst for the DE-LU intraday electricity market.
Your job: analyze price patterns, spreads, renewable forecasts, weather, and fuel costs.
Always cite the source file and show numbers from the data. Be concise — traders need fast answers."""

DISPATCH_PROMPT = """You are a Dispatch Optimizer for a 4-plant German power portfolio.
Plants: RHEIN_CCGT (430MW), NORDSEE_WIND (350MW), BAYERN_SOLAR (120MW), ISAR_OCGT (180MW).
Your job: determine optimal generation, evaluate start-up decisions, compute marginal costs.
Always show formulas, inputs, and source data. Consider ramp constraints and minimum stable load."""

RISK_PROMPT = """You are a Risk & Compliance Officer for a German power utility.
Your job: monitor REMIT compliance, contract obligations, imbalance exposure, and trading risk.
Flag violations, quantify penalty exposure in EUR, and cite specific data sources.
Prioritize issues by financial impact."""

_specialists = {}


def _get_specialist(name: str) -> Agent:
    if name not in _specialists:
        configs = {
            "market": {
                "tools": [
                    _shared_query_intraday_prices,
                    _shared_query_fuel_prices,
                    _shared_query_renewable_forecast,
                    _shared_search_reference_docs,
                ],
                "prompt": MARKET_PROMPT,
            },
            "dispatch": {
                "tools": [
                    _shared_query_plant_info,
                    _shared_compute_marginal_cost,
                    _shared_query_fuel_prices,
                    _shared_query_contract_obligations,
                    _shared_search_reference_docs,
                    run_merit_order,
                    run_dispatch_optimization,
                    evaluate_plant_startup,
                ],
                "prompt": DISPATCH_PROMPT,
            },
            "risk": {
                "tools": [
                    _shared_query_remit_status,
                    _shared_query_contract_obligations,
                    _shared_query_trade_blotter,
                    _shared_query_imbalance_data,
                    get_portfolio_position,
                    check_contract_compliance,
                    check_imbalance_exposure,
                ],
                "prompt": RISK_PROMPT,
            },
        }
        cfg = configs[name]
        _specialists[name] = Agent(
            model=BedrockModel(model_id=SONNET, region_name=REGION),
            tools=cfg["tools"],
            system_prompt=cfg["prompt"],
        )
    return _specialists[name]


def _call_specialist(name: str, query: str) -> str:
    agent = _get_specialist(name)
    result = agent(query)
    content_blocks = result.message.get("content", [])
    text = ""
    for block in content_blocks:
        if isinstance(block, dict) and "text" in block:
            text += block["text"]
    return text if text else str(result.message)


# ===================================================================
# ORCHESTRATOR TOOLS — delegate to sub-agents
# ===================================================================

@tool
def consult_market_analyst(question: str) -> str:
    """Ask the Market Analyst (Sonnet) about prices, spreads, forecasts, weather, or fuel costs. Has access to: intraday_prices_epex.csv, fuel_prices.csv, renewable_forecast.csv, reference docs."""
    return f"[Market Analyst]:\n{_call_specialist('market', question)}"


@tool
def consult_dispatch_optimizer(question: str) -> str:
    """Ask the Dispatch Optimizer (Sonnet) about plant operations, marginal costs, merit order, generation schedules, start-up decisions, or full-day optimization. Has access to: plant_portfolio.csv, fuel_prices.csv, dispatch engine, merit order builder."""
    return f"[Dispatch Optimizer]:\n{_call_specialist('dispatch', question)}"


@tool
def consult_risk_officer(question: str) -> str:
    """Ask the Risk & Compliance Officer (Sonnet) about REMIT status, contract obligations, imbalance exposure, portfolio positions, or trade history. Has access to: remit_transactions.csv, contract_obligations.csv, imbalance_prices.csv, trade_blotter.csv, compliance engine."""
    return f"[Risk & Compliance]:\n{_call_specialist('risk', question)}"


ORCHESTRATOR_PROMPT = """You are the Head Trader / Chief Strategist for a German power utility's intraday trading desk.

You have 3 specialist sub-agents and a reference doc search tool:
1. **Market Analyst** (Sonnet) — prices, spreads, forecasts, weather, fuel costs
2. **Dispatch Optimizer** (Sonnet) — plant operations, marginal costs, merit order, generation schedules, start-up decisions, full-day dispatch optimization
3. **Risk & Compliance Officer** (Sonnet) — REMIT, contracts, imbalance exposure, portfolio positions, penalty quantification

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
    """Create the enhanced orchestrator agent.

    Compatible with multi_agent.py — reuses its shared data cache and tools,
    adds dispatch optimization, merit order, start-up evaluation, and
    portfolio position tracking. Uses Sonnet for sub-agents (faster) and
    Opus for orchestration (better synthesis).
    """
    return Agent(
        model=BedrockModel(model_id=OPUS, region_name=REGION),
        tools=[
            consult_market_analyst,
            consult_dispatch_optimizer,
            consult_risk_officer,
            _shared_search_reference_docs,
        ],
        system_prompt=ORCHESTRATOR_PROMPT,
    )


# ===================================================================
# CLI
# ===================================================================

def main():
    print("=" * 64)
    print("  Trading Strategy Orchestrator (Enhanced)")
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
            content_blocks = result.message.get("content", [])
            text = ""
            for block in content_blocks:
                if isinstance(block, dict) and "text" in block:
                    text += block["text"]
            if not text:
                text = str(result.message)
            print(f"\nChief Strategist:\n{text}\n")
        except Exception as e:
            print(f"\nError: {e}\n")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
