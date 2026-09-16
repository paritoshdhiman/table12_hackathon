import os
import pandas as pd
from strands import Agent
from strands.models.bedrock import BedrockModel
from strands.tools import tool

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-opus-4-6-v1")

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


def _mc_curves():
    return _load("marginal_cost_curves.csv", "plant_portfolio")


@tool
def query_trade_blotter(date: str = "", plant_id: str = "", strategy: str = "",
                        direction: str = "", min_pnl: float = -999999,
                        max_pnl: float = 999999, limit: int = 20) -> str:
    """Query the trade blotter (2,689 trades, Jan-Apr 2026). Filter by date (YYYY-MM-DD), plant_id (RHEIN_CCGT/ISAR_OCGT/NORDSEE_WIND/BAYERN_SOLAR), strategy (DA_HEDGE/ID_OPTIM/BALANCING/SPREAD), direction (BUY/SELL), or P&L range. Source: data/market_prices/trade_blotter.csv"""
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
        csv_row = idx + 2
        lines.append(
            f"  Row {csv_row}: {row['trade_id']} | {row['direction']} {row['volume_mw']}MW "
            f"@ EUR {row['price_eur_mwh']:.2f} | P&L: EUR {row['pnl_eur']:,.2f} | "
            f"Strategy: {row['strategy']} | Plant: {row.get('plant_id', 'N/A')}"
        )
    return "\n".join(lines)


@tool
def query_intraday_prices(date: str, hour: int = -1) -> str:
    """Query intraday EPEX SPOT prices for a date (YYYY-MM-DD), optionally filtering by hour (0-23). Returns VWAP, high, low, volume per quarter-hour. Source: data/market_prices/intraday_prices_epex.csv"""
    df = _intraday()
    df_day = df[df["timestamp_utc"].dt.date == pd.Timestamp(date).date()]
    if hour >= 0:
        df_day = df_day[df_day["timestamp_utc"].dt.hour == hour]

    if df_day.empty:
        return f"No data for {date} (hour={hour})"

    lines = [f"Intraday prices for {date} — {len(df_day)} periods (intraday_prices_epex.csv)"]
    lines.append(f"  Mean VWAP: EUR {df_day['vwap_eur_mwh'].mean():.2f}/MWh")
    lines.append(f"  Min VWAP: EUR {df_day['vwap_eur_mwh'].min():.2f} | Max: EUR {df_day['vwap_eur_mwh'].max():.2f}")
    lines.append(f"  Total volume: {df_day['volume_mwh'].sum():,.1f} MWh | Trades: {df_day['num_trades'].sum()}")

    top = df_day.nlargest(5, "vwap_eur_mwh")
    lines.append("  Top 5 highest priced periods:")
    for idx, row in top.iterrows():
        lines.append(
            f"    Row {idx+2}: {row['delivery_start']} VWAP={row['vwap_eur_mwh']:.2f}, "
            f"High={row['high_eur_mwh']:.2f}, Low={row['low_eur_mwh']:.2f}"
        )
    return "\n".join(lines)


@tool
def query_plant_info(plant_id: str = "") -> str:
    """Get plant specs: capacity, efficiency, ramp rates, start costs, min stable load. Leave plant_id empty for all plants. Source: data/plant_portfolio/plant_portfolio.csv"""
    df = _plants()
    if plant_id:
        df = df[df["plant_id"] == plant_id]
    if df.empty:
        return f"Plant '{plant_id}' not found. Available: RHEIN_CCGT, ISAR_OCGT, NORDSEE_WIND, BAYERN_SOLAR"

    lines = []
    for idx, p in df.iterrows():
        lines.append(
            f"Row {idx+2}: {p['plant_id']} ({p['plant_name']}) — {p['technology']}\n"
            f"  Capacity: {p['capacity_mw']} MW | Min stable: {p['min_stable_load_mw']} MW\n"
            f"  Efficiency: {p['efficiency_pct']}% | Heat rate: {p['heat_rate_btu_kwh']} Btu/kWh\n"
            f"  Ramp up: {p['max_ramp_up_mw_min']} MW/min | Down: {p['max_ramp_down_mw_min']} MW/min\n"
            f"  Start costs — Hot: EUR {p['start_cost_hot_eur']:,} | Warm: EUR {p['start_cost_warm_eur']:,} | Cold: EUR {p['start_cost_cold_eur']:,}\n"
            f"  Min run: {p['min_run_time_hrs']}h | Min down: {p['min_down_time_hrs']}h\n"
            f"  CO2: {p['co2_intensity_tco2_mwh']} tCO2/MWh | VOM: EUR {p['variable_om_eur_mwh']}/MWh"
        )
    return "\n".join(lines) + "\nSource: plant_portfolio.csv"


