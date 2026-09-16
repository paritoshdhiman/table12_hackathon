# DELTA — Dynamic Energy Load & Trading Analytics

Intraday energy trading optimization dashboard for a 4-plant German utility portfolio operating on EPEX SPOT (DE-LU bidding zone). Analyzes 90 days of market data with AI-powered multi-agent analytics.

## Portfolio

| Plant | Type | Capacity |
|-------|------|----------|
| RHEIN_CCGT | Combined Cycle Gas Turbine | 430 MW |
| NORDSEE_WIND | Offshore Wind | 350 MW |
| BAYERN_SOLAR | Solar Park | 120 MW |
| ISAR_OCGT | Open Cycle Gas Turbine (peaker) | 180 MW |

## Features

- **Daily Briefing** — AI-generated market briefing with spread analysis, dispatch economics, and risk signals
- **Portfolio Overview** — Plant specs, contract obligations, and capacity utilization
- **Market Analysis** — Intraday/day-ahead price profiles, fuel trends, renewable forecasts
- **Plant Dispatch** — Merit-order optimization with SRMC curves and part-load efficiency
- **Scenario Simulator** — What-if analysis with sensitivity heatmaps
- **Compliance & Risk** — REMIT reporting status, P&L analytics, imbalance exposure
- **AI Chat** — Multi-agent orchestrator with 4 specialist Claude agents (requires AWS setup)

## Prerequisites

- Python 3.11+
- AWS account with Amazon Bedrock access (for AI Chat feature only)

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Run the app
streamlit run app.py
```

Pages 0–5 (Daily Briefing through Compliance & Risk) work immediately with no additional configuration. They use the included dataset of 12 CSV files covering 55,060 rows of market data.

### AI Chat setup (optional)

The AI Chat page uses a multi-agent system powered by Claude on Amazon Bedrock. To enable it:

1. **Configure AWS credentials** with access to Amazon Bedrock:
   ```bash
   aws configure
   # or export AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_DEFAULT_REGION
   ```

2. **Enable model access** — request access to the Claude model in the [Amazon Bedrock console](https://console.aws.amazon.com/bedrock/) under Model access.

3. **(Optional) Override defaults** via environment variables:
   ```bash
   export AWS_REGION="us-east-1"                                    # default: us-east-1
   export BEDROCK_MODEL_ID="us.anthropic.claude-opus-4-6-v1"        # default: claude-opus-4-6-v1
   ```

4. **Run the app** — the AI Chat page will automatically initialize the multi-agent orchestrator.

### Bedrock AgentCore (optional)

For deployed agent mode, set these environment variables:

```bash
export TRADING_CHAT_AGENT_ARN="arn:aws:bedrock:..."
export MARKET_ANALYST_AGENT_ARN="arn:aws:bedrock:..."
export AGENTCORE_REGION="us-east-1"
```

## Architecture

```
Orchestrator (Claude Opus 4.6)
├── Market Analyst    — prices, spreads, fuel, renewables, weather
├── Dispatch Optimizer — SRMC, merit-order, ramp constraints, contracts
├── Compliance Officer — REMIT reporting, contract tolerances, penalties
└── Risk Manager       — P&L, imbalance exposure, strategy performance
```

Each specialist agent has its own system prompt and tool set covering all 12 data files and 4 reference documents. Every answer cites the source file and row number.

## Data

All data is included in the `data/` directory:

- `market_prices/` — intraday prices, day-ahead prices, fuel prices, trade blotter, REMIT transactions, renewable forecasts, imbalance prices, weather
- `plant_portfolio/` — plant specs, contract obligations, marginal cost curves
- `grid_constraints/` — cross-border ATC/NTC, congestion, redispatch
- `reference_docs/` — EPEX SPOT rules, CCGT operating manual, REMIT compliance guide, balancing framework
