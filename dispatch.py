import pandas as pd
import numpy as np
from domain import (
    compute_srmc_at_load, part_load_efficiency, temp_corrected_efficiency,
    clean_spark_spread, get_start_type,
)


def _is_peak_hour(timestamp_str: str) -> bool:
    """Peak = weekday hours 8-20 CET."""
    ts = pd.Timestamp(timestamp_str)
    return ts.weekday() < 5 and 8 <= ts.hour < 20


def _get_contract_obligation(contracts: pd.DataFrame, plant_id: str,
                              delivery_start: str, date: str) -> float:
    """Sum MW obligation for a plant in a given delivery period."""
    d = pd.Timestamp(date)
    total = 0.0
    for _, c in contracts[contracts["plant_id"] == plant_id].iterrows():
        if c["start_date"] <= d <= c["end_date"]:
            profile = c["delivery_profile"]
            if profile == "BASELOAD":
                total += c["volume_mw"]
            elif profile == "PEAK" and _is_peak_hour(delivery_start):
                total += c["volume_mw"]
            elif profile == "SHAPED":
                total += c["volume_mw"]
    return total


def optimize_dispatch_for_date(
    date: str,
    intraday_prices: pd.DataFrame,
    fuel_prices: pd.DataFrame,
    renewable_forecast: pd.DataFrame,
    weather: pd.DataFrame,
    plants: pd.DataFrame,
    contracts: pd.DataFrame,
    scenario_overrides: dict = None,
) -> pd.DataFrame:
    """
    Greedy merit-order dispatch for all 96 quarter-hours of a given date.

    scenario_overrides can contain:
      gas_price, co2_price, wind_factor, solar_factor, demand_factor
    """
    date_str = str(date)
    overrides = scenario_overrides or {}

    day_prices = intraday_prices[intraday_prices["date"] == pd.Timestamp(date_str).date()].copy()
    if day_prices.empty:
        return pd.DataFrame()

    day_fuel = fuel_prices[fuel_prices["date"].dt.date == pd.Timestamp(date_str).date()]
    if day_fuel.empty:
        day_fuel = fuel_prices.iloc[[-1]]
    fuel_row = day_fuel.iloc[0]
    gas_price = overrides.get("gas_price", fuel_row["ttf_front_month_eur_mwh"])
    co2_price = overrides.get("co2_price", fuel_row["eu_ets_eur_tco2"])

    wind_factor = overrides.get("wind_factor", 1.0)
    solar_factor = overrides.get("solar_factor", 1.0)
    demand_factor = overrides.get("demand_factor", 1.0)

    day_renew = renewable_forecast[renewable_forecast["timestamp_utc"].dt.date == pd.Timestamp(date_str).date()]
    day_weather = weather[weather["timestamp_utc"].dt.date == pd.Timestamp(date_str).date()]

    ccgt = plants[plants["plant_id"] == "RHEIN_CCGT"].iloc[0]
    ocgt = plants[plants["plant_id"] == "ISAR_OCGT"].iloc[0]

    ccgt_temp = 15.0
    ocgt_temp = 15.0
    if not day_weather.empty:
        ccgt_w = day_weather[day_weather["location"] == "Karlsruhe_CCGT"]
        if not ccgt_w.empty:
            ccgt_temp = ccgt_w["temperature_c"].mean()
        ocgt_w = day_weather[day_weather["location"] == "Landshut_OCGT"]
        if not ocgt_w.empty:
            ocgt_temp = ocgt_w["temperature_c"].mean()

    results = []
    prev_ccgt_mw = 0.0
    prev_ocgt_mw = 0.0

    for _, period in day_prices.iterrows():
        ts = period["timestamp_utc"]
        ds = period["delivery_start"]
        market_price = period["vwap_eur_mwh"]

        renew_row = day_renew[day_renew["timestamp_utc"] == ts]
        wind_mw = 0.0
        solar_mw = 0.0
        if not renew_row.empty:
            wind_mw = renew_row.iloc[0]["wind_forecast_mw"] * wind_factor
            solar_mw = renew_row.iloc[0]["solar_forecast_mw"] * solar_factor

        wind_cap = plants[plants["plant_id"] == "NORDSEE_WIND"]["capacity_mw"].iloc[0]
        solar_cap = plants[plants["plant_id"] == "BAYERN_SOLAR"]["capacity_mw"].iloc[0]
        wind_mw = min(wind_mw, wind_cap)
        solar_mw = min(solar_mw, solar_cap)

        ccgt_obligation = _get_contract_obligation(contracts, "RHEIN_CCGT", ds, date_str) * demand_factor
        ocgt_obligation = _get_contract_obligation(contracts, "ISAR_OCGT", ds, date_str) * demand_factor
        wind_obligation = _get_contract_obligation(contracts, "NORDSEE_WIND", ds, date_str) * demand_factor
        solar_obligation = _get_contract_obligation(contracts, "BAYERN_SOLAR", ds, date_str) * demand_factor

        wind_contracted = min(wind_mw, wind_obligation)
        wind_market = wind_mw - wind_contracted
        solar_contracted = min(solar_mw, solar_obligation)
        solar_market = solar_mw - solar_contracted

        ccgt_cap = ccgt["capacity_mw"]
        ccgt_min = ccgt["min_stable_load_mw"]
        ccgt_obligation_capped = min(ccgt_obligation, ccgt_cap)

        ccgt_srmc_full = compute_srmc_at_load("RHEIN_CCGT", ccgt_cap, gas_price, co2_price, plants, ccgt_temp)
        ccgt_srmc_min = compute_srmc_at_load("RHEIN_CCGT", ccgt_min, gas_price, co2_price, plants, ccgt_temp)

        ccgt_dispatch = 0.0
        if ccgt_obligation_capped > 0:
            ccgt_dispatch = max(ccgt_obligation_capped, ccgt_min)
            ccgt_dispatch = min(ccgt_dispatch, ccgt_cap)

        if market_price > ccgt_srmc_full and ccgt_dispatch < ccgt_cap:
            ccgt_dispatch = ccgt_cap
        elif market_price > ccgt_srmc_min and ccgt_dispatch == 0:
            ccgt_dispatch = ccgt_cap

        if ccgt_dispatch > 0 and ccgt_dispatch < ccgt_min:
            ccgt_dispatch = ccgt_min

        ramp_limit_ccgt = ccgt["max_ramp_up_mw_min"] * 15
        if abs(ccgt_dispatch - prev_ccgt_mw) > ramp_limit_ccgt:
            if ccgt_dispatch > prev_ccgt_mw:
                ccgt_dispatch = min(ccgt_dispatch, prev_ccgt_mw + ramp_limit_ccgt)
            else:
                ccgt_dispatch = max(ccgt_dispatch, prev_ccgt_mw - ramp_limit_ccgt)

        ocgt_cap = ocgt["capacity_mw"]
        ocgt_min = ocgt["min_stable_load_mw"]
        ocgt_srmc_full = compute_srmc_at_load("ISAR_OCGT", ocgt_cap, gas_price, co2_price, plants, ocgt_temp)

        ocgt_dispatch = 0.0
        if ocgt_obligation > 0:
            ocgt_dispatch = max(ocgt_obligation, ocgt_min)
            ocgt_dispatch = min(ocgt_dispatch, ocgt_cap)

        if market_price > ocgt_srmc_full and ocgt_dispatch < ocgt_cap:
            ocgt_dispatch = ocgt_cap

        if ocgt_dispatch > 0 and ocgt_dispatch < ocgt_min:
            ocgt_dispatch = ocgt_min

        ramp_limit_ocgt = ocgt["max_ramp_up_mw_min"] * 15
        if abs(ocgt_dispatch - prev_ocgt_mw) > ramp_limit_ocgt:
            if ocgt_dispatch > prev_ocgt_mw:
                ocgt_dispatch = min(ocgt_dispatch, prev_ocgt_mw + ramp_limit_ocgt)
            else:
                ocgt_dispatch = max(ocgt_dispatch, prev_ocgt_mw - ramp_limit_ocgt)

        ccgt_mc = compute_srmc_at_load("RHEIN_CCGT", max(ccgt_dispatch, ccgt_min), gas_price, co2_price, plants, ccgt_temp) if ccgt_dispatch > 0 else 0
        ocgt_mc = compute_srmc_at_load("ISAR_OCGT", max(ocgt_dispatch, ocgt_min), gas_price, co2_price, plants, ocgt_temp) if ocgt_dispatch > 0 else 0

        ccgt_revenue = ccgt_dispatch * 0.25 * market_price
        ccgt_cost = ccgt_dispatch * 0.25 * ccgt_mc
        ocgt_revenue = ocgt_dispatch * 0.25 * market_price
        ocgt_cost = ocgt_dispatch * 0.25 * ocgt_mc
        wind_revenue = wind_mw * 0.25 * market_price
        solar_revenue = solar_mw * 0.25 * market_price

        css = clean_spark_spread(market_price, gas_price, ccgt["efficiency_pct"] / 100, co2_price, ccgt["co2_intensity_tco2_mwh"])

        citation = (
            f"fuel_prices.csv (ttf={gas_price:.2f}, ets={co2_price:.2f}), "
            f"intraday_prices row {period.name + 2} (vwap={market_price:.2f})"
        )

        for plant_id, dispatch, mc, rev, cost in [
            ("RHEIN_CCGT", ccgt_dispatch, ccgt_mc, ccgt_revenue, ccgt_cost),
            ("ISAR_OCGT", ocgt_dispatch, ocgt_mc, ocgt_revenue, ocgt_cost),
            ("NORDSEE_WIND", wind_mw, 0.0, wind_revenue, 0.0),
            ("BAYERN_SOLAR", solar_mw, 0.0, solar_revenue, 0.0),
        ]:
            results.append({
                "timestamp": ts,
                "delivery_start": ds,
                "plant_id": plant_id,
                "dispatch_mw": round(dispatch, 1),
                "marginal_cost": round(mc, 2),
                "market_price": round(market_price, 2),
                "revenue_eur": round(rev, 2),
                "cost_eur": round(cost, 2),
                "margin_eur": round(rev - cost, 2),
                "clean_spark_spread": round(css, 2),
                "source_citation": citation,
            })

        prev_ccgt_mw = ccgt_dispatch
        prev_ocgt_mw = ocgt_dispatch

    return pd.DataFrame(results)


def summarize_dispatch(dispatch_df: pd.DataFrame) -> dict:
    """Summarize dispatch results into key metrics."""
    if dispatch_df.empty:
        return {}

    by_plant = dispatch_df.groupby("plant_id").agg(
        total_gen_mwh=("dispatch_mw", lambda x: (x * 0.25).sum()),
        total_revenue=("revenue_eur", "sum"),
        total_cost=("cost_eur", "sum"),
        total_margin=("margin_eur", "sum"),
        avg_dispatch_mw=("dispatch_mw", "mean"),
        max_dispatch_mw=("dispatch_mw", "max"),
    ).round(2)

    return {
        "by_plant": by_plant,
        "total_generation_mwh": by_plant["total_gen_mwh"].sum(),
        "total_revenue": by_plant["total_revenue"].sum(),
        "total_cost": by_plant["total_cost"].sum(),
        "total_margin": by_plant["total_margin"].sum(),
        "avg_css": dispatch_df["clean_spark_spread"].mean(),
    }
