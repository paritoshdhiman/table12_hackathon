# DELTA User Guide

**Dynamic Energy Load & Trading Analytics**
Intraday trading optimization dashboard for a 4-plant German utility portfolio on EPEX SPOT (DE-LU bidding zone).

---

## Getting Started

```bash
pip install -r requirements.txt
streamlit run app.py
```

Open the app in your browser (default: `http://localhost:8501`). Use the sidebar to navigate between pages.

Pages 0-5 work immediately with the included 90-day dataset. The AI Chat page (page 6) requires AWS credentials for Amazon Bedrock AgentCore.

---

## Pages

### Home

The landing page shows a real-time snapshot of portfolio health.

**What you see:**
- **5 KPI cards** -- Portfolio P&L, Latest VWAP, TTF Gas price, REMIT Compliance rate, Data Coverage
- **2 Critical Findings** -- CCGT Overcommitment Risk (contracts exceed plant capacity) and REMIT Compliance Gap (unreported trades with penalty exposure)
- **Architecture overview** -- describes the 5-agent system and analytical capabilities

No interaction needed -- this page loads automatically from the underlying data.

---

### AI Daily Briefing

Generates a comprehensive AI-style trading briefing for any day in the 90-day window.

**How to use:**
1. **Select a date** using the date picker
2. Click **"Generate AI Briefing"**

**What you get:**
- Price profile chart (Intraday VWAP vs Day-Ahead with CCGT/OCGT SRMC reference lines)
- 5 market metrics (Avg VWAP, Peak Price, Min Price, Volatility, Volume)
- 6 insight cards:
  - **Spread Opportunity** -- intraday vs day-ahead arbitrage signals
  - **Dispatch Economics** -- Clean Spark Spread and profitable dispatch periods
  - **Renewable Output** -- wind/solar generation and forecast error
  - **Price Extremes** -- negative price and spike periods
  - **Trading Performance** -- trade count, P&L, win rate, best trade
  - **Imbalance Risk** -- system regulation state and penalty spread
- **Temperature Impact** warning when CCGT efficiency is derated
- **Recommended Actions** -- numbered list of specific trading decisions

Every insight cites its source file and formula.

---

### Portfolio Overview

Static view of the full plant fleet and 90-day trading performance.

**What you see:**
- **Plant fleet cards** -- 4 plants with capacity, technology, efficiency, and minimum stable load
- **90-day KPIs** -- Total P&L, Average Clean Spark Spread, REMIT Compliance Rate, Total Traded Volume
- **P&L by Strategy** -- bar chart breaking down profits across DA_HEDGE, ID_OPTIM, BALANCING, and SPREAD strategies
- **Trade Count** -- grouped bar showing BUY vs SELL trades per strategy
- **Cumulative P&L** -- line chart showing portfolio equity curve over time
- **Contract Obligations** -- table of all 6 active contracts with volume, price, tolerance, and penalties
- **CCGT Overcommitment Warning** -- flags when peak-hour contracts exceed 430 MW capacity
- **Fuel & Carbon Summary** -- average TTF gas, EU ETS carbon, and intraday VWAP with 90-day ranges

---

### Market Analysis

Deep dive into electricity prices, fuel markets, and renewable forecasts.

**How to use:**
1. **Set the date range** with Start Date and End Date pickers
2. **Switch between 5 tabs:**

| Tab | What it shows |
|-----|---------------|
| **Prices** | Intraday VWAP vs Day-Ahead with high/low band, 4 summary metrics |
| **Spreads** | Intraday-DA spread histogram and daily average spread bar chart |
| **Fuel & Carbon** | TTF Gas and EU ETS Carbon dual-axis time series over 90 days |
| **Renewables** | Wind or Solar forecast with P10/P90 confidence bands, forecast error distribution. Toggle between Wind and Solar with the radio button |
| **Distribution** | VWAP box plot by hour-of-day and price heatmap (hour x day-of-week) |

---

### Plant Dispatch

Runs the merit-order dispatch optimizer for a selected day.

**How to use:**
1. **Select a date** using the date picker
2. Click **"Optimize Dispatch"**

**What you get:**
- **4 summary metrics** -- Total Generation (MWh), Revenue, Cost, and Margin
- **Dispatch schedule** -- stacked area chart showing each plant's generation across 96 quarter-hourly periods, overlaid with the market price
- **Profit waterfall** -- waterfall chart showing each plant's margin contribution
- **Merit-order stack** -- step chart ranking plants by marginal cost (cheapest dispatched first)
- **Marginal cost curves** -- CCGT and OCGT cost at varying load levels, showing part-load efficiency impact
- **Per-plant summary table** -- generation, revenue, cost, margin, and capacity factor per plant
- **Expandable detailed dispatch table** -- every 15-minute period with source citations

The optimizer uses Willans-line part-load efficiency, temperature-corrected capacity derating, and respects minimum stable load, ramp rates, and contract obligations.

---

### Scenario Simulator

What-if analysis comparing base case dispatch against modified market conditions.

**How to use:**
1. **Select a date** using the date picker
2. **Adjust sidebar sliders:**
   - **Gas Price** (EUR/MWh) -- shifts CCGT and OCGT SRMC
   - **Carbon Price** (EUR/tCO2) -- impacts CO2 cost component
   - **Wind Capacity Factor** -- scales wind output (1.0 = actual forecast)
   - **Solar Capacity Factor** -- scales solar output
   - **Demand / Obligation Factor** -- scales contract obligations up or down
3. Click **"Run Scenario Comparison"**

