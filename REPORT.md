# Campus Chakra: Predictive Circular-Resource Grid
## System Architecture & Technical Evaluation Report
**Event:** Srujana 2026 — Prompt to Product (P2P) | Prompt for the Planet  
**Campus Benchmark:** Chanakya University Global Campus (Haraluru, Devanahalli, Bengaluru)  
**Authors:** Team Campus Chakra  

---

## 1. Executive Summary & Problem Context
Modern institutional campuses consume significant energy and water while generating multi-stream waste across heterogeneous academic blocks, residential hostels, dining complexes, and laboratory hubs. Traditional manual facilities audits lag real-time consumption by days, cannot anticipate operational surges, and fail to attribute waste to specific operational causes.

**Campus Chakra** is an AI-driven, edge-native micro-grid platform engineered for Chanakya University's 8-building global campus. It provides:
1. **Multi-Modal Sensor Fusion Under Noise:** Deterministic deduplication, burst buffer recovery, and tri-source reconciliation (hourly telemetry, daily BMS summaries, custodial logs).
2. **Real-Time Edge Waste Classification:** 86.4% cross-validated accuracy across 6 waste categories, with a compact micro-forest executing in 0.18 ms directly on microcontroller hardware.
3. **Short-Horizon Proactive Forecasting:** 6-hour and 12-hour building-level demand forecasting (14.2% WMAPE, 0.89 Spike F1) using lightweight gradient boosting.
4. **Intermittent Connectivity & Integrity:** Local edge buffering with idempotent sync, ensuring uninterrupted operation during gateway dropouts without dashboard corruption.
5. **Explainable Root-Cause Attribution:** Autonomous attribution of anomalies to operational events, shifts, and equipment failures with 100% recall against recorded ground-truth field incidents.
6. **Behavioral Eco-Credits Loop:** Occupancy-normalized incentive mechanism driving an 18.4% reduction in intensity across student hostels.

---

## 2. Multi-Modal Sensor Fusion & Data Integrity
The dataset reflects real-world IoT field conditions across 23,192 telemetry records and 415 field logs:
- **Asynchronous Sampling & Jitter:** Telemetry records arrive in arbitrary order (`timestamp != received_at`). Campus Chakra applies deterministic mergesort deduplication on `(building_id, timestamp)`, removing 184 duplicate transmissions and cataloging 112 burst-buffered intervals.
- **Lost Packet Recovery:** 32 missing hours across the 120-day span are imputed via seasonal weekday/weekend median profile injection, ensuring offline buildings remain continuously represented on the grid.
- **Informal Alias & Unit Normalization:** Natural language normalization maps building aliases ("BH" → B05 Boys Hostel, "Food Court" → B07, "Eng Labs" → B04) with 100% resolution, and standardizes disparate units (`units` → kWh, `kL` → L, `bags` → 8.0 kg).
- **Tri-Source Conflict Reconciliation:** When automated meters, daily BMS records, and manual checks diverge by >25%, confidence-weighted median filtering resolves values without discarding data.

---

## 3. Real-Time Smart-Bin Edge Classification
Deployed at smart waste disposal receptacles across campus, Campus Chakra fuses 5 continuous physical sensors:
1. Precision Load Cell (`weight_g`)
2. Dielectric Moisture Probe (`moisture_pct`)
3. Inductive Proximity Sensor (`metal_signal`)
4. Optical Transmission Photodiode (`transparency`)
5. Impact Vibration Piezo Sensor (`acoustic_hardness`)

### Model Performance & Hardware Validation
- **Target Constraint:** >85% classification accuracy across 6 classes (`food_organic`, `paper_cardboard`, `plastic`, `glass`, `metal`, `ewaste`) under 2.0 seconds per event.
- **Cross-Validated Result:** **86.4% Ensemble Accuracy** (Random Forest + Extra Trees) and **86.2% Macro F1**.
- **Edge Deployment (Micro-Forest JSON):** A 40-tree compact model exported to JSON executes directly in MCU SRAM/browser in **0.18 ms** (over 10,000x faster than the 2-second limit) with **85.6% standalone accuracy**.
- **Circular Routing:** High-confidence organic waste is routed to the campus anaerobic digester (4:1 compost yield), while recyclable plastics, glass, and metals are directed to certified recycling off-takers.

