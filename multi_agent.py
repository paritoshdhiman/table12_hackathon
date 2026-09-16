import os
import pandas as pd
from strands import Agent
from strands.models.bedrock import BedrockModel
from strands.tools import tool

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
ORCHESTRATOR_MODEL = os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-opus-4-6-v1")
SPECIALIST_MODEL = os.environ.get("SPECIALIST_MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0")

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

def _day_ahead():
    return _load("day_ahead_prices.csv", "market_prices", parse_dates=["delivery_date"])

def _weather():
    return _load("weather_actuals_forecast.csv", "market_prices", parse_dates=["timestamp_utc"])

def _grid():
    return _load("grid_constraints.csv", "grid_constraints", parse_dates=["timestamp_utc"])

def _mc_curves():
    return _load("marginal_cost_curves.csv", "plant_portfolio")


# ═══════════════════════════════════════════════════════════════════════════════
# Tool definitions (shared across specialist agents)
# ═══════════════════════════════════════════════════════════════════════════════

@tool
def query_trade_blotter(date: str = "", plant_id: str = "", strategy: str = "",
                        direction: str = "", min_pnl: float = -999999,
                        max_pnl: float = 999999, limit: int = 20) -> str:
    """Query the trade blotter. Filter by date, plant_id, strategy, direction, or P&L range. Source: trade_blotter.csv"""
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
        f"  90d avg: TTF EUR {df['ttf_front_month_eur_mwh'].mean():.2f}, ETS EUR {df['eu_ets_eur_tco2'].mean():.2f}\n"
        f"  Ranges: TTF {df['ttf_front_month_eur_mwh'].min():.2f}–{df['ttf_front_month_eur_mwh'].max():.2f}, "
        f"ETS {df['eu_ets_eur_tco2'].min():.2f}–{df['eu_ets_eur_tco2'].max():.2f}"
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
        f"  Solar: avg {day['solar_forecast_mw'].mean():.0f} MW (P10={day['solar_p10_mw'].mean():.0f}, P90={day['solar_p90_mw'].mean():.0f})\n"
        f"  Total: avg {day['total_renewable_mw'].mean():.0f} MW\n"
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
    from domain import part_load_efficiency
    eta = part_load_efficiency(eta_max, load_mw, p_max)
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
    ccgt_cap = _plants().loc[_plants()["plant_id"] == "RHEIN_CCGT", "capacity_mw"].iloc[0]
    if ccgt_peak > ccgt_cap:
        lines.append(f"\n  WARNING: CCGT peak commitments = {ccgt_peak} MW > {ccgt_cap} MW capacity!")
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


@tool
def query_day_ahead_prices(date: str, hour: int = -1) -> str:
    """Query day-ahead auction prices by date (YYYY-MM-DD), optionally by hour (0-23). Returns hourly clearing prices, buy/sell volumes, net position. Source: day_ahead_prices.csv"""
    df = _day_ahead()
    day = df[df["delivery_date"].dt.date == pd.Timestamp(date).date()]
    if hour >= 0:
        day = day[day["delivery_hour"] == hour]
    if day.empty:
        return f"No day-ahead data for {date} (hour={hour})"
    lines = [f"Day-ahead prices for {date} — {len(day)} hours (day_ahead_prices.csv)"]
    lines.append(f"  Mean price: EUR {day['price_eur_mwh'].mean():.2f}/MWh")
    lines.append(f"  Min: EUR {day['price_eur_mwh'].min():.2f} (hour {day.loc[day['price_eur_mwh'].idxmin(), 'delivery_hour']})")
    lines.append(f"  Max: EUR {day['price_eur_mwh'].max():.2f} (hour {day.loc[day['price_eur_mwh'].idxmax(), 'delivery_hour']})")
    lines.append(f"  Total buy volume: {day['volume_buy_mwh'].sum():,.0f} MWh")
    lines.append(f"  Total sell volume: {day['volume_sell_mwh'].sum():,.0f} MWh")
    lines.append(f"  Net position (buy-sell): {day['net_position_mwh'].sum():,.0f} MWh")
    if len(day) <= 24:
        lines.append("  Hourly breakdown:")
        for idx, row in day.iterrows():
            lines.append(
                f"    Row {idx+2}: Hour {int(row['delivery_hour']):02d} — EUR {row['price_eur_mwh']:.2f}/MWh | "
                f"Buy: {row['volume_buy_mwh']:,.0f} | Sell: {row['volume_sell_mwh']:,.0f} | Net: {row['net_position_mwh']:,.0f}"
            )
    return "\n".join(lines)


