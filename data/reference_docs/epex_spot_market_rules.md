# EPEX SPOT Intraday Continuous Market — Trading Rules & Procedures
## DE-LU Bidding Zone — Quarter-Hourly Products
## Version 4.2 — Effective 1 October 2025

---

## 1. Market Overview & Regulatory Framework

### 1.1 Legal Basis
- **EU Regulation 2019/943** (Electricity Regulation): Establishes rules for cross-border electricity trading
- **Commission Regulation 2015/1222** (CACM): Capacity Allocation and Congestion Management guideline
- **REMIT Regulation 2024/1106**: Wholesale Energy Market Integrity and Transparency (revised)
- **EPEX SPOT Exchange Rules**: Approved by BaFin (German Federal Financial Supervisory Authority)
- **Clearing**: ECC (European Commodity Clearing) acts as central counterparty

### 1.2 Market Operator
- **Exchange**: EPEX SPOT SE, Paris (registered in France)
- **Trading system**: M7 (proprietary matching engine)
- **Clearing house**: European Commodity Clearing AG (ECC), Leipzig
- **Regulatory oversight**: BaFin (DE), AMF (FR), ACM (NL), E-Control (AT)

### 1.3 Bidding Zone: DE-LU
- **Coverage**: Germany + Luxembourg (merged bidding zone since 1 October 2018)
- **TSOs**: 50Hertz, Amprion, TenneT DE, TransnetBW
- **Delivery points**: Virtual trading point (no physical nomination required for financial settlement)

---

## 2. Trading Products

### 2.1 Quarter-Hourly Products (QH) — Primary Product
| Parameter | Specification |
|-----------|--------------|
| Product duration | 15 minutes |
| Products per day | 96 |
| Naming convention | QH-01 (00:00-00:15) through QH-96 (23:45-00:00) |
| Minimum order size | 0.1 MW |
| Maximum order size | 9,999.9 MW |
| Tick size | 0.1 MW (volume), 0.01 EUR/MWh (price) |
| Price range | -9,999.00 to +9,999.00 EUR/MWh |
| Trading start | D-1 at 15:00 CET (day-ahead auction results published) |
| Gate closure | 5 minutes before delivery start |
| Settlement | Physical delivery + financial settlement via ECC |

### 2.2 Half-Hourly Products (HH)
| Parameter | Specification |
|-----------|--------------|
| Product duration | 30 minutes |
| Products per day | 48 |
| Composition | Combination of 2 consecutive QH products |
| Trading start | D-1 at 15:00 CET |
| Gate closure | 5 minutes before delivery start |

### 2.3 Hourly Products (H)
| Parameter | Specification |
|-----------|--------------|
| Product duration | 60 minutes |
| Products per day | 24 |
| Composition | Combination of 4 consecutive QH products |
| Trading start | D-1 at 15:00 CET |
| Gate closure | 5 minutes before delivery start |

---

## 3. Order Types

### 3.1 Limit Order
- Standard order with price and volume
- Rests in order book until matched, cancelled, or expired
- Time-in-force: GTC, GTD, IOC, FOK

### 3.2 Market Order
- Executes immediately at best available price
- No price limit; fills against resting limit orders
- Risk: may execute at unfavorable price in thin markets

### 3.3 Iceberg Order
- Only a portion (clip size) visible in order book
- Remaining volume hidden; replenishes as clips are filled
- Minimum clip size: 1 MW

### 3.4 User-Defined Block Order
- Linked orders across multiple delivery periods
- All-or-nothing execution

---

## 4. Matching & Priority Rules

### 4.1 Price-Time Priority (Continuous Matching)
1. Price priority: Best price always matched first (highest buy, lowest sell)
2. Time priority: At same price, earliest order matched first (FIFO)
3. No pro-rata: Strict FIFO at each price level

### 4.2 Cross-Border Matching (XBID / SIDC)
- Orders in DE-LU can match against orders in other SIDC-connected bidding zones
- Condition: Available Transfer Capacity (ATC) must exist on the relevant border
- Connected zones: AT, FR, NL, BE, CH, DK1, DK2, NO, SE, PL, CZ
- Local orders have priority over cross-border at same price

---

## 5. Price Indices

### 5.1 ID3 Index
- Definition: Volume-weighted average price of all trades in last 3 hours before gate closure
- Calculation: ID3 = Sum(Price_i x Volume_i) / Sum(Volume_i) for trades in [GC-3h, GC]
- Use: Reference price for balancing group settlement

### 5.2 IDFull Index
- Definition: Volume-weighted average of ALL trades for a delivery period
- Publication: After gate closure

---

## 6. Gate Closure Times (DE-LU)
| Market | Gate Closure |
|--------|-------------|
| Intraday continuous (local) | D, H-5min |
| Intraday continuous (XBID) | D, H-60min |
| Intraday auction (IDA1) | D-1, 15:00 CET |
| Intraday auction (IDA2) | D-1, 22:00 CET |
| Intraday auction (IDA3) | D, 10:00 CET |

---

## 7. Fees
| Fee Type | Amount | Basis |
|----------|--------|-------|
| Transaction fee | 0.04 EUR/MWh | Per executed MWh |
| Annual membership | 25,000 EUR | Per trading participant |
| ECC clearing fee | 0.01 EUR/MWh | Per cleared MWh |

---

## 8. REMIT II Compliance
- Transaction reporting: All trades reported to ACER within T+1 business day
- Order reporting: All orders (including cancelled) reported to ACER
- Inside information: Must be disclosed on REMIT platform before trading
- Algorithmic trading: Must be documented, tested, and auditable
- Penalties: Up to 500,000 EUR per violation or 10x profit gained
- Record keeping: All orders and trades retained for 5 years
