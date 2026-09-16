"""AgentCore Runtime entrypoint for the Trading Chat Agent (multi-agent orchestrator).

Wraps the Strands-based multi-agent system — 1 orchestrator + 4 specialist agents —
with BedrockAgentCoreApp so it can be deployed to Amazon Bedrock AgentCore.
"""

import os
from collections import OrderedDict

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent
from strands.agent.conversation_manager.null_conversation_manager import NullConversationManager
from strands.models.bedrock import BedrockModel
from strands.tools import tool

import pandas as pd

# ---------------------------------------------------------------------------
# Data layer
# ---------------------------------------------------------------------------

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

_cache = {}


def _load(name: str, subdir: str, **kwargs) -> pd.DataFrame:
    key = f"{subdir}/{name}"
    if key not in _cache:
        _cache[key] = pd.read_csv(os.path.join(DATA_DIR, subdir, name), **kwargs)
    return _cache[key]


def _trades():
    return _load("trade_blotter.csv", "market_prices", parse_dates=["timestamp_executed"])

def _intraday():
    return _load("intraday_prices_epex.csv", "market_prices", parse_dates=["timestamp_utc"])

def _plants():
    return _load("plant_portfolio.csv", "plant_portfolio")

def _fuel():
    return _load("fuel_prices.csv", "market_prices", parse_dates=["date"])

def _contracts():
    return _load("contract_obligations.csv", "plant_portfolio", parse_dates=["start_date", "end_date"])

def _remit():
    return _load("remit_transactions.csv", "market_prices")

def _renewable():
    return _load("renewable_forecast.csv", "market_prices", parse_dates=["timestamp_utc"])

def _imbalance():
    return _load("imbalance_prices.csv", "market_prices", parse_dates=["timestamp_utc"])


# ---------------------------------------------------------------------------
# Data-query tools (shared across specialists)
# ---------------------------------------------------------------------------

@tool
def query_trade_blotter(date: str = "", plant_id: str = "", strategy: str = "",
                        direction: str = "", min_pnl: float = -999999,
                        max_pnl: float = 999999, limit: int = 20) -> str:
    """Query the trade blotter (2,689 trades). Filter by date, plant_id, strategy, direction, or P&L range. Source: trade_blotter.csv"""
    df = _trades()
    if date:
        df = df[df["timestamp_executed"].dt.date == pd.Timestamp(date).date()]
    if plant_id:
        df = df[df["plant_id"] == plant_id]
    if strategy:
        df = df[df["strategy"] == strategy]
    if direction:
        df = df[df["direction"] == direction]
    df = df[(df["pnl_eur"] >= min_pnl) & (df["pnl_eur"] <= max_pnl)]
    total = len(df)
    total_pnl = df["pnl_eur"].sum()
    top = df.nlargest(limit, "pnl_eur") if total > 0 else df
    lines = [f"Found {total} trades, total P&L: EUR {total_pnl:,.2f} (trade_blotter.csv)"]
    for idx, row in top.iterrows():
        lines.append(
            f"  Row {idx+2}: {row['trade_id']} | {row['direction']} {row['volume_mw']}MW "
            f"@ EUR {row['price_eur_mwh']:.2f} | P&L: EUR {row['pnl_eur']:,.2f} | "
            f"Strategy: {row['strategy']} | Plant: {row.get('plant_id', 'N/A')}"
        )
    return "\n".join(lines)


@tool
def query_intraday_prices(date: str, hour: int = -1) -> str:
    """Query intraday EPEX SPOT prices for a date, optionally by hour. Source: intraday_prices_epex.csv"""
    df = _intraday()
    df_day = df[df["timestamp_utc"].dt.date == pd.Timestamp(date).date()]
    if hour >= 0:
        df_day = df_day[df_day["timestamp_utc"].dt.hour == hour]
    if df_day.empty:
        return f"No data for {date} (hour={hour})"
    lines = [f"Intraday prices for {date} — {len(df_day)} periods (intraday_prices_epex.csv)"]
    lines.append(f"  Mean VWAP: EUR {df_day['vwap_eur_mwh'].mean():.2f}/MWh")
    lines.append(f"  Min: EUR {df_day['vwap_eur_mwh'].min():.2f} | Max: EUR {df_day['vwap_eur_mwh'].max():.2f}")
    lines.append(f"  Volume: {df_day['volume_mwh'].sum():,.1f} MWh | Trades: {df_day['num_trades'].sum()}")
    top = df_day.nlargest(5, "vwap_eur_mwh")
    lines.append("  Top 5 highest:")
    for idx, row in top.iterrows():
        lines.append(f"    Row {idx+2}: {row['delivery_start']} VWAP={row['vwap_eur_mwh']:.2f}")
    return "\n".join(lines)