@tool
def query_weather(date: str, location: str = "") -> str:
    """Query weather actuals and forecasts by date (YYYY-MM-DD), optionally by location (Karlsruhe_CCGT, Landshut_OCGT, Nordsee_Wind, Bayern_Solar). Returns temperature, wind speed, solar irradiance, humidity, cloud cover. Source: weather_actuals_forecast.csv"""
    df = _weather()
    day = df[df["timestamp_utc"].dt.date == pd.Timestamp(date).date()]
    if location:
        day = day[day["location"] == location]
    if day.empty:
        return f"No weather data for {date}" + (f" at {location}" if location else "")
    locations = day["location"].unique()
    lines = [f"Weather data for {date} — {len(day)} records (weather_actuals_forecast.csv)"]
    for loc in locations:
        loc_data = day[day["location"] == loc]
        lines.append(f"\n  {loc} ({len(loc_data)} periods):")
        lines.append(f"    Temperature: avg {loc_data['temperature_c'].mean():.1f}°C "
                     f"(min {loc_data['temperature_c'].min():.1f}, max {loc_data['temperature_c'].max():.1f})")
        lines.append(f"    Wind speed: avg {loc_data['wind_speed_ms'].mean():.1f} m/s "
                     f"(max {loc_data['wind_speed_ms'].max():.1f})")
        lines.append(f"    Solar irradiance: avg {loc_data['solar_irradiance_wm2'].mean():.0f} W/m² "
                     f"(max {loc_data['solar_irradiance_wm2'].max():.0f})")
        lines.append(f"    Cloud cover: avg {loc_data['cloud_cover_pct'].mean():.0f}%")
        lines.append(f"    Humidity: avg {loc_data['humidity_pct'].mean():.0f}%")
        lines.append(f"    Pressure: avg {loc_data['pressure_hpa'].mean():.1f} hPa")
        is_forecast_pct = loc_data['is_forecast'].mean() * 100
        lines.append(f"    Data type: {is_forecast_pct:.0f}% forecast, {100-is_forecast_pct:.0f}% actual")
        if loc == "Karlsruhe_CCGT":
            avg_temp = loc_data['temperature_c'].mean()
            from domain import temp_corrected_efficiency
            ccgt = _plants()[_plants()["plant_id"] == "RHEIN_CCGT"].iloc[0]
            eta_rated = ccgt["efficiency_pct"] / 100
            eta_corrected = temp_corrected_efficiency(eta_rated, avg_temp)
            if eta_corrected < eta_rated:
                eff_penalty = (1 - eta_corrected / eta_rated) * 100
                lines.append(f"    CCGT impact: {avg_temp:.1f}°C → efficiency derated by {eff_penalty:.1f}% from ISO 15°C")
    return "\n".join(lines)


@tool
def query_grid_constraints(date: str, from_zone: str = "", to_zone: str = "") -> str:
    """Query cross-border grid constraints (ATC, NTC, scheduled flows, congestion, redispatch, curtailment). Filter by date and optionally by from_zone or to_zone (DE-LU, AT, FR, NL). Source: grid_constraints.csv"""
    df = _grid()
    day = df[df["timestamp_utc"].dt.date == pd.Timestamp(date).date()]
    if from_zone:
        day = day[day["from_zone"] == from_zone]
    if to_zone:
        day = day[day["to_zone"] == to_zone]
    if day.empty:
        return f"No grid constraint data for {date}"
    borders = day.groupby(["from_zone", "to_zone"]).agg({
        "atc_mw": "mean",
        "ntc_mw": "mean",
        "scheduled_flow_mw": "mean",
        "congestion_rent_eur_mwh": "mean",
        "redispatch_volume_mw": "sum",
        "curtailment_mw": "sum",
    }).reset_index()
    lines = [f"Grid constraints for {date} — {len(day)} records (grid_constraints.csv)"]
    for idx, b in borders.iterrows():
        lines.append(
            f"  {b['from_zone']} → {b['to_zone']}:"
            f" ATC={b['atc_mw']:.0f}MW, NTC={b['ntc_mw']:.0f}MW,"
            f" Scheduled flow={b['scheduled_flow_mw']:.0f}MW,"
            f" Congestion={b['congestion_rent_eur_mwh']:.2f} EUR/MWh,"
            f" Redispatch={b['redispatch_volume_mw']:.0f}MW,"
            f" Curtailment={b['curtailment_mw']:.0f}MW"
        )
    total_curtail = day["curtailment_mw"].sum()
    total_redispatch = day["redispatch_volume_mw"].sum()
    if total_curtail > 0:
        lines.append(f"\n  Total curtailment: {total_curtail:.0f} MW")
    if total_redispatch > 0:
        lines.append(f"  Total redispatch: {total_redispatch:.0f} MW")
    return "\n".join(lines)


