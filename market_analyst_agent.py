#!/usr/bin/env python3
"""Market Analyst Agent — an interactive CLI agent that answers questions
about the intraday energy market dataset using Claude on Bedrock with tool use."""

import json
import os
import sys

import anthropic
import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

MODEL_ID = "us.anthropic.claude-sonnet-4-20250514-v1:0"

TOOLS = [
    {
        "name": "query_intraday_prices",
        "description": (
            "Load the EPEX SPOT intraday continuous market prices (15-min intervals, "
            "8640 rows over 90 days). Returns summary statistics and the first 5 rows. "
            "Optionally filter by date range."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "start_date": {
                    "type": "string",
                    "description": "Optional start date filter (YYYY-MM-DD)",
                },
                "end_date": {
                    "type": "string",
                    "description": "Optional end date filter (YYYY-MM-DD)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "query_day_ahead_prices",
        "description": (
            "Load the day-ahead auction prices (hourly, 2160 rows over 90 days). "
            "Returns summary statistics and the first 5 rows. "
            "Optionally filter by date range."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "start_date": {"type": "string", "description": "Optional start date (YYYY-MM-DD)"},
                "end_date": {"type": "string", "description": "Optional end date (YYYY-MM-DD)"},
            },
            "required": [],
        },
    },
    {
        "name": "query_fuel_prices",
        "description": (
            "Load daily TTF gas and EU ETS carbon prices (90 rows). "
            "Returns summary statistics and the first 5 rows. "
            "Optionally filter by date range."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "start_date": {"type": "string", "description": "Optional start date (YYYY-MM-DD)"},
                "end_date": {"type": "string", "description": "Optional end date (YYYY-MM-DD)"},
            },
            "required": [],
        },
    },
    {
        "name": "query_renewable_forecast",
        "description": (
            "Load 15-minute wind and solar generation forecasts (8640 rows). "
            "Returns summary statistics and the first 5 rows. "
            "Optionally filter by date range."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "start_date": {"type": "string", "description": "Optional start date (YYYY-MM-DD)"},
                "end_date": {"type": "string", "description": "Optional end date (YYYY-MM-DD)"},
            },
            "required": [],
        },
    },
    {
        "name": "query_imbalance_prices",
        "description": (
            "Load 15-minute imbalance settlement prices from the TSO (8640 rows). "
            "Returns summary statistics and the first 5 rows. "
            "Optionally filter by date range."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "start_date": {"type": "string", "description": "Optional start date (YYYY-MM-DD)"},
                "end_date": {"type": "string", "description": "Optional end date (YYYY-MM-DD)"},
            },
            "required": [],
        },
    },
    {
        "name": "query_weather",
        "description": (
            "Load hourly weather observations and forecasts for plant locations "
            "(8640 rows, 4 locations). Returns summary statistics and the first 5 rows. "
            "Optionally filter by date range and/or location."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "start_date": {"type": "string", "description": "Optional start date (YYYY-MM-DD)"},
                "end_date": {"type": "string", "description": "Optional end date (YYYY-MM-DD)"},
                "location": {
                    "type": "string",
                    "description": "Optional location filter: Karlsruhe_CCGT, Nordsee_Wind, Augsburg_Solar, or Landshut_OCGT",
                },
            },
            "required": [],
        },
    },
]

SYSTEM_PROMPT = """\
You are a Market Analyst Agent for a European power utility's intraday trading desk.
You have access to 90 days of market data for the DE-LU bidding zone (EPEX SPOT).

When answering questions:
1. Use the tools to load the relevant datasets.
2. Always show the **first 5 rows** of every table you reference (the tool output includes them).
3. Ground every claim in specific data — cite numbers, dates, and column names.
4. If the data doesn't support a conclusion, say so.
5. Keep analysis concise and actionable for a trader.

Available datasets:
- Intraday prices (15-min VWAP, highs, lows, spreads vs day-ahead)
- Day-ahead auction prices (hourly)
- Fuel prices (TTF gas, EU ETS carbon, coal, Brent)
- Renewable forecasts (wind + solar with P10/P90 bands)
- Imbalance prices (long/short settlement, system balance)
- Weather (temperature, wind speed, solar irradiance per plant location)
"""


def _load_and_format(filepath: str, date_col: str, start_date: str = None,
                     end_date: str = None, extra_filter: dict = None) -> str:
    df = pd.read_csv(filepath)

    if date_col in df.columns:
        df[date_col] = pd.to_datetime(df[date_col], utc=True)
        if start_date:
            df = df[df[date_col] >= pd.Timestamp(start_date, tz="UTC")]
        if end_date:
            df = df[df[date_col] <= pd.Timestamp(end_date, tz="UTC")]

    if extra_filter:
        for col, val in extra_filter.items():
            if col in df.columns:
                df = df[df[col] == val]

    head = df.head(5).to_string(index=False)
    stats = df.describe(include="all").to_string()
    shape = f"Shape: {df.shape[0]} rows x {df.shape[1]} columns"
    cols = f"Columns: {', '.join(df.columns.tolist())}"
    date_range = ""
    if date_col in df.columns:
        date_range = f"Date range: {df[date_col].min()} to {df[date_col].max()}"

    return f"{shape}\n{cols}\n{date_range}\n\n--- First 5 Rows ---\n{head}\n\n--- Summary Statistics ---\n{stats}"


def execute_tool(name: str, inputs: dict) -> str:
    start = inputs.get("start_date")
    end = inputs.get("end_date")

    if name == "query_intraday_prices":
        return _load_and_format(
            os.path.join(DATA_DIR, "market_prices", "intraday_prices_epex.csv"),
            "timestamp_utc", start, end,
        )
    elif name == "query_day_ahead_prices":
        return _load_and_format(
            os.path.join(DATA_DIR, "market_prices", "day_ahead_prices.csv"),
            "delivery_date", start, end,
        )
    elif name == "query_fuel_prices":
        return _load_and_format(
            os.path.join(DATA_DIR, "market_prices", "fuel_prices.csv"),
            "date", start, end,
        )
    elif name == "query_renewable_forecast":
        return _load_and_format(
            os.path.join(DATA_DIR, "market_prices", "renewable_forecast.csv"),
            "timestamp_utc", start, end,
        )
    elif name == "query_imbalance_prices":
        return _load_and_format(
            os.path.join(DATA_DIR, "market_prices", "imbalance_prices.csv"),
            "timestamp_utc", start, end,
        )
    elif name == "query_weather":
        extra = {}
        if inputs.get("location"):
            extra["location"] = inputs["location"]
        return _load_and_format(
            os.path.join(DATA_DIR, "market_prices", "weather_actuals_forecast.csv"),
            "timestamp_utc", start, end, extra,
        )
    return "Unknown tool"


def run_agent(user_question: str) -> str:
    client = anthropic.AnthropicBedrock(aws_region=os.environ.get("AWS_REGION", "us-east-1"))

    messages = [{"role": "user", "content": user_question}]

    print(f"\n{'='*60}")
    print(f"Question: {user_question}")
    print(f"{'='*60}\n")

    while True:
        response = client.messages.create(
            model=MODEL_ID,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    print(f"  [Tool Call] {block.name}({json.dumps(block.input)})")
                    result = execute_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

        else:
            final_text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    final_text += block.text
            return final_text


def main():
    print("=" * 60)
    print("  Market Analyst Agent — Intraday Energy Trading")
    print("  Type 'quit' to exit")
    print("=" * 60)

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
            answer = run_agent(question)
            print(f"\nAnalyst:\n{answer}\n")
        except Exception as e:
            print(f"\nError: {e}\n")


if __name__ == "__main__":
    main()