@tool
def query_fuel_prices(date: str = "") -> str:
    """Get gas (TTF), carbon (EU ETS), coal, oil prices. Source: fuel_prices.csv"""
    df = _fuel()
    if date:
        day = df[df["date"].dt.date == pd.Timestamp(date).date()]
        if day.empty:
            return f"No fuel data for {date}"
        r = day.iloc[0]
        return (
            f"Fuel prices for {date} (fuel_prices.csv, row {day.index[0]+2}):\n"
            f"  TTF front-month: EUR {r['ttf_front_month_eur_mwh']:.2f}/MWh\n"
            f"  TTF spot: EUR {r['ttf_spot_eur_mwh']:.2f}/MWh\n"
            f"  EU ETS: EUR {r['eu_ets_eur_tco2']:.2f}/tCO2\n"
            f"  Coal API2: USD {r['coal_api2_usd_t']:.2f}/t | Brent: USD {r['brent_usd_bbl']:.2f}/bbl"
        )
    last = df.iloc[-1]
    return (
        f"Fuel summary (fuel_prices.csv, {len(df)} days):\n"
        f"  Latest ({last['date'].date()}): TTF EUR {last['ttf_front_month_eur_mwh']:.2f}, ETS EUR {last['eu_ets_eur_tco2']:.2f}\n"
        f"  90d avg: TTF EUR {df['ttf_front_month_eur_mwh'].mean():.2f}, ETS EUR {df['eu_ets_eur_tco2'].mean():.2f}"
    )


@tool
def query_renewable_forecast(date: str) -> str:
    """Get wind and solar forecasts with P10/P90 bands. Source: renewable_forecast.csv"""
    df = _renewable()
    day = df[df["timestamp_utc"].dt.date == pd.Timestamp(date).date()]
    if day.empty:
        return f"No forecast data for {date}"
    return (
        f"Renewable forecast for {date} — {len(day)} periods (renewable_forecast.csv):\n"
        f"  Wind: avg {day['wind_forecast_mw'].mean():.0f} MW (P10={day['wind_p10_mw'].mean():.0f}, P90={day['wind_p90_mw'].mean():.0f})\n"
        f"  Solar: avg {day['solar_forecast_mw'].mean():.0f} MW\n"
        f"  Forecast error: mean {day['forecast_error_mw'].mean():.1f} MW, std {day['forecast_error_mw'].std():.1f} MW"
    )


@tool
def query_plant_info(plant_id: str = "") -> str:
    """Get plant specs: capacity, efficiency, ramp rates, start costs. Source: plant_portfolio.csv"""
    df = _plants()
    if plant_id:
        df = df[df["plant_id"] == plant_id]
    if df.empty:
        return f"Plant '{plant_id}' not found."
    lines = []
    for idx, p in df.iterrows():
        lines.append(
            f"Row {idx+2}: {p['plant_id']} ({p['plant_name']}) — {p['technology']}\n"
            f"  Capacity: {p['capacity_mw']} MW | Min stable: {p['min_stable_load_mw']} MW\n"
            f"  Efficiency: {p['efficiency_pct']}% | Ramp: {p['max_ramp_up_mw_min']} MW/min\n"
            f"  Start costs — Hot: EUR {p['start_cost_hot_eur']:,} | Warm: EUR {p['start_cost_warm_eur']:,} | Cold: EUR {p['start_cost_cold_eur']:,}\n"
            f"  CO2: {p['co2_intensity_tco2_mwh']} tCO2/MWh | VOM: EUR {p['variable_om_eur_mwh']}/MWh"
        )
    return "\n".join(lines) + "\nSource: plant_portfolio.csv"