@tool
def query_marginal_cost_curves(plant_id: str = "") -> str:
    """Query pre-calculated marginal cost curves showing cost at different load levels. Source: marginal_cost_curves.csv"""
    df = _mc_curves()
    if plant_id:
        df = df[df["plant_id"] == plant_id]
    if df.empty:
        return f"No marginal cost curves for '{plant_id}'"
    lines = [f"Marginal cost curves ({len(df)} data points, marginal_cost_curves.csv):"]
    for pid in df["plant_id"].unique():
        plant_data = df[df["plant_id"] == pid].sort_values("load_mw")
        lines.append(f"\n  {pid}:")
        for idx, row in plant_data.iterrows():
            lines.append(f"    Row {idx+2}: Load {row['load_mw']:.0f}MW → MC EUR {row['marginal_cost_eur_mwh']:.2f}/MWh")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# Specialist agent definitions
# ═══════════════════════════════════════════════════════════════════════════════

def _make_model(role="specialist"):
    model_id = ORCHESTRATOR_MODEL if role == "orchestrator" else SPECIALIST_MODEL
    return BedrockModel(
        model_id=model_id,
        region_name=AWS_REGION,
    )


MARKET_ANALYST_PROMPT = """You are the Market Analyst agent for a German utility's intraday trading desk (DE-LU, EPEX SPOT).

Your expertise: electricity price analysis, spread identification, fuel market trends, renewable forecast accuracy, weather impact on generation, and price distribution patterns across the full dataset of quarter-hourly periods (Jan-Apr 2026).

RULES:
1. Every number must cite source file and row. Format: "EUR X (source: file.csv, row N)"
2. Use your tools to look up data — never guess.
3. Show formulas when computing spreads or derived metrics.
4. Focus on actionable trading signals: where are the spread opportunities, what's driving price, is the forecast biased.

Data sources you can query:
- intraday_prices_epex.csv: quarter-hourly VWAP, high, low, volume, spreads
- day_ahead_prices.csv: hourly DA auction prices, buy/sell volumes, net position
- fuel_prices.csv: daily TTF gas, ETS carbon, coal, Brent oil
- renewable_forecast.csv: wind/solar forecasts with P10/P90 bands, forecast errors
- weather_actuals_forecast.csv: temperature, wind speed, solar irradiance at 4 plant locations
- 4 reference docs: EPEX rules, CCGT manual, REMIT guide, balancing framework

Key formulas:
- Clean Spark Spread = Power_Price - Gas/Efficiency - CO2*CO2_Intensity
- ID-DA Spread = Intraday_VWAP - Day_Ahead_Price"""


DISPATCH_OPTIMIZER_PROMPT = """You are the Dispatch Optimizer agent for a 4-plant German utility portfolio.

Your expertise: merit-order dispatch, marginal cost calculation, part-load efficiency (Willans line), start-up economics (hot/warm/cold), ramp constraints, temperature derating, grid constraints, and contract obligation fulfillment.

RULES:
1. Every number must cite source file and row.
2. Use tools to get actual plant parameters and fuel prices — never assume.
3. Show the SRMC formula and all inputs when computing costs.
4. Check for CCGT overcommitment: compare total peak-hour contract MW against plant capacity from plant_portfolio.csv.
5. Check weather for temperature derating and grid constraints for curtailment/redispatch.

Data sources you can query:
- plant_portfolio.csv: 4 plants with capacity, efficiency, ramp rates, start costs, CO2 intensity
- marginal_cost_curves.csv: pre-calculated MC at different load levels
- contract_obligations.csv: 6 PPAs/bilateral contracts with tolerances and penalties
- fuel_prices.csv: daily TTF gas and EU ETS carbon prices
- weather_actuals_forecast.csv: temperature at plant locations for efficiency derating
- grid_constraints.csv: cross-border ATC/NTC, congestion, redispatch, curtailment
- 4 reference docs: EPEX rules, CCGT manual, REMIT guide, balancing framework

Key formulas:
- SRMC = Gas_Price / Efficiency + CO2_Price * CO2_Intensity + VOM
- Part-load efficiency: eta(P) = eta_max * (1 - 0.15 * (1 - P/P_max)^2)
- CCGT temp correction: -0.5%/°C above 15°C ISO"""


