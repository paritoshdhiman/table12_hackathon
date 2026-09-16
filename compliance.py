import pandas as pd
import numpy as np


def check_remit_compliance(trades: pd.DataFrame, remit: pd.DataFrame) -> dict:
    """Cross-reference trade blotter with REMIT transaction reports."""
    all_trade_ids = set(trades["trade_id"].unique())
    reported_trade_ids = set(remit["trade_id"].unique())
    missing = all_trade_ids - reported_trade_ids

    status_counts = remit["status"].value_counts().to_dict()
    rejected = remit[remit["status"] == "REJECTED"]
    pending = remit[remit["status"] == "PENDING"]

    overdue = remit[
        (remit["submission_timestamp"] > remit["reporting_deadline"]) &
        (remit["status"] != "REJECTED")
    ]

    accepted = status_counts.get("ACCEPTED", 0)
    total = len(trades)
    compliance_rate = accepted / total * 100 if total > 0 else 0

    return {
        "total_trades": total,
        "total_remit_reports": len(remit),
        "missing_reports": sorted(missing),
        "missing_count": len(missing),
        "status_counts": status_counts,
        "rejected_reports": rejected,
        "pending_reports": pending,
        "overdue_reports": overdue,
        "compliance_rate": compliance_rate,
    }


def check_contract_obligations(
    contracts: pd.DataFrame,
    trades: pd.DataFrame,
    date_range: tuple = None,
    renewable_forecast: pd.DataFrame = None,
    intraday_prices: pd.DataFrame = None,
    fuel_prices: pd.DataFrame = None,
    plants: pd.DataFrame = None,
) -> pd.DataFrame:
    """Estimate delivery vs committed volume per contract.

    Methodology by contract type:
    - Renewable BASELOAD (PPA-001 wind): forecast capped at contract MW.
    - SHAPED (PPA-002 solar, BAL-001 OCGT): as-produced basis, committed = delivered.
    - Firm thermal BASELOAD/PEAK: plant delivers full commitment, shortfall only
      from physical capacity overcommitment across co-located contracts.
    """
    results = []

    plant_capacity = {}
    if plants is not None:
        for _, p in plants.iterrows():
            plant_capacity[p["plant_id"]] = p["capacity_mw"]

    plant_contracts = {}
    for _, c in contracts.iterrows():
        pid = c["plant_id"]
        plant_contracts.setdefault(pid, []).append(c)

    for _, c in contracts.iterrows():
        contract_id = c["contract_id"]
        plant_id = c["plant_id"]
        volume_mw = c["volume_mw"]
        profile = c["delivery_profile"]
        tolerance = c["tolerance_pct"]
        penalty = c["penalty_eur_mwh"]
        start = c["start_date"]
        end = c["end_date"]

        if date_range:
            d_start, d_end = date_range
        else:
            d_start = start.date() if hasattr(start, "date") else start
            d_end = end.date() if hasattr(end, "date") else end

        is_renewable = plant_id in ("NORDSEE_WIND", "BAYERN_SOLAR")

        if profile == "SHAPED":
            est = _estimate_renewable_delivery(
                plant_id, volume_mw, d_start, d_end, renewable_forecast,
                intraday_prices, fuel_prices, plants,
            )
            committed_mwh = est
            delivered_mwh = est
        elif is_renewable and profile == "BASELOAD":
            committed_mwh, delivered_mwh = _renewable_baseload(
                plant_id, volume_mw, d_start, d_end, renewable_forecast,
            )
        else:
            committed_mwh, delivered_mwh = _firm_thermal_delivery(
                contract_id, plant_id, volume_mw, profile, d_start, d_end,
                plant_capacity.get(plant_id, 9999),
                plant_contracts.get(plant_id, []),
                intraday_prices,
            )

        if committed_mwh > 0:
            pct_deviation = ((delivered_mwh - committed_mwh) / committed_mwh) * 100
        else:
            pct_deviation = 0

        within_tolerance = abs(pct_deviation) <= tolerance
        shortfall_mwh = max(0, committed_mwh - delivered_mwh)
        penalty_exposure = shortfall_mwh * penalty if not within_tolerance else 0

        results.append({
            "contract_id": contract_id,
            "counterparty": c["counterparty"],
            "plant_id": plant_id,
            "profile": profile,
            "volume_mw": volume_mw,
            "committed_mwh": round(committed_mwh, 0),
            "delivered_mwh": round(delivered_mwh, 0),
            "deviation_pct": round(pct_deviation, 1),
            "tolerance_pct": tolerance,
            "within_tolerance": within_tolerance,
            "penalty_exposure_eur": round(penalty_exposure, 0),
        })

    return pd.DataFrame(results)