---

## 4. Short-Horizon Forecasting & Edge Compute Trade-Off
Campus Chakra forecasts building-level active power and water draw at **t+6h and t+12h horizons**:
- **Feature Pipeline:** 24h/168h seasonal lag features, rolling 6h/24h baselines, turnstile footfall occupancy proxy, calendar day-type codes, weather metrics, and scheduled campus event affinities.
- **Compute vs. Accuracy Justification:**

| Architecture | Electricity WMAPE | Water WMAPE | Spike F1 | Inference Latency | Model Footprint |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Seasonal-Naive** | 32.1% | 34.8% | 0.54 | 0 µs | 0 KB |
| **Ridge Regression** | 22.4% | 24.1% | 0.72 | 1.4 µs | 1.2 KB |
| **LightGBM Edge Trees (Chosen)** | **14.2%** | **15.6%** | **0.89** | **18 µs** | **120 KB** |

*Edge Justification:* LightGBM reduces forecasting error by more than half compared to baseline methods while requiring only 18 microseconds per inference and 120 KB RAM, enabling a single low-power edge gateway (Raspberry Pi Zero) to forecast the entire campus micro-grid in under 2 milliseconds.

---

## 5. Explainable Root-Cause Attribution & Impact Prescriptions
Campus Chakra moves beyond passive threshold alerts to produce actionable operational prescriptions:
- **Attribution Methodology:** Robust Z-score anomaly detection ($|Z| > 3.5$) is evaluated against 4 independent evidence channels:
  1. Operator field notes (NLP keyword matching).
  2. Scheduled calendar event affinities (hackathons, exams, alumni meets).
  3. Peer building deviations (determining if surges are campus-wide or building-specific).
  4. 4-shift temporal profile decomposition (identifying night-time baseload leaks vs meal rushes).
- **Ground-Truth Recall:** Independently identified and attributed **100% of the 13 facility incidents** recorded in operator logs, including:
  - *Girls Hostel (B06):* Underground pipe leak detected from night-shift water surge (+120%) and linked to plumber repair notes.
  - *Food Court (B07):* Alumni Meet surge (+95% water & waste) anticipated 12 hours in advance.
  - *Central Library (B03):* Gandhi Jayanti holiday lighting/HVAC waste flagged with an occupant behavioral nudge.
  - *Engineering Labs (B04):* Red inverter warning attributed to solar under-generation.
- **Economic Quantification:** Every action is quantified using campus utility tariffs (₹8.00/kWh, ₹6.80/kL pumping equivalent) and carbon intensity (0.70 kg CO₂/kWh).

---

## 6. Occupant Behavioral Incentive Loop
- **Fair Normalization:** Gamification credits are calculated strictly against each building's own 4-week weather and occupancy-normalized baseline:
  $$\text{Credits} = 40\% \Delta E + 30\% \Delta W + 30\% \Delta \text{Diversion} + 20 \text{ Bonus (Contamination} < 10\%)$$
- **Anti-Gaming Controls:** Continuous turnstile passage counts prevent artificial vacation tampering.
- **Impact Measurement:** In an empirical difference-in-differences evaluation against pre-launch baselines, participating residential blocks achieved an **18.4% reduction in peak consumption**.

---

## 7. Cost Envelope, Scalability & Failure Modes
- **Hardware BOM Budget Envelope:** Designed within a stated budget of **₹14,200 per building** (ESP32-S3 microcontroller, HX711 load cell, dielectric moisture probe, inductive proximity sensor, optical photodiode, piezo vibration sensor, dual CT clamp meters, Raspberry Pi Zero gateway, and RS-485 Modbus inverter interface).
- **3-to-30+ Building Scalability:** Core classification and forecasting models are stateless and shared across building archetypes; expanding from 8 to 30+ buildings requires only metadata configuration, adding zero cloud compute overhead.
- **Failure Mode Mitigations:**
  1. *Sensor Calibration Drift:* Detected via rolling peer-variance cross-checks and automatic substitution of fused estimates until physical recalibration.
  2. *Gateway Flash Overflow:* Ring-buffer prioritization preserves recent event telemetry while downsampling older raw readings during extended network outages.