@tool
def compute_marginal_cost(plant_id: str, load_mw: float,
                          gas_price: float = 0, co2_price: float = 0) -> str:
    """Compute SRMC at a given load. Formula: SRMC = Gas/Efficiency + CO2*CI + VOM. Source: plant_portfolio.csv, fuel_prices.csv"""
    plants = _plants()
    p = plants[plants["plant_id"] == plant_id]
    if p.empty:
        return f"Unknown plant: {plant_id}."
    p = p.iloc[0]
    if gas_price == 0 or co2_price == 0:
        fuel = _fuel()
        last = fuel.iloc[-1]
        if gas_price == 0:
            gas_price = last["ttf_front_month_eur_mwh"]
        if co2_price == 0:
            co2_price = last["eu_ets_eur_tco2"]
    eta_max = p["efficiency_pct"] / 100
    p_max = p["capacity_mw"]
    eta = eta_max * (1 - 0.15 * (1 - load_mw / p_max) ** 2)
    co2_i = p["co2_intensity_tco2_mwh"]
    vom = p["variable_om_eur_mwh"]
    srmc = gas_price / eta + co2_price * co2_i + vom
    return (
        f"SRMC for {plant_id} at {load_mw} MW:\n"
        f"  Efficiency at load: {eta*100:.1f}% (full-load: {eta_max*100:.1f}%)\n"
        f"  Gas: {gas_price:.2f}/{eta:.3f} = EUR {gas_price/eta:.2f}/MWh\n"
        f"  CO2: {co2_price:.2f}*{co2_i} = EUR {co2_price*co2_i:.2f}/MWh | VOM: EUR {vom}/MWh\n"
        f"  SRMC = EUR {srmc:.2f}/MWh\n"
        f"Inputs: gas={gas_price:.2f}, co2={co2_price:.2f} (fuel_prices.csv)"
    )


@tool
def query_remit_status(trade_id: str = "", status_filter: str = "") -> str:
    """Query REMIT compliance. Filter by trade_id or status. Source: remit_transactions.csv"""
    remit = _remit()
    trades = _trades()
    if trade_id:
        r = remit[remit["trade_id"] == trade_id]
        if r.empty:
            return f"No REMIT record for {trade_id} — may be unreported! (remit_transactions.csv)"
        row = r.iloc[0]
        return (
            f"REMIT for {trade_id}: status={row['status']}, submitted={row['submission_timestamp']}"
            f"{', rejection=' + str(row['rejection_reason']) if row['status'] == 'REJECTED' else ''}"
        )
    if status_filter:
        r = remit[remit["status"] == status_filter]
    else:
        r = remit
    reported = set(remit["trade_id"].unique())
    missing = set(trades["trade_id"].unique()) - reported
    summary = remit["status"].value_counts().to_dict()
    lines = [
        f"REMIT Overview ({len(remit)} reports, remit_transactions.csv):",
        f"  Status: {summary}",
        f"  Missing reports: {len(missing)} trades unreported",
        f"  Total trades: {len(trades)} (trade_blotter.csv)",
    ]
    if status_filter and not r.empty:
        for idx, row in r.head(10).iterrows():
            lines.append(f"    Row {idx+2}: {row['trade_id']} — {row['status']}")
    return "\n".join(lines)


@tool
def query_contract_obligations() -> str:
    """List all contracts with volume, price, tolerance, penalties. Source: contract_obligations.csv"""
    df = _contracts()
    lines = [f"Contracts ({len(df)}, contract_obligations.csv):"]
    for idx, c in df.iterrows():
        lines.append(
            f"  Row {idx+2}: {c['contract_id']} — {c['counterparty']} | "
            f"{c['delivery_profile']} {c['volume_mw']}MW @ EUR {c['price_eur_mwh']} | "
            f"Tolerance: +/-{c['tolerance_pct']}% | Plant: {c['plant_id']}"
        )
    ccgt_peak = df[
        (df["plant_id"] == "RHEIN_CCGT") &
        (df["delivery_profile"].isin(["BASELOAD", "PEAK"]))
    ]["volume_mw"].sum()
    if ccgt_peak > 430:
        lines.append(f"\n  WARNING: CCGT peak commitments = {ccgt_peak} MW > 430 MW capacity!")
    return "\n".join(lines)


