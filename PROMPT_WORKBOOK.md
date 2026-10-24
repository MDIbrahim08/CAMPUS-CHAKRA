# Campus Chakra: Prompt to Product (P2P 2026) Workbook
**Event:** Srujana 2026 | Prompt to Product  
**Project:** Campus Chakra – Predictive Circular-Resource Grid  
**Context:** Chanakya University Global Campus (Haraluru, Devanahalli, Bengaluru)  
**Submission Deadline:** 24 October 2026, 2:00 PM  

---

## 1. AI Tools & LLM Ecosystem Used

1. **Claude Opus / Gemini 3.8 / Gemma & Qwen:**
   - Architecture decomposition and edge hardware tradeoff analysis.
   - Design of deterministic sensor fusion under noise (dedup, reconciliation, jitter handling).
   - Python code generation for feature engineering and LightGBM / Random Forest / ExtraTrees model training.

2. **Multi-Agent Facilities Copilot (Integrated into Product):**
   - **NVIDIA Nemotron Super-49B / Llama 3.3:** Acting as root-cause diagnostic Analyst.
   - **Groq Llama 3.3 70B / Qwen:** Acting as operational Planner (calculating ₹ tariffs and CO₂ impact).
   - **Google Gemini 2.0 Flash / Gemma:** Acting as Verifier to prevent hallucination by cross-referencing ground-truth telemetry evidence.
   - **Local Deterministic Fallback Engine:** Guarantees 100% offline edge operational resilience without external internet dependencies.

---

## 2. Key Prompts & Iterative Engineering Evolution

### Phase 1: Problem Formulation & Schema Inspection
- **Prompt:**
  > *"Analyze the problem statement constraints: Multi-modal sensor fusion under noise, Real-time edge classification (>85% target within 2s), Short-horizon forecasting (6–12h ahead), Intermittent connectivity & buffer recovery, Root-cause anomaly attribution, and Behavioral eco-credits. Inspect `P2P_DATASET` tables: `buildings.csv`, `calendar.csv`, `daily_summary.csv`, `hourly_streams.csv`, `manual_logs.csv`, `waste_events_train.csv`, `waste_events_test.csv`."*
- **Outcome & Findings:**
  - Discovered 184 duplicate retransmissions with jitter and 112 late-buffered bursts (>2h lag).
  - Uncovered 415 manual operator logs with informal aliases ("BH" for Boys Hostel, "Food Court", "Eng Labs") and mixed units (`kWh` vs `units`, `L` vs `kL`, `kg` vs `bags`).
  - Identified 13 qualitative field notes serving as ground-truth incident records (underground pipe leak, composter burnout, inverter failure).

### Phase 2: Smart-Bin Edge Classifier Optimization
- **Prompt Iteration 1 (Sensor-Only Baseline):**
  > *"Train a classifier on the 5 physical sensor continuous features (`weight_g`, `moisture_pct`, `metal_signal`, `transparency`, `acoustic_hardness`). Handle missing sensor values natively."*
  - *Result:* 84.5% 5-fold CV accuracy (just below the 85% competition target threshold).
- **Prompt Iteration 2 (Physical Glitch & Edge Context Fusion):**
  > *"Analyze physical sensor hardware behaviors: moisture and inductive sensors frequently glitch/saturate at 100.0%. Add saturation binary flags, missing sensor counts, and edge-available contextual features: building ID, hour-of-day, and day-of-week. Compare Random Forest, Extra Trees, and LightGBM."*
  - *Result:* Reached **86.4% Accuracy** and **86.2% Macro F1**.
- **Prompt Iteration 3 (Micro-Forest JSON Export for Low-Power Microcontrollers):**
  > *"Export a compact 40-tree micro-forest into pure JSON arrays for direct execution in microcontroller C/JavaScript with zero dependencies and <1 ms inference time."*
  - *Result:* 85.6% standalone browser/MCU execution accuracy at **0.18 ms** per event (10,000x faster than the 2-second constraint).

### Phase 3: Short-Horizon Forecasting (t+6h, t+12h) & Edge Tradeoff
- **Prompt:**
  > *"Develop a global time-series model forecasting electricity and water demand at t+6h and t+12h horizons. Benchmark Seasonal-Naive vs Ridge vs LightGBM on a strict 21-day chronological holdout across all 8 buildings. Explicitly document the compute-accuracy tradeoff for edge gateways."*
- **Outcome & Benchmark:**
  - *Seasonal-Naive:* 32.1% WMAPE, 0 KB RAM, 0 µs compute.
  - *Ridge Regression:* 22.4% WMAPE, 1.2 KB RAM, 1.4 µs compute.
  - *LightGBM Edge Trees (Chosen):* **14.2% WMAPE**, **0.89 Spike F1**, 120 KB RAM, **18 µs** compute per building.

### Phase 4: Root-Cause Attribution & Operator Note Ground-Truth
- **Prompt:**
  > *"Do not merely flag raw graphs as anomalies. Build a multi-factor attribution engine combining calendar event affinities, operator field note NLP regex, peer-building comparisons, and shift profiles (night baseload vs meal shifts). Calculate exact cost in ₹ (₹8/kWh tariff) and CO₂ (0.70 kg/kWh) for each recommendation."*
- **Outcome:**
  - Successfully achieved **100% independent recall on all 13 ground-truth facility incidents** in the dataset (Girls Hostel pipe leak, composter motor failure, AC left on during Gandhi Jayanti, Alumni Meet food court demand spike).

---

## 3. Human Contribution & Engineering Decisions

1. **Deterministic Edge Resilience:** We mandated that all critical operational intelligence (classification, forecasting, anomaly attribution, data integrity sync) must run deterministically on local edge gateways without requiring continuous cloud GPU or internet connectivity.
2. **Idempotent Data Reconciliation:** Engineered a deterministic key `(building_id, timestamp, seq)` with last-write-wins sequencing to guarantee that whenever edge gateways disconnect for hours, their local SD card buffers merge into the central grid without corrupting historical aggregates.
3. **Equitable Eco-Credits Formula:** Designed the gamification system to normalize consumption against each building's own 4-week weather and occupancy baseline, preventing unfair hostel vs. lab comparisons.
4. **Hardware BOM Budget Envelope:** Specified a realistic hardware BOM of **₹14,200 per building** (ESP32-S3, load cells, inductive/optical probes, Raspberry Pi Zero gateway, energy CT clamps, RS-485 Modbus) meeting the stated cost constraints.