@tool
def compute_marginal_cost(plant_id: str, load_mw: float,
                          gas_price: float = 0, co2_price: float = 0) -> str:
    """Compute SRMC for RHEIN_CCGT or ISAR_OCGT at a given load (MW). If gas_price/co2_price=0, uses latest from fuel_prices.csv. Formula: SRMC = Gas/Efficiency + CO2*CO2_Intensity + VOM. Source: plant_portfolio.csv, fuel_prices.csv, ccgt_plant_operating_manual.md"""
    plants = _plants()
    p = plants[plants["plant_id"] == plant_id]
    if p.empty:
        return f"Unknown plant: {plant_id}. Use RHEIN_CCGT or ISAR_OCGT."
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
    k = 0.15
    eta = eta_max * (1 - k * (1 - load_mw / p_max) ** 2)
    co2_i = p["co2_intensity_tco2_mwh"]
    vom = p["variable_om_eur_mwh"]
    srmc = gas_price / eta + co2_price * co2_i + vom

    return (
        f"SRMC for {plant_id} at {load_mw} MW:\n"
        f"  Efficiency at load: {eta*100:.1f}% (full-load: {eta_max*100:.1f}%)\n"
        f"  Gas cost: {gas_price:.2f} / {eta:.3f} = EUR {gas_price/eta:.2f}/MWh\n"
        f"  CO2 cost: {co2_price:.2f} * {co2_i} = EUR {co2_price*co2_i:.2f}/MWh\n"
        f"  VOM: EUR {vom}/MWh\n"
        f"  **SRMC = EUR {srmc:.2f}/MWh**\n"
        f"Inputs: gas={gas_price:.2f} (fuel_prices.csv), co2={co2_price:.2f} (fuel_prices.csv)\n"
        f"Formula: SRMC = Gas/Eff + CO2*CI + VOM (ccgt_plant_operating_manual.md)"
    )


@tool
def query_remit_status(trade_id: str = "", status_filter: str = "") -> str:
    """Query REMIT compliance status. Filter by trade_id or status (ACCEPTED/REJECTED/PENDING/SUBMITTED). Source: remit_transactions.csv, trade_blotter.csv"""
    remit = _remit()
    trades = _trades()

    if trade_id:
        r = remit[remit["trade_id"] == trade_id]
        if r.empty:
            return f"No REMIT record for trade {trade_id} — this trade may be unreported! (Source: remit_transactions.csv)"
        row = r.iloc[0]
        return (
            f"REMIT report for {trade_id}: status={row['status']}, "
            f"submitted={row['submission_timestamp']}, deadline={row['reporting_deadline']}"
            f"{', rejection_reason=' + str(row['rejection_reason']) if row['status'] == 'REJECTED' else ''}\n"
            f"Source: remit_transactions.csv"
        )

    if status_filter:
        r = remit[remit["status"] == status_filter]
    else:
        r = remit

    reported_ids = set(remit["trade_id"].unique())
    all_ids = set(trades["trade_id"].unique())
    missing = all_ids - reported_ids

    summary = remit["status"].value_counts().to_dict()
    lines = [
        f"REMIT Overview (remit_transactions.csv, {len(remit)} reports):",
        f"  Status breakdown: {summary}",
        f"  Trades without REMIT report: {len(missing)}",
        f"  Total trades: {len(trades)} (trade_blotter.csv)",
    ]

    if status_filter and not r.empty:
        lines.append(f"\n  Showing up to 10 {status_filter} reports:")
        for idx, row in r.head(10).iterrows():
            lines.append(
                f"    Row {idx+2}: {row['trade_id']} — {row['status']} "
                f"(submitted: {row['submission_timestamp']})"
            )

    return "\n".join(lines)


