# German Electricity Balancing & Imbalance Settlement
## TSO Balancing Framework - DE-LU Control Area
## Based on EU Electricity Balancing Guideline (EB GL) 2017/2195

---

## 1. Balancing Framework Overview

### 1.1 Responsible Parties
| Entity | Role |
|--------|------|
| Balance Responsible Party (BRP) | Responsible for balancing supply and demand in their portfolio |
| TSO (50Hertz, Amprion, TenneT DE, TransnetBW) | Maintains system balance, activates reserves |
| Balancing Service Provider (BSP) | Provides balancing energy (generators, demand response) |
| EPEX SPOT / exchanges | Provide intraday market for BRPs to self-balance |

### 1.2 Balancing Products (Germany)
| Product | Activation Time | Duration | Platform |
|---------|----------------|----------|----------|
| FCR (Frequency Containment Reserve) | 30 seconds | Continuous | PICASSO |
| aFRR (Automatic Frequency Restoration) | 5 minutes | 15 min | PICASSO |
| mFRR (Manual Frequency Restoration) | 12.5 minutes | 15 min | MARI |
| RR (Replacement Reserve) | 30 minutes | Variable | TERRE |

---

## 2. Imbalance Settlement

### 2.1 Settlement Period
- Duration: 15 minutes (aligned with market time unit since Oct 2025)
- 96 settlement periods per day
- Each BRP settled independently per period

### 2.2 Imbalance Calculation
    Imbalance (MW) = Actual_Generation + Actual_Imports - Actual_Demand - Actual_Exports - Scheduled_Position

Where Scheduled_Position = sum of all nominated trades (day-ahead + intraday)

### 2.3 Imbalance Pricing (Single Pricing - Germany)
Germany uses single imbalance pricing:
    Imbalance_Price = Marginal price of activated balancing energy in the settlement period

- If system is SHORT (under-generation): price = cost of upward balancing energy (high)
- If system is LONG (over-generation): price = cost of downward balancing energy (low/negative)
- BRPs with imbalance in SAME direction as system pay the imbalance price
- BRPs with imbalance in OPPOSITE direction receive the imbalance price

### 2.4 Imbalance Price Ranges (Typical)
| System State | Imbalance Price Range | Frequency |
|-------------|----------------------|-----------|
| Balanced (+/- 100 MW) | 50-90 EUR/MWh | ~60% of periods |
| Moderately short | 80-150 EUR/MWh | ~20% of periods |
| Moderately long | 20-60 EUR/MWh | ~15% of periods |
| Extremely short | 150-9,999 EUR/MWh | ~3% of periods |
| Extremely long | -500 to 20 EUR/MWh | ~2% of periods |

### 2.5 Imbalance Cost Calculation
    Cost_to_BRP = Imbalance_Volume (MWh) * (Imbalance_Price - Reference_Price)

Where Reference_Price = ID3 index (volume-weighted average of last 3h intraday trades)

---

## 3. Incentive Structure

### 3.1 Why Intraday Trading Reduces Imbalance Risk
- Intraday market gate closure: 5 min before delivery
- Imbalance settlement: after delivery
- Trading intraday allows BRP to adjust position based on latest forecasts
- Imbalance prices are MORE volatile than intraday prices (by design)
- Expected cost of being imbalanced > expected cost of trading intraday

### 3.2 Passive Balancing
- BRPs can intentionally deviate from schedule to help system balance
- If BRP deviates in OPPOSITE direction to system imbalance: receives favorable price
- This is LEGAL under REMIT (not manipulation) if based on public information
- Risk: if system direction changes, BRP pays unfavorable price

### 3.3 Imbalance Risk Quantification
    Expected_Imbalance_Cost = P(short) * E[Imb_Price_Short - Market] * Volume
                            + P(long) * E[Market - Imb_Price_Long] * Volume

Typical values:
- P(short) for wind portfolio: 30-40% of periods
- E[Imb_Price_Short - Market]: 15-40 EUR/MWh (average penalty)
- For 100 MW portfolio: expected imbalance cost = 5,000-15,000 EUR/day

---

## 4. Balancing Energy Platforms

### 4.1 PICASSO (aFRR)
- Platform for Automatic Frequency Restoration Reserve
- Activation: automatic, based on frequency deviation
- Merit order: cheapest bids activated first across all connected TSOs
- Settlement: pay-as-cleared (marginal pricing)
- Gate closure: 25 minutes before delivery

### 4.2 MARI (mFRR)
- Platform for Manual Frequency Restoration Reserve
- Activation: manual, by TSO operator
- Merit order: cheapest bids activated first
- Settlement: pay-as-cleared
- Gate closure: 25 minutes before delivery

### 4.3 Cross-Border Balancing
- Imbalance netting (IGCC): TSOs net opposing imbalances before activating reserves
- Reduces total balancing costs by 200-400M EUR/year across Europe
- Connected TSOs: 21 operational members across continental Europe

---

## 5. Data Sources for Imbalance Forecasting

### 5.1 Real-Time Data (Available to All Market Participants)
| Source | Data | Update Frequency | URL |
|--------|------|-------------------|-----|
| ENTSO-E Transparency | System balance, activated reserves | 1 minute | transparency.entsoe.eu |
| TSO websites | Control area balance, frequency | 10 seconds | 50hertz.com, amprion.net |
| EPEX SPOT | Intraday prices, order book | Real-time | epexspot.com |
| Netztransparenz.de | Imbalance prices (ex-post) | 15 minutes (T+10min) | netztransparenz.de |

### 5.2 Forecasting Indicators
| Indicator | Correlation with Imbalance Price | Source |
|-----------|----------------------------------|--------|
| Wind forecast error | HIGH (negative: over-forecast = long system) | ENTSO-E |
| Solar forecast error | MEDIUM | ENTSO-E |
| Temperature deviation | MEDIUM (cold snap = short system) | Weather services |
| Unplanned outages | HIGH (large outage = short system) | UMM platform |
| Cross-border flow changes | MEDIUM | ENTSO-E |
| Intraday price trend | HIGH (rising ID price = market expects shortage) | EPEX SPOT |

---

## 6. Trading Strategy Implications

### 6.1 When to Trade Intraday vs Accept Imbalance
Trade intraday when:
- Forecast error is large and direction is clear
- Imbalance price spread (short vs long) is wide
- Intraday liquidity is sufficient (volume > 50 MWh per QH)
- Time to gate closure > 30 minutes (can still adjust)

Accept imbalance when:
- Forecast uncertainty is symmetric (equal chance of long/short)
- Intraday spread is already at imbalance price level
- Volume is small (<5 MW) and transaction costs dominate
- Gate closure is imminent and liquidity is thin

### 6.2 Optimal Position Management
1. After day-ahead: calculate expected position based on latest forecasts
2. At D-1 15:00 (intraday opens): place limit orders for known deviations
3. During delivery day: continuously update position as forecasts improve
4. Near gate closure: use market orders for remaining imbalance
5. Post-delivery: analyze imbalance costs and refine forecasting model