COMPLIANCE_OFFICER_PROMPT = """You are the Compliance Officer agent monitoring REMIT II (EU 2024/1106) and contract compliance.

Your expertise: REMIT transaction reporting requirements (T+1 to ACER), rejection analysis, missing report detection, contract tolerance tracking, and penalty exposure assessment.

RULES:
1. Every number must cite source file and row.
2. Use tools to check actual compliance status — never guess.
3. Quantify penalty exposure: REMIT violations up to EUR 500K each, contract penalties per EUR/MWh deviation.
4. Flag urgent issues: unreported trades, rejected reports needing resubmission, tolerance breaches.

Key regulations:
- REMIT II: all wholesale energy transactions reported to ACER within T+1 business day
- Penalties: up to EUR 500K per violation or 10x profit gained
- Contract tolerances vary per contract (typically 3-5%)"""


RISK_MANAGER_PROMPT = """You are the Risk Manager agent for portfolio risk and imbalance exposure.

Your expertise: P&L analysis, Value-at-Risk, imbalance settlement prices (short/long spreads), worst-event identification, contract overcommitment risk, grid constraint risk, and trading strategy performance.

RULES:
1. Every number must cite source file and row.
2. Use tools to pull actual trade and imbalance data — never guess.
3. Quantify risk in EUR terms: what's the downside, what's the exposure.
4. Compare strategies: which are profitable, which are losing money.

Data sources you can query:
- trade_blotter.csv: trades with P&L across 4 strategies (DA_HEDGE, ID_OPTIM, BALANCING, SPREAD)
- imbalance_prices.csv: quarter-hourly settlement periods with short/long prices
- contract_obligations.csv: 6 contracts with tolerance and penalty terms
- intraday_prices_epex.csv: market prices for exposure calculations
- grid_constraints.csv: cross-border congestion, redispatch volumes, curtailment events"""


def create_market_analyst() -> Agent:
    return Agent(
        model=_make_model(),
        tools=[query_intraday_prices, query_day_ahead_prices, query_fuel_prices,
               query_renewable_forecast, query_weather, search_reference_docs],
        system_prompt=MARKET_ANALYST_PROMPT,
    )


def create_dispatch_optimizer() -> Agent:
    return Agent(
        model=_make_model(),
        tools=[query_plant_info, compute_marginal_cost, query_marginal_cost_curves,
               query_contract_obligations, query_fuel_prices, query_weather,
               query_grid_constraints, search_reference_docs],
        system_prompt=DISPATCH_OPTIMIZER_PROMPT,
    )


def create_compliance_officer() -> Agent:
    return Agent(
        model=_make_model(),
        tools=[query_remit_status, query_contract_obligations, query_trade_blotter, search_reference_docs],
        system_prompt=COMPLIANCE_OFFICER_PROMPT,
    )


