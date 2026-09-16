import os
import zipfile
import streamlit as st
import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
ZIP_PATH = os.path.join(os.path.dirname(__file__), "Files", "use-case-4-data.zip")


def extract_data_if_needed():
    if not os.path.isdir(os.path.join(DATA_DIR, "market_prices")):
        with zipfile.ZipFile(ZIP_PATH, "r") as z:
            z.extractall(os.path.dirname(__file__))


@st.cache_data
def load_intraday_prices() -> pd.DataFrame:
    path = os.path.join(DATA_DIR, "market_prices", "intraday_prices_epex.csv")
    df = pd.read_csv(path, parse_dates=["timestamp_utc"])
    df["date"] = pd.to_datetime(df["delivery_start"]).dt.date
    df["hour"] = pd.to_datetime(df["delivery_start"]).dt.hour
    df["quarter"] = pd.to_datetime(df["delivery_start"]).dt.minute // 15
    df.attrs["source_file"] = "data/market_prices/intraday_prices_epex.csv"
    return df


@st.cache_data
def load_day_ahead_prices() -> pd.DataFrame:
    path = os.path.join(DATA_DIR, "market_prices", "day_ahead_prices.csv")
    df = pd.read_csv(path)
    df["timestamp"] = pd.to_datetime(df["delivery_date"]) + pd.to_timedelta(df["delivery_hour"], unit="h")
    df.attrs["source_file"] = "data/market_prices/day_ahead_prices.csv"
    return df


@st.cache_data
def load_plant_portfolio() -> pd.DataFrame:
    path = os.path.join(DATA_DIR, "plant_portfolio", "plant_portfolio.csv")
    df = pd.read_csv(path)
    df.attrs["source_file"] = "data/plant_portfolio/plant_portfolio.csv"
    return df


@st.cache_data
def load_marginal_cost_curves() -> pd.DataFrame:
    path = os.path.join(DATA_DIR, "plant_portfolio", "marginal_cost_curves.csv")
    df = pd.read_csv(path)
    df.attrs["source_file"] = "data/plant_portfolio/marginal_cost_curves.csv"
    return df


@st.cache_data
def load_contract_obligations() -> pd.DataFrame:
    path = os.path.join(DATA_DIR, "plant_portfolio", "contract_obligations.csv")
    df = pd.read_csv(path, parse_dates=["start_date", "end_date"])
    df.attrs["source_file"] = "data/plant_portfolio/contract_obligations.csv"
    return df


@st.cache_data
def load_fuel_prices() -> pd.DataFrame:
    path = os.path.join(DATA_DIR, "market_prices", "fuel_prices.csv")
    df = pd.read_csv(path, parse_dates=["date"])
    df.attrs["source_file"] = "data/market_prices/fuel_prices.csv"
    return df


@st.cache_data
def load_renewable_forecast() -> pd.DataFrame:
    path = os.path.join(DATA_DIR, "market_prices", "renewable_forecast.csv")
    df = pd.read_csv(path, parse_dates=["timestamp_utc"])
    df.attrs["source_file"] = "data/market_prices/renewable_forecast.csv"
    return df


@st.cache_data
def load_imbalance_prices() -> pd.DataFrame:
    path = os.path.join(DATA_DIR, "market_prices", "imbalance_prices.csv")
    df = pd.read_csv(path, parse_dates=["timestamp_utc"])
    df.attrs["source_file"] = "data/market_prices/imbalance_prices.csv"
    return df


@st.cache_data
def load_trade_blotter() -> pd.DataFrame:
    path = os.path.join(DATA_DIR, "market_prices", "trade_blotter.csv")
    df = pd.read_csv(path, parse_dates=["timestamp_executed"])
    df["delivery_date"] = pd.to_datetime(df["delivery_start"]).dt.date
    df.attrs["source_file"] = "data/market_prices/trade_blotter.csv"
    return df


@st.cache_data
def load_grid_constraints() -> pd.DataFrame:
    path = os.path.join(DATA_DIR, "grid_constraints", "grid_constraints.csv")
    df = pd.read_csv(path, parse_dates=["timestamp_utc"])
    df.attrs["source_file"] = "data/grid_constraints/grid_constraints.csv"
    return df


@st.cache_data
def load_weather() -> pd.DataFrame:
    path = os.path.join(DATA_DIR, "market_prices", "weather_actuals_forecast.csv")
    df = pd.read_csv(path, parse_dates=["timestamp_utc"])
    df.attrs["source_file"] = "data/market_prices/weather_actuals_forecast.csv"
    return df


@st.cache_data
def load_remit_transactions() -> pd.DataFrame:
    path = os.path.join(DATA_DIR, "market_prices", "remit_transactions.csv")
    df = pd.read_csv(path, parse_dates=["submission_timestamp", "reporting_deadline"])
    df.attrs["source_file"] = "data/market_prices/remit_transactions.csv"
    return df


def load_reference_doc(name: str) -> str:
    path = os.path.join(DATA_DIR, "reference_docs", name)
    with open(path, "r") as f:
        return f.read()
