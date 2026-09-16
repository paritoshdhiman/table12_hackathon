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
) -> pd.DataFrame:
    """Check actual delivery vs committed volume per contract."""
    results = []

    for _, c in contracts.iterrows():
        contract_id = c["contract_id"]
        plant_id = c["plant_id"]
        volume_mw = c["volume_mw"]
        profile = c["delivery_profile"]
        tolerance = c["tolerance_pct"]
        penalty = c["penalty_eur_mwh"]
        start = c["start_date"]
        end = c["end_date"]

        plant_sells = trades[
            (trades["plant_id"] == plant_id) &
            (trades["direction"] == "SELL")
        ].copy()

        plant_sells["delivery_dt"] = pd.to_datetime(plant_sells["delivery_start"])

        if date_range:
            plant_sells = plant_sells[
                (plant_sells["delivery_dt"].dt.date >= date_range[0]) &
                (plant_sells["delivery_dt"].dt.date <= date_range[1])
            ]
        else:
            plant_sells = plant_sells[
                (plant_sells["delivery_dt"].dt.date >= start.date()) &
                (plant_sells["delivery_dt"].dt.date <= end.date())
            ]

        if profile == "PEAK":
            plant_sells = plant_sells[
                (plant_sells["delivery_dt"].dt.weekday < 5) &
                (plant_sells["delivery_dt"].dt.hour >= 8) &
                (plant_sells["delivery_dt"].dt.hour < 20)
            ]

        total_delivered_mwh = (plant_sells["volume_mw"] * 0.25).sum()

        if date_range:
            n_days = (date_range[1] - date_range[0]).days + 1
        else:
            n_days = min((end - start).days + 1, 90)

        if profile == "BASELOAD":
            periods_per_day = 96
        elif profile == "PEAK":
            weekdays = sum(1 for d in pd.date_range(start, periods=n_days)
                          if d.weekday() < 5)
            periods_per_day = 48
            n_days = weekdays
        elif profile == "SHAPED":
            periods_per_day = 96
        else:
            periods_per_day = 96

        committed_mwh = volume_mw * 0.25 * periods_per_day * n_days

        if committed_mwh > 0:
            pct_deviation = ((total_delivered_mwh - committed_mwh) / committed_mwh) * 100
        else:
            pct_deviation = 0

        within_tolerance = abs(pct_deviation) <= tolerance
        shortfall_mwh = max(0, committed_mwh - total_delivered_mwh)
        penalty_exposure = shortfall_mwh * penalty if not within_tolerance else 0

        results.append({
            "contract_id": contract_id,
            "counterparty": c["counterparty"],
            "plant_id": plant_id,
            "profile": profile,
            "volume_mw": volume_mw,
            "committed_mwh": round(committed_mwh, 0),
            "delivered_mwh": round(total_delivered_mwh, 0),
            "deviation_pct": round(pct_deviation, 1),
            "tolerance_pct": tolerance,
            "within_tolerance": within_tolerance,
            "penalty_exposure_eur": round(penalty_exposure, 0),
        })

    return pd.DataFrame(results)


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
