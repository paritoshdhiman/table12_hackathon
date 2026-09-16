# REMIT II Compliance Guide for Algorithmic Energy Trading
## EU Regulation 2024/1106 - Wholesale Energy Market Integrity and Transparency
## Effective: 7 May 2024

---

## 1. Scope & Applicability

### 1.1 Who Must Comply
- All market participants trading wholesale energy products in the EU
- Includes: generators, retailers, traders, aggregators, storage operators
- Threshold: Any entity executing transactions on organized markets or OTC

### 1.2 What Is Covered
- Wholesale energy products: spot, forward, futures, options on electricity/gas
- Contracts for physical delivery AND financial derivatives
- NEW in REMIT II: Hydrogen contracts, energy storage, LNG

---

## 2. Transaction Reporting (Article 8)

### 2.1 Reporting Deadlines
| Event | Deadline |
|-------|----------|
| Standard supply contracts (spot) | T+1 business day |
| Transportation contracts | T+1 business day |
| Derivative contracts | T+1 business day |
| Order reporting | Real-time (via exchange) |
| Lifecycle events | T+1 business day |

### 2.2 Required Fields
| Field | Description | Example |
|-------|-------------|---------|
| UTI | Unique Transaction Identifier | EPEX-2026-03-15-QH45-001 |
| Reporting entity | ACER registration code | A0003421.DE |
| Contract type | CONT / AUCT | CONT |
| Delivery point | Bidding zone | DE-LU |
| Delivery start | ISO 8601 | 2026-03-15T14:00:00+01:00 |
| Delivery end | ISO 8601 | 2026-03-15T14:15:00+01:00 |
| Volume | MW | 50 |
| Price | EUR/MWh | 85.40 |
| Direction | Buy / Sell | Sell |
| Execution timestamp | Microsecond precision | 2026-03-15T08:23:14.456789+01:00 |
| Trading venue | MIC code | EPXS |

---

## 3. Prohibition of Market Manipulation (Article 5)

### 3.1 Prohibited Behaviors
| Behavior | Definition |
|----------|-----------|
| Wash trading | Trading with yourself to create false volume |
| Spoofing | Placing orders with intent to cancel before execution |
| Layering | Multiple orders at different prices to create false depth |
| Cornering | Accumulating dominant position to control price |
| Ramping | Trading to move price, then profiting from the move |
| Cross-market manipulation | Using position in one market to profit in another |

### 3.2 Algorithmic Trading Requirements (NEW in REMIT II)
1. Document all algorithms with clear description of strategy logic
2. Implement kill switches to halt trading immediately
3. Maintain audit trail of all algorithmic decisions
4. Test algorithms in sandbox before production deployment
5. Notify exchange and NRA of algorithmic trading activity
6. Designate a responsible person for each algorithm
7. Review algorithms annually for compliance

### 3.3 AI/ML-Specific Obligations
- Model documentation: training data, architecture, decision logic
- Explainability: ability to explain why a specific trade was recommended
- Human oversight: human must be able to override AI decisions
- Monitoring: real-time surveillance of AI trading behavior
- Version control: all model versions retained for 5 years

---

## 4. Inside Information (Article 4)

### 4.1 Examples in Power Trading
| Information | Inside? | Action Required |
|-------------|---------|-----------------|
| Planned plant outage (unscheduled) | YES | Disclose on UMM platform before trading |
| Fuel supply disruption | YES | Disclose immediately |
| Grid constraint (non-public) | YES | Disclose via TSO transparency |
| Weather forecast (public) | NO | Can trade on public forecasts |
| Own trading strategy | NO | Proprietary, not inside information |

### 4.2 Urgent Market Messages (UMMs)
- Platform: REMIT Inside Information Platform (IIP)
- Timing: Disclose BEFORE trading on the information
- Penalty for late disclosure: Up to 500,000 EUR

---

## 5. Penalties (REMIT II)
| Violation | Maximum Penalty |
|-----------|----------------|
| Market manipulation | 500,000 EUR or 10x profit |
| Insider trading | 500,000 EUR or 10x profit |
| Failure to report transactions | 200,000 EUR per violation |
| Failure to disclose inside information | 200,000 EUR |
| Inadequate record keeping | 100,000 EUR |

---

## 6. Record Keeping
| Record Type | Retention Period |
|-------------|-----------------|
| Transaction records | 5 years |
| Order records (including cancelled) | 5 years |
| Algorithm documentation | 5 years after decommission |
| Communication records | 5 years |

---

## 7. Compliance Checklist for AI Trading Agent

### Pre-Deployment
- [ ] Algorithm documented with strategy description
- [ ] Kill switch implemented and tested
- [ ] Sandbox testing completed (minimum 30 days)
- [ ] ACER registration confirmed
- [ ] Exchange notified of algorithmic trading
- [ ] Responsible person designated

### Operational
- [ ] All trades reported to ACER within T+1
- [ ] All orders logged with timestamps
- [ ] Real-time surveillance active
- [ ] UMM platform monitored
- [ ] Human oversight available during trading hours

### Post-Trade
- [ ] Daily reconciliation of reported vs executed trades
- [ ] Weekly algorithm performance review
- [ ] Annual algorithm re-certification
- [ ] 5-year record retention confirmed