@tool
def query_renewable_forecast(date: str) -> str:
    """Get wind and solar forecasts for a date (YYYY-MM-DD) with P10/P90 bands. Source: renewable_forecast.csv"""
    df = _renewable()
    day = df[df["timestamp_utc"].dt.date == pd.Timestamp(date).date()]
    if day.empty:
        return f"No forecast data for {date}"

    lines = [
        f"Renewable forecast for {date} — {len(day)} periods (renewable_forecast.csv):",
        f"  Wind: avg {day['wind_forecast_mw'].mean():.0f} MW "
        f"(P10={day['wind_p10_mw'].mean():.0f}, P90={day['wind_p90_mw'].mean():.0f})",
        f"  Solar: avg {day['solar_forecast_mw'].mean():.0f} MW "
        f"(P10={day['solar_p10_mw'].mean():.0f}, P90={day['solar_p90_mw'].mean():.0f})",
        f"  Total renewable: avg {day['total_renewable_mw'].mean():.0f} MW",
        f"  Forecast error (actual-forecast): mean {day['forecast_error_mw'].mean():.1f} MW, "
        f"std {day['forecast_error_mw'].std():.1f} MW",
    ]
    return "\n".join(lines)


@tool
def query_fuel_prices(date: str = "") -> str:
    """Get gas (TTF), carbon (EU ETS), coal, oil prices. If no date, returns latest + summary. Source: fuel_prices.csv"""
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
            f"  Coal API2: USD {r['coal_api2_usd_t']:.2f}/t\n"
            f"  Brent: USD {r['brent_usd_bbl']:.2f}/bbl"
        )

    last = df.iloc[-1]
    return (
        f"Fuel price summary (fuel_prices.csv, {len(df)} days):\n"
        f"  Latest ({last['date'].date()}):\n"
        f"    TTF: EUR {last['ttf_front_month_eur_mwh']:.2f} | ETS: EUR {last['eu_ets_eur_tco2']:.2f}\n"
        f"  90-day averages:\n"
        f"    TTF: EUR {df['ttf_front_month_eur_mwh'].mean():.2f} | ETS: EUR {df['eu_ets_eur_tco2'].mean():.2f}\n"
        f"  Ranges:\n"
        f"    TTF: EUR {df['ttf_front_month_eur_mwh'].min():.2f}–{df['ttf_front_month_eur_mwh'].max():.2f}\n"
        f"    ETS: EUR {df['eu_ets_eur_tco2'].min():.2f}–{df['eu_ets_eur_tco2'].max():.2f}"
    )


@tool
def query_contract_obligations() -> str:
    """List all PPA and bilateral contracts with volume, price, tolerance, penalties. Source: contract_obligations.csv"""
    df = _contracts()
    lines = [f"Contract obligations ({len(df)} contracts, contract_obligations.csv):"]
    for idx, c in df.iterrows():
        lines.append(
            f"  Row {idx+2}: {c['contract_id']} — {c['counterparty']}\n"
            f"    Type: {c['contract_type']} | Profile: {c['delivery_profile']}\n"
            f"    Volume: {c['volume_mw']} MW | Price: EUR {c['price_eur_mwh']}/MWh\n"
            f"    Period: {c['start_date'].date()} to {c['end_date'].date()}\n"
            f"    Tolerance: +/-{c['tolerance_pct']}% | Penalty: EUR {c['penalty_eur_mwh']}/MWh\n"
            f"    Plant: {c['plant_id']}"
        )

    ccgt_peak = df[
        (df["plant_id"] == "RHEIN_CCGT") &
        (df["delivery_profile"].isin(["BASELOAD", "PEAK"]))
    ]["volume_mw"].sum()
    ccgt_cap = _plants()[_plants()["plant_id"] == "RHEIN_CCGT"]["capacity_mw"].iloc[0]
    if ccgt_peak > ccgt_cap:
        lines.append(
            f"\n  WARNING: CCGT peak-hour commitments total {ccgt_peak} MW "
            f"but RHEIN_CCGT capacity is only {ccgt_cap:.0f} MW!"
        )
    return "\n".join(lines)