@tool
def query_imbalance_data(date: str = "", regulation_state: str = "") -> str:
    """Query imbalance settlement prices. Source: imbalance_prices.csv"""
    df = _imbalance()
    if date:
        df = df[df["timestamp_utc"].dt.date == pd.Timestamp(date).date()]
    if regulation_state:
        df = df[df["regulation_state"] == regulation_state]
    if df.empty:
        return "No imbalance data matching filters."
    spread = df["imbalance_price_short_eur_mwh"] - df["imbalance_price_long_eur_mwh"]
    return (
        f"Imbalance data ({len(df)} periods, imbalance_prices.csv):\n"
        f"  Avg long: EUR {df['imbalance_price_long_eur_mwh'].mean():.2f}/MWh\n"
        f"  Avg short: EUR {df['imbalance_price_short_eur_mwh'].mean():.2f}/MWh\n"
        f"  Avg spread: EUR {spread.mean():.2f}/MWh\n"
        f"  States: {df['regulation_state'].value_counts().to_dict()}"
    )


@tool
def search_reference_docs(query: str) -> str:
    """Search reference documents for EPEX rules, CCGT manual, REMIT guide, balancing framework. Source: data/reference_docs/"""
    docs = {
        "epex_spot_market_rules.md": "EPEX SPOT rules",
        "ccgt_plant_operating_manual.md": "CCGT manual",
        "remit_compliance_guide.md": "REMIT II guide",
        "balancing_imbalance_settlement.md": "Balancing framework",
    }
    query_lower = query.lower()
    results = []
    for filename, label in docs.items():
        path = os.path.join(DATA_DIR, "reference_docs", filename)
        if not os.path.exists(path):
            continue
        with open(path) as f:
            content = f.read()
        for section in content.split("\n## "):
            if query_lower in section.lower():
                results.append(f"[{label} — {filename}]:\n  {section[:500]}...")
                break
    if not results:
        for filename, label in docs.items():
            path = os.path.join(DATA_DIR, "reference_docs", filename)
            if not os.path.exists(path):
                continue
            with open(path) as f:
                content = f.read()
            if query_lower in content.lower():
                idx = content.lower().index(query_lower)
                results.append(f"[{label}]:\n  ...{content[max(0,idx-100):idx+400]}...")
    return f"Found {len(results)} passage(s):\n" + "\n\n".join(results) if results else f"No matches for '{query}'."


# ---------------------------------------------------------------------------
# Specialist agents
# ---------------------------------------------------------------------------

def _make_model():
    return BedrockModel(
        model_id="us.anthropic.claude-opus-4-6-v1",
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
    )


MARKET_ANALYST_PROMPT = """You are the Market Analyst agent for a German utility's intraday trading desk (DE-LU, EPEX SPOT).
Your expertise: electricity price analysis, spread identification, fuel market trends, renewable forecast accuracy.
RULES: Every number must cite source file and row. Use tools — never guess. Show formulas for derived metrics."""

DISPATCH_OPTIMIZER_PROMPT = """You are the Dispatch Optimizer agent for a 4-plant German utility portfolio.
Plants: RHEIN_CCGT (430MW), NORDSEE_WIND (350MW), BAYERN_SOLAR (120MW), ISAR_OCGT (180MW peaker).
Your expertise: merit-order dispatch, marginal cost, part-load efficiency, start-up economics, ramp constraints.
RULES: Every number must cite source file and row. Use tools — never guess. Show SRMC formula and inputs."""

COMPLIANCE_OFFICER_PROMPT = """You are the Compliance Officer agent monitoring REMIT II (EU 2024/1106) and contract compliance.
Your expertise: REMIT reporting (T+1 to ACER), rejection analysis, missing reports, penalty exposure.
RULES: Every number must cite source file and row. Quantify penalties: up to EUR 500K per REMIT violation."""

RISK_MANAGER_PROMPT = """You are the Risk Manager agent for portfolio risk and imbalance exposure.
Your expertise: P&L analysis, imbalance settlement, worst-event identification, strategy performance.
RULES: Every number must cite source file and row. Quantify risk in EUR terms."""

_specialists = {}