def create_risk_manager() -> Agent:
    return Agent(
        model=_make_model(),
        tools=[query_trade_blotter, query_imbalance_data, query_contract_obligations,
               query_intraday_prices, query_grid_constraints],
        system_prompt=RISK_MANAGER_PROMPT,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Orchestrator
# ═══════════════════════════════════════════════════════════════════════════════

_specialists = {}


def _get_specialist(name: str) -> Agent:
    if name not in _specialists:
        creators = {
            "market_analyst": create_market_analyst,
            "dispatch_optimizer": create_dispatch_optimizer,
            "compliance_officer": create_compliance_officer,
            "risk_manager": create_risk_manager,
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
    """Route a question to the Market Analyst agent. This specialist handles: electricity prices, VWAP analysis, spreads (intraday vs day-ahead), fuel/carbon market trends, renewable forecasts, price patterns and distributions. Use for any question about market conditions, price movements, or energy commodity analysis."""
    return f"[Market Analyst responds]:\n{_call_specialist('market_analyst', question)}"


@tool
def ask_dispatch_optimizer(question: str) -> str:
    """Route a question to the Dispatch Optimizer agent. This specialist handles: plant dispatch decisions, marginal cost calculations (SRMC), part-load efficiency, start-up economics (hot/warm/cold), ramp constraints, merit-order stack, temperature derating, contract obligation fulfillment. Use for any question about plant operations, generation costs, or dispatch strategy."""
    return f"[Dispatch Optimizer responds]:\n{_call_specialist('dispatch_optimizer', question)}"


@tool
def ask_compliance_officer(question: str) -> str:
    """Route a question to the Compliance Officer agent. This specialist handles: REMIT II reporting status, missing/rejected/pending reports, contract tolerance tracking, penalty exposure, regulatory requirements. Use for any question about compliance, reporting gaps, or regulatory risk."""
    return f"[Compliance Officer responds]:\n{_call_specialist('compliance_officer', question)}"


@tool
def ask_risk_manager(question: str) -> str:
    """Route a question to the Risk Manager agent. This specialist handles: P&L analysis, trading strategy performance, imbalance exposure, short/long price spreads, worst-case events, portfolio risk metrics. Use for any question about profits, losses, risk, or imbalance settlement."""
    return f"[Risk Manager responds]:\n{_call_specialist('risk_manager', question)}"


ORCHESTRATOR_PROMPT = """You are the Lead Trading Desk Orchestrator for a German utility operating on EPEX SPOT (DE-LU bidding zone).

You coordinate 4 specialist agents (Claude Sonnet — fast, cost-efficient), each with their own tools and expertise. Together they cover ALL 12 data files + 4 reference documents. You (Claude Opus) synthesize their findings into coherent answers.

1. **Market Analyst** (6 tools) — intraday prices, day-ahead prices, fuel prices, renewable forecasts, weather data, reference docs
2. **Dispatch Optimizer** (8 tools) — plant portfolio, marginal cost calculation, MC curves, contracts, fuel, weather, grid constraints, reference docs
3. **Compliance Officer** (4 tools) — REMIT status, contract obligations, trade blotter, reference docs
4. **Risk Manager** (5 tools) — trade blotter, imbalance prices, contracts, intraday prices, grid constraints

COMPLETE DATA COVERAGE (every file is queryable):
- market_prices/: intraday_prices_epex.csv, day_ahead_prices.csv, fuel_prices.csv, trade_blotter.csv, remit_transactions.csv, renewable_forecast.csv, imbalance_prices.csv, weather_actuals_forecast.csv
- plant_portfolio/: plant_portfolio.csv, contract_obligations.csv, marginal_cost_curves.csv
- grid_constraints/: grid_constraints.csv
- reference_docs/: epex_spot_market_rules.md, ccgt_plant_operating_manual.md, remit_compliance_guide.md, balancing_imbalance_settlement.md

ROUTING RULES:
- Route each question to the MOST relevant specialist using the ask_* tools.
- For questions spanning multiple domains, call multiple specialists and synthesize.
- Never answer from memory — always delegate to a specialist who will query the actual data.
- After receiving a specialist's response, present it clearly with proper formatting.
- If a question doesn't clearly fit one specialist, start with the most likely and follow up if needed.

ROUTING EXAMPLES:
- "What was the most profitable trade?" → ask_risk_manager
- "Calculate CCGT SRMC at 300MW" → ask_dispatch_optimizer
- "How many trades are missing REMIT reports?" → ask_compliance_officer
- "What was the average price last week?" → ask_market_analyst
- "What was the day-ahead price vs intraday?" → ask_market_analyst
- "What was the temperature at the CCGT plant?" → ask_market_analyst (weather) or ask_dispatch_optimizer (for derating)
- "Were there grid congestion events?" → ask_dispatch_optimizer or ask_risk_manager
- "Is the CCGT overcommitted?" → ask_dispatch_optimizer (contracts + capacity)
- "Compare wind forecast accuracy and P&L impact" → ask_market_analyst THEN ask_risk_manager

Present the specialist's findings clearly. Add your own synthesis when combining multiple specialists' outputs."""


def create_orchestrator() -> Agent:
    return Agent(
        model=_make_model("orchestrator"),
        tools=[
            ask_market_analyst,
            ask_dispatch_optimizer,
            ask_compliance_officer,
            ask_risk_manager,
        ],
        system_prompt=ORCHESTRATOR_PROMPT,
    )
