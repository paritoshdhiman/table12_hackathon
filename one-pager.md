# Use Case 4: Intraday Energy Trading Optimization Agent
### Segment: Power & Utilities | Claude Code + Bedrock AgentCore Hackathon · Energy Symposium

---

## The Problem

European power generators and retailers must continuously optimize their trading positions across intraday electricity markets (EPEX SPOT, Nord Pool) where prices fluctuate every 15 minutes. Since October 2025, all continental European electricity markets trade on quarter-hourly intervals — a 4× increase in decision complexity versus the previous hourly granularity.

A 400 MW Combined Cycle Gas Turbine (CCGT) plant generates approximately €800K–€1.2M in daily revenue. The difference between optimal and suboptimal intraday trading can be 5–12% of revenue — that's €40K–€144K per day left on the table. Across a portfolio of 3–5 plants, the annual opportunity cost of manual trading exceeds €50M.

The core challenge: traders must simultaneously evaluate real-time market prices, plant-specific marginal costs (which vary with load, ambient temperature, and gas price), grid transmission constraints, ramp-rate limitations, start-up costs (hot/warm/cold), contractual obligations (PPAs, balancing group commitments), and REMIT II compliance requirements — all within the 5-minute gate closure window of the continuous intraday market.

Human traders can process 2–3 of these dimensions simultaneously.

## Your Task

**Solve the problem above using Agentic AI — built with Claude Code and deployed on Amazon Bedrock AgentCore.**

Use the dataset and reference documents provided in this package:

- **Market prices** — `market_prices/intraday_prices_epex.csv` (8,640 quarter-hourly periods), `day_ahead_prices.csv`, `imbalance_prices.csv`, `fuel_prices.csv` (TTF gas and EU ETS carbon)
- **Your portfolio** — `plant_portfolio/plant_portfolio.csv` (CCGT, OCGT, wind, solar), `marginal_cost_curves.csv`, `contract_obligations.csv`
- **Forecasts and constraints** — `market_prices/renewable_forecast.csv`, `weather_actuals_forecast.csv`, `grid_constraints/grid_constraints.csv`
- **Position and compliance** — `market_prices/trade_blotter.csv` (2,689 trades), `remit_transactions.csv`
- **Reference documents** (`data/reference_docs/`, `.md` and `.pdf`) — EPEX SPOT market rules (DE-LU), CCGT plant operating manual (Siemens H-class), REMIT II compliance guide, German balancing & imbalance settlement

### What you decide

Everything else. What the application actually does, which question it answers and who it answers it for, how many agents and how they divide the work, which orchestration pattern, what each tool does, which AgentCore modules you use, and what the interface looks like — all of that is your team's call.

There is deliberately no worked solution and no capability checklist in this document. Deciding what is worth building from the problem and the data is the hackathon. Two teams solving this well should end up with two visibly different applications.

### What "grounded" means here

Every number and claim your application states should trace back to a specific file, row, or passage in the data above — and it should be able to say which one. An answer that sounds expert but cites nothing is worth less than a narrower answer that shows its evidence. If the data doesn't support a conclusion, the right behavior is to say so, not to fill the gap.

Judges score the working demo, the depth of the application's reasoning, and whether its claims trace back to this data.

---

## Dataset Provided

**Folder layout** — unlike the other use cases, these files are grouped into subfolders under `data/`:

```
data/
├── market_prices/      intraday_prices_epex.csv, day_ahead_prices.csv, fuel_prices.csv,
│                       imbalance_prices.csv, renewable_forecast.csv,
│                       weather_actuals_forecast.csv, trade_blotter.csv, remit_transactions.csv
├── plant_portfolio/    plant_portfolio.csv, marginal_cost_curves.csv, contract_obligations.csv
├── grid_constraints/   grid_constraints.csv
└── reference_docs/     4 Markdown documents
```

All 12 CSVs cover the same 90-day window. Row counts are given per file below.

### 1. Intraday Market Prices — `market_prices/intraday_prices_epex.csv`
**90 days of 15-minute EPEX SPOT continuous intraday prices for DE-LU bidding zone** — 8,640 quarter-hour periods

