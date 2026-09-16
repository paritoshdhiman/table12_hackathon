# Rheinhafen Combined Cycle Gas Turbine (CCGT) - Plant Operating Manual
## Siemens SGT5-8000H Gas Turbine + SST5-5000 Steam Turbine
## Nameplate Capacity: 430 MW (net) | Commissioned: 2019

---

## 1. Plant Configuration

### 1.1 Gas Turbine Island
| Parameter | Value |
|-----------|-------|
| Manufacturer | Siemens Energy |
| Model | SGT5-8000H (H-class) |
| Fuel | Natural gas (pipeline quality, Wobbe Index 47-53 MJ/m3) |
| Gross output (GT only) | 295 MW at ISO conditions |
| Turbine inlet temperature | 1,500 C (design) |
| Pressure ratio | 21:1 |
| Exhaust temperature | 625 C |
| Exhaust mass flow | 820 kg/s |

### 1.2 Heat Recovery Steam Generator (HRSG)
| Parameter | Value |
|-----------|-------|
| Type | Triple-pressure with reheat |
| HP steam | 170 bar / 565 C |
| IP steam | 35 bar / 565 C (reheat) |
| LP steam | 4.5 bar / 250 C |

### 1.3 Overall Plant Performance
| Parameter | ISO Conditions | Summer (35C) | Winter (-5C) |
|-----------|---------------|--------------|--------------|
| Net output | 430 MW | 395 MW | 455 MW |
| Net efficiency (LHV) | 58.0% | 56.2% | 59.1% |
| Heat rate (Btu/kWh) | 5,880 | 6,069 | 5,770 |
| CO2 intensity | 0.349 tCO2/MWh | 0.360 tCO2/MWh | 0.342 tCO2/MWh |

---

## 2. Operating Modes & Constraints

### 2.1 Load Range
| Mode | Load Range | Notes |
|------|-----------|-------|
| Full load | 380-430 MW | Normal operating range |
| Part load | 170-380 MW | Efficiency penalty applies |
| Minimum stable load | 170 MW (40%) | Below this: flame instability |

### 2.2 Ramp Rates
| Condition | Ramp Up | Ramp Down |
|-----------|---------|-----------|
| Normal operation | 20 MW/min | 20 MW/min |
| Fast ramp (GT only) | 30 MW/min | 30 MW/min |
| Frequency response | +/- 5% in 30s | +/- 5% in 30s |

### 2.3 Start-Up Times & Costs
| Start Type | Condition | Time to Min Load | Time to Full Load | Total Start Cost |
|-----------|-----------|-----------------|-------------------|-----------------|
| Hot start | <8h offline | 30 min | 60 min | 45,000 EUR |
| Warm start | 8-48h offline | 90 min | 150 min | 85,000 EUR |
| Cold start | >48h offline | 240 min | 360 min | 145,000 EUR |

### 2.4 Minimum Run/Down Times
| Parameter | Value | Reason |
|-----------|-------|--------|
| Minimum run time | 4 hours | Thermal stress limits on HRSG headers |
| Minimum down time | 4 hours | Cooling requirements before restart |
| Maximum starts per day | 2 | Lifetime management |

---

## 3. Efficiency & Part-Load Performance

### 3.1 Willans Line
    eta(P) = eta_max * (1 - k * (1 - P/P_max)^2)
    eta_max = 0.580, k = 0.15, P_max = 430 MW

### 3.2 Part-Load Efficiency Table
| Load (MW) | Efficiency (%) | Heat Rate (Btu/kWh) | SRMC (EUR/MWh) |
|-----------|---------------|---------------------|----------------|
| 430 | 58.0 | 5,880 | 68.4 |
| 400 | 57.7 | 5,912 | 68.8 |
| 350 | 57.0 | 5,986 | 69.7 |
| 300 | 55.9 | 6,103 | 71.1 |
| 250 | 54.4 | 6,272 | 73.1 |
| 200 | 52.4 | 6,511 | 76.0 |
| 170 | 50.8 | 6,717 | 78.4 |

(SRMC calculated at TTF=32 EUR/MWh, ETS=65 EUR/tCO2)

### 3.3 Ambient Temperature Correction
- Output: -0.7% per degree C above 15C ISO
- Efficiency: -0.5% per degree C above 15C ISO

### 3.4 Short-Run Marginal Cost Formula
    SRMC = Gas_Price / Efficiency + CO2_Price * (0.202 / Efficiency) + VOM
    VOM = 2.70 EUR/MWh

---

## 4. Fuel System
| Parameter | Value |
|-----------|-------|
| Gas source | TransnetBW high-pressure grid (70 bar) |
| Gas quality | H-gas (Wobbe 47-53 MJ/m3, CH4 > 85%) |
| Maximum consumption | 74,000 Nm3/h at full load |
| Gas calorific value | 39.0 MJ/Nm3 (HHV) / 35.2 MJ/Nm3 (LHV) |
| Conversion | 1 MWh_th = 3.412 MMBtu = 3.6 GJ |

---

## 5. Emissions & EU ETS
| Parameter | Value |
|-----------|-------|
| Emission factor (gas) | 0.202 tCO2/MWh_th |
| Specific emissions (full load) | 0.349 tCO2/MWh_e |
| Specific emissions (min load) | 0.398 tCO2/MWh_e |
| EU ETS Phase IV | No free allocation for power generation |
| Carbon cost at full load | 0.349 * ETS_price EUR/MWh |

---

## 6. Trading-Relevant Operating Procedures

### 6.1 Pre-Start Checklist
1. Confirm plant status (hot/warm/cold) with control room
2. Calculate start cost + minimum run time revenue requirement
3. Verify gas nomination is possible (check gas day timing)
4. Check ambient temperature for output correction
5. Break-even price: (Start_Cost / (Min_Run_Hours * Capacity)) + SRMC

### 6.2 Dispatch Optimization Rules
- Never start for less than minimum run time (4 hours)
- Never operate below minimum stable load (170 MW)
- Ramp constraint: max 20 MW per minute
- If selling 430 MW for hour H, must be at 430 MW by start of H
- Ramp from 170 to 430 MW takes (430-170)/20 = 13 minutes

### 6.3 Gas Nomination Timing
- Day-ahead nomination: by 14:00 CET D-1
- Within-day nomination: 2-hour lead time
- Renomination: every 2 hours during gas day
- Imbalance tolerance: +/- 5% of nominated volume
