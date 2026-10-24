# Campus Chakra: Prompt to Product (P2P 2026) Workbook
## Official Prompt Engineering Architecture & Evolution Log

[![Prompt Workbook PDF](https://img.shields.io/badge/Download_Workbook-PDF-8A2BE2?style=for-the-badge&logo=adobeacrobatreader&logoColor=white)](PROMPT_WORKBOOK.pdf)
[![Platform](https://img.shields.io/badge/Platform-Campus%20Chakra-00A86B?style=for-the-badge)](README.md)
[![Edge Accuracy](https://img.shields.io/badge/Edge%20Accuracy-86.4%25-brightgreen?style=for-the-badge)](REPORT.md)
[![Latency](https://img.shields.io/badge/Latency-0.18ms-blue?style=for-the-badge)](REPORT.md)

**Event:** Srujana 2026 — Prompt to Product (P2P) | Prompt for the Planet  
**Project:** Campus Chakra – Predictive Circular-Resource Grid  
**Benchmark Context:** Chanakya University Global Campus (Haraluru–Polanahalli, Devanahalli, Bengaluru)  
**Quick Downloads:** [📥 Download Official PDF Workbook (PROMPT_WORKBOOK.pdf)](PROMPT_WORKBOOK.pdf) · [📄 Alternative PDF Link (PROMPTS.pdf)](PROMPTS.pdf) · [🌐 View Web HTML Version](PROMPT_WORKBOOK.html)

---

## 🏆 Executive Summary for Juries

This workbook provides an auditable, step-by-step record of the prompt engineering evolution that produced **Campus Chakra**. Rather than treating LLMs as naive code generation black boxes, we employed structured, multi-stage prompt chains combining:
1. **Domain-Constrained Problem Formulation:** Enforcing edge hardware bounds (ESP32-S3, Raspberry Pi Zero) and mathematical constraints.
2. **Glitch-Aware Feature Conditioning:** Prompting models to inspect physical sensor physics (impedance saturation, piezo impact frequencies) rather than treating tabular data as clean.
3. **Compute-vs-Accuracy Tradeoff Optimization:** Guiding models to evaluate lightweight decision trees and micro-forests achieving **86.4% accuracy** in **0.18 ms** (10,000× faster than the 2-second competition limit).
4. **Multi-Agent Tri-Verification Chains:** Grounding LLM outputs in verified telemetry evidence with deterministic local fallbacks.

### 📊 Prompt Evolution & Measurable Impact Matrix

| Phase & Prompt Focus | Initial Baseline Prompt | Iterative Engineering Prompt | Resulting Metric Jump | Key Engineering Insight |
| :--- | :--- | :--- | :---: | :--- |
| **Phase 1: Telemetry Ingest** | Standard pandas deduplication | Mergesort deduplication on `(building_id, timestamp)` + seasonal weekday median profile imputation | **184 duplicates resolved; 32 missing hours imputed** | Preserved continuous time matrices without synthesizing fake energy spikes. |
| **Phase 2: Edge Waste AI** | 5 continuous sensor inputs (`weight`, `moisture`, `metal`, `transparency`, `piezo`) | Added saturation binary flags (100% glitch), missing sensor counts, and time-of-day edge context | **84.5% → 86.4% Accuracy (86.2% Macro F1)** | Physical sensors saturate under moisture; binary flags allow trees to isolate wet waste immediately. |
| **Phase 2b: MCU Quantization** | Full scikit-learn random forest model (50 MB) | Quantize into a compact 40-tree micro-forest serialized into pure JSON array logic | **50 MB → 120 KB RAM; 180 ms → 0.18 ms latency** | Directly executable in ESP32 SRAM / browser with 85.6% standalone accuracy. |
| **Phase 3: Demand Forecast** | Seasonal-Naive / Linear Ridge regression | LightGBM with 24h/168h seasonal lag features, weather vectors, and turnstile footfall | **32.1% → 14.2% WMAPE; 0.89 Spike F1** | Captures non-linear building interactions in 18 µs per inference on Raspberry Pi Zero. |
| **Phase 4: Anomaly Sentinel** | Static threshold alerts ($>3\sigma$) | Multi-factor evidence corroboration (NLP operator notes, academic calendar, peer variance) | **100% recall across all 13 ground-truth incidents** | Correctly resolved underground pipe leak, alumni food surge, and inverter failure. |

---

## 1. AI Tools & LLM Ecosystem Used

1. **Foundational Code & Architecture Models:**
   - **Gemini 3.8 / Gemma & Claude Opus:** Used for architecture decomposition, edge hardware trade-off modeling, and generating vectorized pipelines for multi-modal sensor fusion.
2. **Multi-Agent Facilities Copilot (Product Core):**
   - **NVIDIA Nemotron Super-49B / Llama 3.3:** Acts as the telemetry Analyst diagnosing root causes.
   - **Groq Llama 3.3 70B:** Acts as the operational Planner formulating concrete maintenance work-orders and calculating financial tariffs (₹8.00/kWh).
   - **Google Gemini 2.0 Flash:** Acts as the Verifier cross-checking proposed actions against ground-truth sensor evidence to eliminate hallucinations.
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

---

## 🏁 Verification & Downloads for Juries

- 📥 **[Download PROMPT_WORKBOOK.pdf](PROMPT_WORKBOOK.pdf)** — Official PDF Prompt Engineering Workbook.
- 📄 **[Download REPORT.pdf](REPORT.pdf)** — Official PDF Technical Evaluation Report.
- 🎬 **[View DEMO_VIDEO_SCRIPT.md](DEMO_VIDEO_SCRIPT.md)** — Production 5-minute timed video script.
- 💻 **[GitHub Repository](https://github.com/MDIbrahim08/CAMPUS-CHAKRA)** — Full open-source codebase.