**What you get:**
- **4 delta metrics** -- Generation, Revenue, Cost, Margin with change vs base case
- **Side-by-side dispatch charts** -- stacked area showing how the generation mix shifts
- **Per-plant comparison table** -- base vs scenario generation and margin for each plant
- **Textual analysis** -- explains what each parameter change means for dispatch economics
- **Sensitivity heatmap** -- 5x5 grid of Gas x Carbon prices showing portfolio margin across 25 dispatch optimizations

---

### Compliance & Risk

Monitors regulatory compliance and portfolio risk exposure across 4 tabs.

**Tab 1: REMIT Compliance**
- Compliance Rate, Missing Reports, Rejected, Pending metrics
- REMIT report status pie chart
- Reporting summary with trade counts
- Rejected REMIT reports table with rejection reasons
- Expandable list of trades missing REMIT reports

**Tab 2: Contract Obligations**
- Per-contract cards showing Committed vs Delivered MWh and deviation percentage
- Tolerance breach warnings with penalty exposure in EUR
- Committed vs Delivered grouped bar chart
- CCGT overcommitment warning with shortfall calculation

**Tab 3: Imbalance Exposure**
- Average Long/Short/Spread prices
- System regulation state pie chart (SHORT/LONG/BALANCED)
- Imbalance price spread histogram
- Imbalance settlement prices time series
- Top 10 worst imbalance events table

**Tab 4: Value-at-Risk**
- VaR 95%, VaR 99%, CVaR 95%, Worst Day metrics
- Daily P&L histogram with VaR threshold lines
- Cumulative P&L with drawdown chart
- Rolling 7-day VaR with daily P&L scatter (red dots = VaR breaches)
- VaR breach count and confidence assessment

---

### AI Chat

Conversational interface powered by 4 specialist Claude agents on Amazon Bedrock AgentCore.

**Setup (one-time per session):**
1. Open the sidebar
2. Enter your **AWS credentials** (Access Key ID, Secret Access Key, Session Token)
3. Click **"Save Credentials"**
4. Status shows "Connected" when ready

**How to use:**
- Click any of the **6 example questions** to get started, or type your own question
- The orchestrator routes your question to the most relevant specialist agent:

| Agent | Expertise |
|-------|-----------|
| **Market Analyst** | Prices, spreads, fuel trends, renewable forecasts, weather |
| **Dispatch Optimizer** | SRMC, merit-order, start-up costs, ramp constraints, contracts |
| **Compliance Officer** | REMIT reporting, contract tolerances, penalty exposure |
| **Risk Manager** | P&L analysis, imbalance exposure, strategy performance |

**Grounding policy:** Every answer cites the source file, row number, and formula used. If the data doesn't support a claim, the agent says so.

Click **"Reset Conversation"** to clear chat history and start fresh.

**Example questions to try:**
- "What was the single most profitable trade and why?"
- "Calculate the break-even electricity price for a CCGT cold start"
- "Which trades are missing REMIT reports? What's the penalty exposure?"
- "Is the CCGT overcommitted during peak hours? Show the math"
- "Compare wind forecast accuracy -- is there a systematic bias?"
- "What was the worst imbalance event in the dataset?"

---

## Data Sources

All data is in the `data/` directory (12 CSV files, 4 reference documents):

| File | Records | Description |
|------|---------|-------------|
| intraday_prices_epex.csv | 8,640 | Quarter-hourly VWAP, high, low, volume, spreads |
| day_ahead_prices.csv | 2,160 | Hourly DA auction prices, buy/sell volumes |
| fuel_prices.csv | 90 | Daily TTF gas, EU ETS carbon, coal, Brent oil |
| trade_blotter.csv | 2,689 | All executed trades with P&L |
| remit_transactions.csv | 2,232 | REMIT transaction reports filed with ACER |
| renewable_forecast.csv | 8,640 | Wind/solar forecasts with P10/P90 bands |
| imbalance_prices.csv | 8,640 | Quarter-hourly settlement prices |
| weather_actuals_forecast.csv | 8,640 | Temperature, wind, solar at 4 locations |
| plant_portfolio.csv | 4 | Plant specs, efficiency, ramp rates, start costs |
| contract_obligations.csv | 6 | PPAs and bilateral contracts |
| marginal_cost_curves.csv | varies | Pre-calculated MC at different load levels |
| grid_constraints.csv | 12,960 | Cross-border ATC/NTC, congestion, redispatch |

**Reference documents:** EPEX SPOT market rules, CCGT operating manual, REMIT compliance guide, balancing and imbalance settlement framework.

---

## Key Formulas

| Formula | Equation |
|---------|----------|
| **SRMC** | Gas_Price / Efficiency + CO2_Price x CO2_Intensity + VOM |
| **Part-load efficiency** | eta(P) = eta_max x (1 - 0.15 x (1 - P/P_max)^2) |
| **Temperature correction** | -0.5% per degree C above 15 degrees C ISO |
| **Clean Spark Spread** | Power_Price - Gas/Efficiency - CO2 x CO2_Intensity |
| **VaR (Historical)** | 5th percentile of daily P&L distribution |
| **CVaR** | Expected loss beyond VaR threshold |

---

## Portfolio

| Plant | Type | Capacity | Efficiency | Min Stable Load |
|-------|------|----------|------------|-----------------|
| RHEIN_CCGT | Combined Cycle Gas Turbine | 430 MW | 58.0% | 170 MW |
| NORDSEE_WIND | Offshore Wind | 350 MW | -- | -- |
| BAYERN_SOLAR | Solar Park | 120 MW | -- | -- |
| ISAR_OCGT | Open Cycle Gas Turbine | 180 MW | 37.1% | 90 MW |