| Column | Description | Unit |
|--------|-------------|------|
| `timestamp_utc` | Delivery period start (ISO 8601) | UTC |
| `delivery_start` | Delivery period start (CET/CEST) | Local |
| `delivery_end` | Delivery period end (CET/CEST) | Local |
| `product_type` | `QH` (quarter-hour), `HH` (half-hour), `H` (hour) | — |
| `vwap_eur_mwh` | Volume-weighted average price | €/MWh |
| `high_eur_mwh` | Highest traded price in period | €/MWh |
| `low_eur_mwh` | Lowest traded price in period | €/MWh |
| `last_eur_mwh` | Last traded price before gate closure | €/MWh |
| `volume_mwh` | Total traded volume | MWh |
| `num_trades` | Number of individual trades | count |
| `id3_index_eur_mwh` | ID3 index (average of last 3 hours of trading) | €/MWh |
| `day_ahead_price_eur_mwh` | Corresponding day-ahead auction price | €/MWh |
| `spread_id_vs_da_eur_mwh` | Intraday vs day-ahead spread | €/MWh |

Price characteristics: Mean ~€72/MWh, std dev ~€35/MWh, occasional negative prices (high wind/solar), spikes to €200+ (low wind + cold snap), realistic autocorrelation structure.

### 2. Day-Ahead Auction Results — `market_prices/day_ahead_prices.csv`
**90 days of hourly day-ahead prices (EPEX SPOT DE-LU)** — 2,160 rows

| Column | Description | Unit |
|--------|-------------|------|
| `delivery_date` | Delivery date | YYYY-MM-DD |
| `delivery_hour` | Hour of delivery (0–23) | CET |
| `price_eur_mwh` | Market clearing price | €/MWh |
| `volume_buy_mwh` | Total accepted buy volume | MWh |
| `volume_sell_mwh` | Total accepted sell volume | MWh |
| `net_position_mwh` | Net cross-border flow | MWh |

### 3. Plant Portfolio — `plant_portfolio/plant_portfolio.csv`
**Fleet of 4 generation assets (realistic European utility portfolio)** — 4 rows, 20 columns. `plant_id` values: `RHEIN_CCGT`, `NORDSEE_WIND`, `BAYERN_SOLAR`, `ISAR_OCGT`

| Column | Description |
|--------|-------------|
| `plant_id` | Unique identifier |
| `plant_name` | Human-readable name |
| `technology` | CCGT / OCGT / Wind / Solar |
| `capacity_mw` | Nameplate capacity |
| `min_stable_load_mw` | Minimum stable generation |
| `max_ramp_up_mw_min` | Maximum ramp-up rate |
| `max_ramp_down_mw_min` | Maximum ramp-down rate |
| `heat_rate_btu_kwh` | Full-load heat rate (thermal only) |
| `efficiency_pct` | Net electrical efficiency |
| `start_cost_hot_eur` | Hot start cost (<8h offline) |
| `start_cost_warm_eur` | Warm start cost (8–48h offline) |
| `start_cost_cold_eur` | Cold start cost (>48h offline) |
| `start_time_hot_min` | Hot start time to min stable load |
| `start_time_warm_min` | Warm start time |
| `start_time_cold_min` | Cold start time |
| `min_run_time_hrs` | Minimum run time once started |
| `min_down_time_hrs` | Minimum down time after shutdown |
| `co2_intensity_tco2_mwh` | CO2 emission factor |
| `variable_om_eur_mwh` | Variable O&M cost |
| `location_bidding_zone` | EPEX bidding zone |

**Plant details:**
- **Rheinhafen CCGT** — 430 MW, 58% efficiency, €45K hot start, 20 MW/min ramp
- **Nordsee Wind Farm** — 350 MW nameplate, zero marginal cost, variable output
- **Bayern Solar Park** — 120 MW nameplate, zero marginal cost, daylight only
- **Isar Peaker OCGT** — 180 MW, 37% efficiency, €15K hot start, 30 MW/min ramp (fast response)

### 4. Plant Marginal Cost Curves — `plant_portfolio/marginal_cost_curves.csv`
**Load-dependent marginal cost for each thermal plant (10 MW increments)** — 37 rows, covering the two thermal plants only (`RHEIN_CCGT`, `ISAR_OCGT`). Wind and solar have zero marginal cost, so they have no curve