@tool
def query_imbalance_data(date: str = "", regulation_state: str = "") -> str:
    """Query imbalance settlement prices. Filter by date and/or regulation_state (LONG/SHORT/BALANCED). Source: imbalance_prices.csv"""
    df = _imbalance()
    if date:
        df = df[df["timestamp_utc"].dt.date == pd.Timestamp(date).date()]
    if regulation_state:
        df = df[df["regulation_state"] == regulation_state]
    if df.empty:
        return "No imbalance data matching filters."

    lines = [
        f"Imbalance data ({len(df)} periods, imbalance_prices.csv):",
        f"  Avg long price: EUR {df['imbalance_price_long_eur_mwh'].mean():.2f}/MWh",
        f"  Avg short price: EUR {df['imbalance_price_short_eur_mwh'].mean():.2f}/MWh",
        f"  Avg spread (short-long): EUR {(df['imbalance_price_short_eur_mwh'] - df['imbalance_price_long_eur_mwh']).mean():.2f}/MWh",
        f"  Regulation states: {df['regulation_state'].value_counts().to_dict()}",
    ]
    return "\n".join(lines)


@tool
def search_reference_docs(query: str) -> str:
    """Search the 4 reference documents for rules about: EPEX SPOT market rules, CCGT operating manual, REMIT II compliance, or German balancing/imbalance settlement. Provide a keyword or topic. Source: data/reference_docs/"""
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

        sections = content.split("\n## ")
        for section in sections:
            if query_lower in section.lower():
                snippet = section[:500]
                results.append(f"[{label} — {filename}]:\n  {snippet}...")
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
                start = max(0, idx - 100)
                end = min(len(content), idx + 400)
                results.append(f"[{label} — {filename}]:\n  ...{content[start:end]}...")

    if results:
        return f"Found {len(results)} relevant passage(s):\n" + "\n\n".join(results)
    return f"No passages found matching '{query}' in reference documents."


SYSTEM_PROMPT = """You are an expert Intraday Energy Trading Analyst for a German utility operating in the DE-LU bidding zone on EPEX SPOT.

You have access to 90 days of trading data (Jan 5 - Apr 4, 2026) for a portfolio of 4 plants:
- RHEIN_CCGT: 430 MW Combined Cycle Gas Turbine (Siemens H-class)
- NORDSEE_WIND: 350 MW offshore wind farm
- BAYERN_SOLAR: 120 MW solar park
- ISAR_OCGT: 180 MW Open Cycle Gas Turbine (peaker)

CRITICAL RULES:
1. EVERY number you cite MUST reference the source file and row number.
   Format: "EUR X/MWh (source: filename.csv, row N)"
2. If the data doesn't support a claim, say so explicitly — don't fill gaps.
3. ALWAYS use the query tools to look up actual data before answering. Never guess.
4. When computing costs or margins, show the formula and all inputs.
5. Reference the operating manuals and market rules when discussing constraints.

Key formulas:
- SRMC = Gas_Price / Efficiency + CO2_Price * CO2_Intensity + VOM
- Part-load efficiency: eta(P) = eta_max * (1 - 0.15 * (1 - P/P_max)^2)
- Clean Spark Spread = Power_Price - Gas/Eff - CO2*CI
- CCGT temp correction: -0.5%/C above 15C ISO

Data files available via tools:
- trade_blotter.csv (2,689 trades with P&L)
- intraday_prices_epex.csv (8,640 15-min periods)
- plant_portfolio.csv (4 plants)
- fuel_prices.csv (90 daily gas/carbon prices)
- contract_obligations.csv (6 PPAs/contracts)
- remit_transactions.csv (2,554 ACER reports)
- renewable_forecast.csv (wind/solar forecasts)
- imbalance_prices.csv (TSO settlement)
- marginal_cost_curves.csv (thermal MC curves)

Reference docs: EPEX SPOT rules, CCGT manual, REMIT guide, balancing framework."""


def create_chat_agent() -> Agent:
    model = BedrockModel(
        model_id=BEDROCK_MODEL_ID,
        region_name=AWS_REGION,
    )
    return Agent(
        model=model,
        tools=[
            query_trade_blotter,
            query_intraday_prices,
            query_plant_info,
            compute_marginal_cost,
            query_remit_status,
            query_renewable_forecast,
            query_fuel_prices,
            query_contract_obligations,
            query_imbalance_data,
            search_reference_docs,
        ],
        system_prompt=SYSTEM_PROMPT,
    )