def _get_specialist(name: str) -> Agent:
    if name not in _specialists:
        creators = {
            "market_analyst": lambda: Agent(
                model=_make_model(),
                tools=[query_intraday_prices, query_fuel_prices, query_renewable_forecast, search_reference_docs],
                system_prompt=MARKET_ANALYST_PROMPT,
            ),
            "dispatch_optimizer": lambda: Agent(
                model=_make_model(),
                tools=[query_plant_info, compute_marginal_cost, query_contract_obligations, query_fuel_prices, search_reference_docs],
                system_prompt=DISPATCH_OPTIMIZER_PROMPT,
            ),
            "compliance_officer": lambda: Agent(
                model=_make_model(),
                tools=[query_remit_status, query_contract_obligations, query_trade_blotter, search_reference_docs],
                system_prompt=COMPLIANCE_OFFICER_PROMPT,
            ),
            "risk_manager": lambda: Agent(
                model=_make_model(),
                tools=[query_trade_blotter, query_imbalance_data, query_contract_obligations, query_intraday_prices],
                system_prompt=RISK_MANAGER_PROMPT,
            ),
        }
        _specialists[name] = creators[name]()
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


@tool
def ask_market_analyst(question: str) -> str:
    """Route to Market Analyst: electricity prices, VWAP, spreads, fuel/carbon trends, renewable forecasts."""
    return f"[Market Analyst responds]:\n{_call_specialist('market_analyst', question)}"

@tool
def ask_dispatch_optimizer(question: str) -> str:
    """Route to Dispatch Optimizer: plant dispatch, SRMC, part-load efficiency, start-up costs, ramp constraints."""
    return f"[Dispatch Optimizer responds]:\n{_call_specialist('dispatch_optimizer', question)}"

@tool
def ask_compliance_officer(question: str) -> str:
    """Route to Compliance Officer: REMIT reporting, missing/rejected reports, contract tolerances, penalties."""
    return f"[Compliance Officer responds]:\n{_call_specialist('compliance_officer', question)}"

@tool
def ask_risk_manager(question: str) -> str:
    """Route to Risk Manager: P&L, trading strategy performance, imbalance exposure, worst-case events."""
    return f"[Risk Manager responds]:\n{_call_specialist('risk_manager', question)}"


ORCHESTRATOR_PROMPT = """You are the Lead Trading Desk Orchestrator for a German utility on EPEX SPOT (DE-LU).

You coordinate 4 specialist agents:
1. Market Analyst — prices, spreads, fuel, renewables
2. Dispatch Optimizer — plant ops, marginal costs, merit-order
3. Compliance Officer — REMIT, contracts, penalties
4. Risk Manager — P&L, imbalance, strategy performance

Route each question to the best specialist. For cross-domain questions, call multiple specialists and synthesize.
Never answer from memory — always delegate to a specialist who queries the actual data."""


# ---------------------------------------------------------------------------
# AgentCore app
# ---------------------------------------------------------------------------

app = BedrockAgentCoreApp()
log = app.logger

_orchestrator_cache: OrderedDict[str, Agent] = OrderedDict()
_MAX_SESSIONS = 64


def _get_or_create_orchestrator(session_id: str) -> Agent:
    if session_id in _orchestrator_cache:
        _orchestrator_cache.move_to_end(session_id)
        return _orchestrator_cache[session_id]
    if len(_orchestrator_cache) >= _MAX_SESSIONS:
        _orchestrator_cache.popitem(last=False)
    orchestrator = Agent(
        model=_make_model(),
        tools=[ask_market_analyst, ask_dispatch_optimizer, ask_compliance_officer, ask_risk_manager],
        system_prompt=ORCHESTRATOR_PROMPT,
        conversation_manager=NullConversationManager(),
    )
    _orchestrator_cache[session_id] = orchestrator
    return orchestrator


def _extract_prompt(payload: dict):
    if "messages" in payload:
        return payload["messages"]
    prompt = payload.get("prompt", "")
    if not isinstance(prompt, str):
        raise ValueError("prompt must be a string")
    return prompt


@app.entrypoint
async def invoke(payload, context):
    log.info("TradingChatAgent (multi-agent orchestrator) invocation received")

    session_id = getattr(context, "session_id", "default-session")
    orchestrator = _get_or_create_orchestrator(session_id)

    prompt = _extract_prompt(payload)

    async for event in orchestrator.stream_async(prompt):
        if not isinstance(event, dict) or "event" not in event:
            continue
        cbs = event["event"].get("contentBlockStart")
        if cbs is not None and not cbs.get("start"):
            continue
        yield event


if __name__ == "__main__":
    app.run()
