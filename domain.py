import pandas as pd
import numpy as np


def compute_srmc(gas_price: float, efficiency: float, co2_price: float,
                 co2_intensity: float, vom: float) -> float:
    """SRMC = Gas_Price / Efficiency + CO2_Price * CO2_Intensity + VOM"""
    return gas_price / efficiency + co2_price * co2_intensity + vom


def part_load_efficiency(eta_max: float, load: float, p_max: float, k: float = 0.15) -> float:
    """Willans line: eta(P) = eta_max * (1 - k * (1 - P/P_max)^2)"""
    return eta_max * (1 - k * (1 - load / p_max) ** 2)


def temp_corrected_efficiency(eta: float, temp_c: float) -> float:
    """-0.5% per C above 15C ISO conditions."""
    if temp_c > 15:
        return eta * (1 - 0.005 * (temp_c - 15))
    return eta


def temp_corrected_capacity(p_max: float, temp_c: float) -> float:
    """-0.7% per C above 15C ISO conditions."""
    if temp_c > 15:
        return p_max * (1 - 0.007 * (temp_c - 15))
    return p_max


def clean_spark_spread(power_price: float, gas_price: float,
                       efficiency: float, co2_price: float,
                       co2_intensity: float) -> float:
    """CSS = Power_Price - Gas_Price/Efficiency - CO2_Price * CO2_Intensity"""
    return power_price - gas_price / efficiency - co2_price * co2_intensity


def get_start_type(hours_offline: float) -> str:
    """Hot: <8h, Warm: 8-48h, Cold: >48h"""
    if hours_offline < 8:
        return "hot"
    elif hours_offline <= 48:
        return "warm"
    return "cold"


def get_start_cost(plant_row: pd.Series, hours_offline: float) -> float:
    st = get_start_type(hours_offline)
    return plant_row[f"start_cost_{st}_eur"]


def start_justified(expected_margin: float, run_hours: float,
                    start_cost: float, min_run_time: float, vom: float) -> bool:
    """Start justified if Expected_Margin * Run_Hours > Start_Cost + Min_Run_Time * VOM"""
    return expected_margin * run_hours > start_cost + min_run_time * vom


def compute_srmc_at_load(plant_id: str, load_mw: float, gas_price: float,
                         co2_price: float, plants_df: pd.DataFrame,
                         temp_c: float = 15.0) -> float:
    """Compute SRMC for a thermal plant at a specific load and temperature."""
    plant = plants_df[plants_df["plant_id"] == plant_id].iloc[0]
    p_max = plant["capacity_mw"]
    eta_max = plant["efficiency_pct"] / 100.0
    co2_i = plant["co2_intensity_tco2_mwh"]
    vom = plant["variable_om_eur_mwh"]

    eta = part_load_efficiency(eta_max, load_mw, p_max)
    eta = temp_corrected_efficiency(eta, temp_c)

    return compute_srmc(gas_price, eta, co2_price, co2_i, vom)


def build_merit_order(gas_price: float, co2_price: float,
                      plants_df: pd.DataFrame, temp_c: float = 15.0) -> list[dict]:
    """Build merit order for thermal plants at full load."""
    thermals = plants_df[plants_df["technology"].isin(["CCGT", "OCGT"])]
    order = []
    for _, p in thermals.iterrows():
        srmc = compute_srmc_at_load(p["plant_id"], p["capacity_mw"],
                                    gas_price, co2_price, plants_df, temp_c)
        order.append({
            "plant_id": p["plant_id"],
            "technology": p["technology"],
            "capacity_mw": p["capacity_mw"],
            "min_stable_load_mw": p["min_stable_load_mw"],
            "srmc_eur_mwh": round(srmc, 2),
        })
    order.sort(key=lambda x: x["srmc_eur_mwh"])
    return order