| Column | Description | Unit |
|--------|-------------|------|
| `plant_id` | Plant identifier | — |
| `load_mw` | Operating load point | MW |
| `marginal_cost_eur_mwh` | Marginal cost at this load | €/MWh |
| `heat_rate_at_load_btu_kwh` | Heat rate at part-load | Btu/kWh |
| `efficiency_at_load_pct` | Efficiency at part-load | % |
| `co2_cost_eur_mwh` | CO2 cost component (ETS price × intensity) | €/MWh |
| `gas_cost_eur_mwh` | Gas cost component | €/MWh |
| `vom_eur_mwh` | Variable O&M component | €/MWh |

Marginal cost formula: `MC = (Gas_Price / Efficiency) + (CO2_Price × CO2_Intensity) + VOM`
- Gas price: TTF front-month (varies daily, ~€32/MWh thermal in dataset)
- CO2 price: EU ETS (varies daily, ~€65/tCO2 in dataset)
- Part-load penalty: efficiency drops 3–8% below 60% load

### 5. Gas & Carbon Prices — `market_prices/fuel_prices.csv`
**90 days of daily TTF gas and EU ETS carbon prices** — 90 rows

| Column | Description | Unit |
|--------|-------------|------|
| `date` | Trading date | YYYY-MM-DD |
| `ttf_front_month_eur_mwh` | TTF natural gas front-month | €/MWh (thermal) |
| `ttf_spot_eur_mwh` | TTF day-ahead gas price | €/MWh (thermal) |
| `eu_ets_eur_tco2` | EU ETS carbon allowance price | €/tCO2 |
| `coal_api2_usd_t` | API2 coal price (reference) | $/tonne |
| `brent_usd_bbl` | Brent crude (reference) | $/barrel |

### 6. Renewable Forecast — `market_prices/renewable_forecast.csv`
**15-minute wind and solar generation forecasts (48h rolling)** — 8,640 rows

| Column | Description | Unit |
|--------|-------------|------|
| `timestamp_utc` | Forecast period start | UTC |
| `forecast_horizon_hrs` | Hours ahead of delivery | hours |
| `wind_forecast_mw` | Expected wind generation | MW |
| `wind_p10_mw` | 10th percentile (low wind scenario) | MW |
| `wind_p90_mw` | 90th percentile (high wind scenario) | MW |
| `solar_forecast_mw` | Expected solar generation | MW |
| `solar_p10_mw` | 10th percentile | MW |
| `solar_p90_mw` | 90th percentile | MW |
| `total_renewable_mw` | Combined forecast | MW |
| `forecast_error_mw` | Actual minus forecast (backfilled) | MW |

### 7. Grid Constraints — `grid_constraints/grid_constraints.csv`
**Transmission capacity limits and congestion indicators** — 12,960 rows (multiple interconnector zone-pairs per period)

| Column | Description | Unit |
|--------|-------------|------|
| `timestamp_utc` | Period start | UTC |
| `from_zone` | Source bidding zone | — |
| `to_zone` | Destination bidding zone | — |
| `atc_mw` | Available Transfer Capacity | MW |
| `ntc_mw` | Net Transfer Capacity | MW |
| `scheduled_flow_mw` | Scheduled commercial flow | MW |
| `congestion_rent_eur_mwh` | Congestion rent (price spread) | €/MWh |
| `redispatch_volume_mw` | Redispatch activated | MW |
| `curtailment_mw` | Renewable curtailment | MW |

### 8. Trading Positions & Blotter — `market_prices/trade_blotter.csv`
**Historical trade execution log (90 days)** — 2,689 trades. `plant_id` is blank on BUY-side trades that are not backed by a specific asset

| Column | Description | Unit |
|--------|-------------|------|
| `trade_id` | Unique trade identifier | — |
| `timestamp_executed` | Execution timestamp | UTC |
| `delivery_start` | Delivery period start | CET |
| `delivery_end` | Delivery period end | CET |
| `direction` | `BUY` or `SELL` | — |
| `volume_mw` | Traded volume | MW |
| `price_eur_mwh` | Execution price | €/MWh |
| `plant_id` | Dispatched plant (if sell) | — |
| `strategy` | `DA_HEDGE` / `ID_OPTIM` / `BALANCING` / `SPREAD` | — |
| `pnl_eur` | Realized P&L vs day-ahead | € |
| `trader_id` | Trader who executed | — |
| `order_type` | `LIMIT` / `MARKET` / `ICEBERG` | — |
| `remit_reported` | REMIT transaction reported | boolean |

