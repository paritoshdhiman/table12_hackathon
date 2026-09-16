# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Streamlit 1.40+ with Plotly charts, Python 3.12, Strands Agents SDK with AWS Bedrock (Claude Opus 4.6)

## Users

Hackathon judges evaluating a Claude Code + Bedrock AgentCore demo. They score: working demo, depth of reasoning, and data traceability (every number traces to a specific data file/row). Secondary: energy trading professionals who would use this operationally.

## Product Purpose

Intraday Energy Trading Optimization Agent — analyzes 90 days of EPEX SPOT DE-LU electricity market data for a 4-plant German utility portfolio (CCGT 430MW, Wind 350MW, Solar 120MW, OCGT 180MW). Demonstrates Claude's analytical depth through merit-order dispatch optimization, scenario simulation, REMIT compliance monitoring, and AI-powered market briefings. Success = judges see that Claude can reason deeply about complex energy trading decisions with full data traceability.

## Positioning

Hybrid Analyst + Scenario Simulator: pre-computed analytics displayed in a professional trading desk dashboard, combined with an AI chat agent (Claude on Bedrock) that answers grounded questions with source citations. Shows Claude reasoning about SRMC, part-load efficiency, clean spark spreads, start-up economics, and regulatory compliance — not just summarizing data.

## Operating Context

Hackathon demo environment. Port 3001 for Streamlit. Data from 12 CSVs (55,060 rows) unzipped from use-case-4-data.zip. Key demo moments: CCGT overcommitment detection (450MW contracted vs 430MW capacity), 457 missing REMIT reports, AI briefing generation, scenario what-if analysis with sensitivity heatmaps.

## Capabilities and Constraints

- 8 pages: Command Center, AI Daily Briefing, Portfolio Overview, Market Analysis, Plant Dispatch, Scenario Simulator, Compliance & Risk, AI Chat
- Dark trading desk theme across all visualizations
- Merit-order dispatch optimizer with Willans line part-load efficiency
- VaR/CVaR risk analytics
- Strands Agent with 10 tool functions for grounded Q&A
- Constraint: Streamlit's component model limits animation/interactivity vs React

## Evidence on Hand

Real market data structure (synthetic 90-day dataset): intraday prices, day-ahead prices, fuel prices, renewable forecasts, weather, trade blotter, REMIT transactions, imbalance prices, plant portfolio, contract obligations, marginal cost curves, grid constraints. Reference docs: EPEX rules, CCGT operating manual, REMIT regulation, grid code.

## Product Principles

1. Every number is grounded — traceable to a specific CSV file, row, and formula
2. Show depth of reasoning, not just data display — surface non-obvious insights like overcommitment, efficiency derating, start-up economics
3. Professional trading desk aesthetic — dark theme, information-dense, zero visual noise
4. Claude as the analyst — the AI briefing and chat demonstrate Claude reasoning about energy markets, not just querying a database