def _estimate_renewable_delivery(
    plant_id, volume_mw, d_start, d_end, renewable_forecast,
    intraday_prices=None, fuel_prices=None, plants_df=None,
):
    """Estimate MWh for a SHAPED contract: min(forecast, cap) per period."""
    if plant_id == "NORDSEE_WIND" and renewable_forecast is not None:
        rf = renewable_forecast.copy()
        rf["date"] = rf["timestamp_utc"].dt.date
        periods = rf[(rf["date"] >= d_start) & (rf["date"] <= d_end)]
        if not periods.empty:
            return (periods["wind_forecast_mw"].clip(upper=volume_mw) * 0.25).sum()

    if plant_id == "BAYERN_SOLAR" and renewable_forecast is not None:
        rf = renewable_forecast.copy()
        rf["date"] = rf["timestamp_utc"].dt.date
        periods = rf[(rf["date"] >= d_start) & (rf["date"] <= d_end)]
        if not periods.empty:
            return (periods["solar_forecast_mw"].clip(upper=volume_mw) * 0.25).sum()

    if plant_id == "ISAR_OCGT" and intraday_prices is not None and fuel_prices is not None and plants_df is not None:
        plant_row = plants_df[plants_df["plant_id"] == plant_id]
        if not plant_row.empty:
            p = plant_row.iloc[0]
            srmc = (fuel_prices["ttf_front_month_eur_mwh"].mean() / (p["efficiency_pct"] / 100)
                    + fuel_prices["eu_ets_eur_tco2"].mean() * p["co2_intensity_tco2_mwh"]
                    + p["variable_om_eur_mwh"])
            ip = intraday_prices.copy()
            if "date" not in ip.columns:
                ip["date"] = ip["timestamp_utc"].dt.date
            periods = ip[(ip["date"] >= d_start) & (ip["date"] <= d_end)]
            dispatched = periods[periods["vwap_eur_mwh"] > srmc]
            return len(dispatched) * volume_mw * 0.25

    return 0.0


def _renewable_baseload(plant_id, volume_mw, d_start, d_end, renewable_forecast):
    """Renewable plant with BASELOAD commitment (e.g. wind PPA at fixed MW)."""
    if renewable_forecast is None:
        return 0.0, 0.0
    rf = renewable_forecast.copy()
    rf["date"] = rf["timestamp_utc"].dt.date
    periods = rf[(rf["date"] >= d_start) & (rf["date"] <= d_end)]
    if periods.empty:
        return 0.0, 0.0

    n_periods = len(periods)
    committed = volume_mw * 0.25 * n_periods

    col = "wind_forecast_mw" if plant_id == "NORDSEE_WIND" else "solar_forecast_mw"
    delivered = (periods[col].clip(upper=volume_mw) * 0.25).sum()
    return committed, delivered


def _firm_thermal_delivery(
    contract_id, plant_id, volume_mw, profile,
    d_start, d_end, capacity_mw, all_plant_contracts,
    intraday_prices=None,
):
    """Firm thermal contract: plant delivers full commitment minus overcommitment.

    When total contracted MW on one plant exceeds its capacity during certain
    periods, each contract's delivery is pro-rated by its share of the total.
    """
    if intraday_prices is not None:
        ip = intraday_prices.copy()
        if "date" not in ip.columns:
            ip["date"] = ip["timestamp_utc"].dt.date
        periods = ip[(ip["date"] >= d_start) & (ip["date"] <= d_end)]
        is_peak = ((periods["timestamp_utc"].dt.weekday < 5) &
                   (periods["timestamp_utc"].dt.hour >= 8) &
                   (periods["timestamp_utc"].dt.hour < 20))
        n_peak = is_peak.sum()
        n_offpeak = (~is_peak).sum()
    else:
        n_days = (d_end - d_start).days + 1
        weekdays = sum(1 for d in pd.date_range(d_start, periods=n_days) if d.weekday() < 5)
        n_peak = weekdays * 48
        n_offpeak = n_days * 96 - n_peak

    bl_mw = sum(
        ct["volume_mw"] for ct in all_plant_contracts
        if ct["delivery_profile"] == "BASELOAD"
    )
    pk_mw = sum(
        ct["volume_mw"] for ct in all_plant_contracts
        if ct["delivery_profile"] == "PEAK"
    )

    total_peak_mw = bl_mw + pk_mw
    total_offpeak_mw = bl_mw

    peak_ratio = min(1.0, capacity_mw / total_peak_mw) if total_peak_mw > 0 else 1.0
    offpeak_ratio = min(1.0, capacity_mw / total_offpeak_mw) if total_offpeak_mw > 0 else 1.0

    if profile == "BASELOAD":
        committed = volume_mw * 0.25 * (n_peak + n_offpeak)
        delivered = volume_mw * 0.25 * (n_peak * peak_ratio + n_offpeak * offpeak_ratio)
    elif profile == "PEAK":
        committed = volume_mw * 0.25 * n_peak
        delivered = volume_mw * 0.25 * n_peak * peak_ratio
    else:
        committed = volume_mw * 0.25 * (n_peak + n_offpeak)
        delivered = committed

    return committed, delivered


def analyze_imbalance_exposure(imbalance: pd.DataFrame) -> dict:
    """Analyze imbalance settlement data."""
    state_counts = imbalance["regulation_state"].value_counts().to_dict()

    imbalance["spread"] = (
        imbalance["imbalance_price_short_eur_mwh"] -
        imbalance["imbalance_price_long_eur_mwh"]
    )

    worst = imbalance.nlargest(10, "spread")[
        ["timestamp_utc", "imbalance_price_long_eur_mwh",
         "imbalance_price_short_eur_mwh", "spread",
         "system_balance_mw", "regulation_state"]
    ]

    return {
        "state_counts": state_counts,
        "avg_long_price": imbalance["imbalance_price_long_eur_mwh"].mean(),
        "avg_short_price": imbalance["imbalance_price_short_eur_mwh"].mean(),
        "avg_spread": imbalance["spread"].mean(),
        "max_spread": imbalance["spread"].max(),
        "worst_events": worst,
    }