### 9. Imbalance Settlement — `market_prices/imbalance_prices.csv`
**15-minute imbalance settlement prices (TSO balancing)** — 8,640 rows

| Column | Description | Unit |
|--------|-------------|------|
| `timestamp_utc` | Settlement period start | UTC |
| `imbalance_price_long_eur_mwh` | Price for long positions (over-generation) | €/MWh |
| `imbalance_price_short_eur_mwh` | Price for short positions (under-generation) | €/MWh |
| `system_balance_mw` | Net system imbalance | MW |
| `regulation_state` | `LONG` / `SHORT` / `BALANCED` | — |
| `activated_reserves_mw` | Balancing energy activated | MW |
| `reserve_type` | `aFRR` / `mFRR` / `RR` | — |

### 10. Contract Obligations — `plant_portfolio/contract_obligations.csv`
**PPA and bilateral contract commitments** — 6 contracts across the 4 plants

| Column | Description | Unit |
|--------|-------------|------|
| `contract_id` | Contract identifier | — |
| `counterparty` | Buyer/seller name | — |
| `contract_type` | `PPA_FIXED` / `PPA_INDEXED` / `BASELOAD` / `PEAKLOAD` / `SHAPED` | — |
| `start_date` | Contract start | YYYY-MM-DD |
| `end_date` | Contract end | YYYY-MM-DD |
| `volume_mw` | Contracted volume | MW |
| `price_eur_mwh` | Contract price (fixed) or index formula | €/MWh |
| `delivery_profile` | `BASELOAD` (24/7) / `PEAK` (8–20 weekdays) / `OFFPEAK` / `SHAPED` | — |
| `tolerance_pct` | Volume tolerance band (±%) | % |
| `penalty_eur_mwh` | Under-delivery penalty | €/MWh |
| `plant_id` | Assigned generation source | — |

### 11. Weather Data — `market_prices/weather_actuals_forecast.csv`
**Hourly weather observations and 48h forecasts for plant locations** — 8,640 rows: 4 locations (`Karlsruhe_CCGT`, `Nordsee_Wind`, `Augsburg_Solar`, `Landshut_OCGT`) × 2,160 hourly periods. Ambient temperature drives the CCGT efficiency correction below

| Column | Description | Unit |
|--------|-------------|------|
| `timestamp_utc` | Observation/forecast time | UTC |
| `location` | Plant location identifier | — |
| `temperature_c` | Ambient temperature | °C |
| `wind_speed_ms` | Wind speed at hub height | m/s |
| `wind_direction_deg` | Wind direction | degrees |
| `solar_irradiance_wm2` | Global horizontal irradiance | W/m² |
| `cloud_cover_pct` | Cloud cover | % |
| `humidity_pct` | Relative humidity | % |
| `pressure_hpa` | Atmospheric pressure | hPa |
| `is_forecast` | Actual observation or forecast | boolean |
| `forecast_source` | `ECMWF` / `GFS` / `ACTUAL` | — |

### 12. REMIT Compliance Log — `market_prices/remit_transactions.csv`
**REMIT II transaction reporting records** — 2,554 rows, linked to the blotter on `trade_id`

| Column | Description | Unit |
|--------|-------------|------|
| `report_id` | ACER transaction report ID | — |
| `trade_id` | Linked trade from blotter | — |
| `reporting_entity` | Market participant ID (ACER code) | — |
| `transaction_type` | `STANDARD_SUPPLY` / `TRANSPORTATION` / `DERIVATIVE` | — |
| `contract_type` | `CONT` (continuous) / `AUCT` (auction) | — |
| `delivery_point` | Bidding zone | — |
| `submission_timestamp` | When reported to ACER | UTC |
| `reporting_deadline` | T+1 business day deadline | UTC |
| `status` | `SUBMITTED` / `ACCEPTED` / `REJECTED` / `PENDING` | — |
| `rejection_reason` | If rejected, ACER error code | — |

### 13. Reference Documents — `reference_docs/`

Four documents, supplied as Markdown (this use case has no PDF versions — the Markdown is the source of truth):

| File | Contents |
|---|---|
| `epex_spot_market_rules.md` | EPEX SPOT intraday continuous market rules for DE-LU — quarter-hourly products, gate closure, order types, tick sizes |
| `ccgt_plant_operating_manual.md` | Rheinhafen CCGT operating manual (Siemens SGT5-8000H + SST5-5000) — start sequences, ramp limits, part-load behaviour, ambient corrections |
| `remit_compliance_guide.md` | REMIT II compliance for algorithmic trading (EU 2024/1106) — reporting obligations, inside information, manipulation controls |
| `balancing_imbalance_settlement.md` | German balancing framework — aFRR/mFRR/RR, imbalance pricing, BRP obligations |

These are where the market rules and the plant's operating limits are written down.

---

## Key Domain Formulas & Constants

### Short-Run Marginal Cost (SRMC)
```
SRMC (€/MWh) = Gas_Price_€/MWh_th / Efficiency + CO2_Price_€/tCO2 × CO2_Intensity_tCO2/MWh + VOM_€/MWh
```

### CCGT Efficiency at Part-Load (Willans Line Approximation)
```
η(P) = η_max × (1 - k × (1 - P/P_max)²)
where k ≈ 0.15 for modern CCGT, P = current load, P_max = nameplate capacity
```

### Spread Calculation
```
Clean Spark Spread = Power_Price - (Gas_Price / Efficiency) - (CO2_Price × CO2_Intensity)
Clean Dark Spread = Power_Price - (Coal_Price / Efficiency) - (CO2_Price × CO2_Intensity)
```

### Imbalance Risk Cost
```
Expected_Imbalance_Cost = P(short) × E[Imbalance_Price_Short - Market_Price] × Volume
                        + P(long) × E[Market_Price - Imbalance_Price_Long] × Volume
```

### Ramp Constraint
```
|P(t+1) - P(t)| ≤ Ramp_Rate_MW/min × Δt_minutes
P_min ≤ P(t) ≤ P_max (when unit is online)
```

### Start-Up Cost Decision
```
Start_Justified = Expected_Margin × Run_Hours > Start_Cost + Min_Run_Time × VOM
where Expected_Margin = E[Price] - SRMC at expected load
```

### Physical Constants Used
- Gas HHV: 39.0 MJ/m³ (Groningen-quality natural gas)
- Gas LHV: 35.2 MJ/m³
- CO2 emission factor (gas): 0.202 tCO2/MWh_th (IPCC 2006)
- CO2 emission factor (coal): 0.341 tCO2/MWh_th
- 1 MWh = 3.412 MMBtu = 3,600 MJ
- Standard atmospheric pressure: 1013.25 hPa
- CCGT efficiency correction: -0.5% per °C above 15°C ISO conditions

---

## Regulatory & Compliance Context

### REMIT II (EU Regulation 2024/1106)
- All wholesale energy transactions must be reported to ACER within T+1 business day
- Market participants must have systems to detect and prevent market manipulation
- Inside information must be disclosed via REMIT platforms before trading
- Algorithmic trading strategies must be documented and auditable
- Penalties: up to €500K per violation or 10× the profit gained

### EU ETS (Emissions Trading System)
- Each MWh of gas-fired generation requires surrender of CO2 allowances
- Current Phase IV (2021–2030): declining cap, prices €60–€80/tCO2
- Free allocation being phased out for power sector

### Electricity Balancing Guideline (EB GL)
- Balance Responsible Parties (BRPs) must minimize imbalances
- Imbalance settlement uses single pricing (marginal balancing energy cost)
- Platforms: PICASSO (aFRR), MARI (mFRR), TERRE (RR)

---

> **Logging in, environment setup, and how to submit:** see the hackathon portal.
>
> **Claude Code:** [https://docs.claude.com/en/docs/claude-code](https://docs.claude.com/en/docs/claude-code)
> **Strands Agents SDK:** [https://strandsagents.com](https://strandsagents.com)
> **Amazon Bedrock AgentCore:** [https://docs.aws.amazon.com/bedrock-agentcore/](https://docs.aws.amazon.com/bedrock-agentcore/)
